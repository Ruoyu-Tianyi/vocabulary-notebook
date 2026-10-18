"""词汇笔记本 — FastAPI 后端"""
import asyncio
import csv
import html as html_mod
import io
import math
import json
import os
import re
import socket
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fpdf import FPDF

import config
import fsrs
import sync_storage
from drive_sync import DriveSync
import instance_lock

# ─── App ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _event_queue, _enrich_queue
    cache_lock = instance_lock.acquire(DATA_FILE)
    # 启动时校验配置
    try:
        provider = config.get_provider()
        config.get_sync_config()
        print(f"  [config] provider: {provider}")
    except RuntimeError as e:
        print(f"  [config] 配置错误：{e}")
        cache_lock.close()
        raise
    try:
        load_words()  # fail before starting workers if the local cache is damaged
    except Exception:
        cache_lock.close()
        raise
    _event_queue = asyncio.Queue()
    _enrich_queue = asyncio.Queue()
    _enrich_jobs.clear()
    _enriching_ids.clear()
    worker_task = asyncio.create_task(_enrich_worker())
    backup_task = asyncio.create_task(_periodic_backup_loop())
    sync_task = asyncio.create_task(_cloud_sync_loop())
    yield
    sync_task.cancel()
    backup_task.cancel()
    worker_task.cancel()
    for t in (sync_task, backup_task, worker_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await asyncio.to_thread(cloud.lock.acquire)
    cloud.lock.release()
    cache_lock.close()


async def _periodic_backup_loop():
    """每 10 分钟把 words.json 原子复制到 words.json.bak。

    设计意图：这是 T18 期间数据被无痕覆盖的事后兜底 — 万一主文件被误删 / 损坏 /
    被代码错误重写，备份至少落后 ≤10 分钟。原子写（tmp+rename）保证备份本身不被中途
    写入中断。空数据跳过（避免把已丢的 0 词状态覆盖掉还能救的旧备份）。
    """
    while True:
        try:
            await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
        try:
            if not DATA_FILE.exists():
                continue
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if len(data.get("words", [])) < 1:
                # 跳过空数据，不让"丢失"状态覆盖掉能救的旧备份
                continue
            backup = DATA_FILE.with_suffix(".json.bak")
            tmp = DATA_FILE.with_suffix(".json.bak.tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(backup)
            print(f"  [backup] words.json → words.json.bak ({len(data['words'])} words)")
        except asyncio.CancelledError:
            return
        except Exception as e:
            # 备份失败不能拖垮服务
            print(f"  [backup] failed: {type(e).__name__}: {e}")


app = FastAPI(title="Drive Vocabulary Book", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1400", "http://127.0.0.1:1400", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in (
        "http://localhost:1400", "http://127.0.0.1:1400", "http://localhost:5173", "http://127.0.0.1:5173"
    ):
        return JSONResponse({"detail": "仅允许本地词汇本页面修改数据"}, status_code=403)
    return await call_next(request)

# ─── Config ───────────────────────────────────────────────

# 测试/临时验收可通过环境变量隔离数据；正常启动仍使用项目内 words.json。
DATA_FILE = Path(os.environ.get("VOCAB_DATA_FILE", "words.json"))
CHINA_TZ = timezone(timedelta(hours=8))
STATIC_DIR = Path("frontend/dist")

# SSE 事件总线 — 后台 enrichment 完成后通知前端
# 必须在 startup 事件中初始化，否则 asyncio.Queue() 会绑定到错误的 event loop（Python 3.9）
_event_queue = None

# 补全任务队列 — 单 worker 串行消费，控制 DeepSeek 请求并发
_enrich_queue: Optional[asyncio.Queue] = None
# word_id → 上次尝试时间戳，冷却期内不重复入队
_enriching_ids: dict[str, float] = {}
_enrich_jobs: dict[str, dict] = {}
_ENRICH_COOLDOWN = 300  # 秒
# 进度追踪
_enrich_current: Optional[str] = None
_enrich_batch_total: int = 0
_enrich_batch_done: int = 0

# ─── 周期备份 ────────────────────────────────────────────
# 后端运行时每 10 分钟把 words.json 原子复制到 words.json.bak。
# 万一主文件被误删/损坏/被代码错误重写，备份至少落后 ≤10 分钟。
BACKUP_INTERVAL_SECONDS = 600  # 10 分钟


# ─── PDF 字体路径 (fpdf2 纯 Python，零系统依赖) ──────────

_CJK_FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if not os.path.exists(_CJK_FONT_PATH):
    _CJK_FONT_PATH = next((font for font in (
        "C:/Windows/Fonts/simhei.ttf", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttf"
    ) if os.path.exists(font)), None)


# ─── PDF 表格化导出 ─────────────────────────────────────

def _estimate_lines(text: str, col_w_mm: float, font_size_pt: float) -> int:
    """估算文本在指定列宽（mm）和字号（pt）下需要多少行。

    启发式：CJK 字符 ≈ 1em，全角标点 ≈ 0.85em，
    ASCII 字母 ≈ 0.5em，数字 / 半角标点 ≈ 0.55em。
    """
    if not text:
        return 0
    em = font_size_pt * 0.3528  # pt → mm
    total_lines = 0
    for para in text.split("\n"):
        w = 0.0
        for ch in para:
            cp = ord(ch)
            if 0x2E80 <= cp <= 0x303E or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
                w += em * 1.0  # CJK / 全角
            elif 0xFF00 <= cp <= 0xFFEF:
                w += em * 0.85  # 全角标点
            elif ch.isascii() and ch.isalpha():
                w += em * 0.50  # Latin
            else:
                w += em * 0.55  # 数字 / 半角标点 / 其他
        total_lines += max(1, math.ceil(w / col_w_mm))
    return total_lines


def _build_pdf(words: list[dict], today: str, use_cjk: bool, cjk_font_path: Optional[str]) -> bytes:
    """渲染词汇笔记本 PDF：密集表格布局，~20 词/页。

    设计: Scholar's Compact
    - 顶栏: 标题 + 日期 + 计数 + 双线分割
    - 表头: 序号 / 单词 + 音标 / 释义 / 例句
    - 行: 斑马纹（极淡米色），超细分隔线
    - 字: 单词 Times Bold, 音标 Courier Italic, 释义 Helvetica, 例句 Italic
    - 底栏: 页码 + 总数
    """

    # ── 字体注册 ──
    class _VocabPDF(FPDF):
        def __init__(self):
            super().__init__("P", "mm", "A4")
            self._cjk = use_cjk
            self._word_count = len(words)
            if use_cjk:
                self.add_font("CJK", "", cjk_font_path)
                self.add_font("CJK", "B", cjk_font_path)
                self.add_font("CJK", "I", cjk_font_path)

    pdf = _VocabPDF()

    # ── 排版常量 ──
    M_L, M_R, M_T, M_B = 16, 16, 14, 16
    pdf.set_margins(M_L, M_T, M_R)
    pdf.set_auto_page_break(False)  # 手动控制分页
    pdf.set_left_margin(M_L)
    pdf.set_right_margin(M_R)
    pdf.set_top_margin(M_T)
    pdf.set_auto_page_break(False)

    PAGE_W = pdf.w  # 210
    CONTENT_W = PAGE_W - M_L - M_R  # 178

    # 列宽（mm）
    COL_NUM_W = 8
    COL_WORD_W = 36
    COL_DEF_W = 86
    COL_EX_W = CONTENT_W - COL_NUM_W - COL_WORD_W - COL_DEF_W  # 48

    COL_X = {
        "num": M_L,
        "word": M_L + COL_NUM_W,
        "def": M_L + COL_NUM_W + COL_WORD_W,
        "ex": M_L + COL_NUM_W + COL_WORD_W + COL_DEF_W,
    }

    # 行高常量
    LH_DEF = 8.5 * 0.3528 * 1.22  # 8.5pt × 1.22 leading ≈ 3.66mm
    LH_EX = 7.5 * 0.3528 * 1.22   # 7.5pt × 1.22 leading ≈ 3.23mm
    ROW_PAD_TOP = 1.6
    ROW_PAD_BOT = 1.4
    MIN_ROW_H = 8.8

    # 顶栏 + 表头占用高度
    HEADER_BAND_H = 11
    HEADER_RULE_GAP = 1.2
    COL_HEADER_H = 6.2
    COL_HEADER_GAP = 1.0
    TABLE_TOP_OFFSET = HEADER_BAND_H + HEADER_RULE_GAP + COL_HEADER_H + COL_HEADER_GAP
    TABLE_BOTTOM = pdf.h - M_B  # 281

    # ── 配色 ──
    C_TITLE = (38, 38, 38)
    C_META = (120, 116, 108)
    C_RULE = (180, 172, 156)        # 主分割线
    C_RULE_LITE = (215, 210, 196)   # 行间细线
    C_ZEBRA = (247, 243, 232)       # 斑马米色
    C_NUM = (170, 162, 142)         # 序号灰
    C_WORD = (20, 20, 20)
    C_PHON = (130, 130, 130)
    C_DEF = (60, 60, 60)
    C_EX = (110, 110, 110)
    C_HEADER_BG = (50, 46, 40)      # 表头深色背景
    C_HEADER_FG = (245, 240, 228)

    sans = "CJK" if use_cjk else "Helvetica"
    serif = "CJK" if use_cjk else "Times"
    mono = "CJK" if use_cjk else "Courier"

    # ── 头部 ──
    def draw_header():
        y = M_T
        # 标题行
        pdf.set_xy(M_L, y)
        pdf.set_font(serif, "B", 14)
        pdf.set_text_color(*C_TITLE)
        title = "VOCABULARY NOTEBOOK"
        pdf.cell(80, 6.5, title)
        # 副标题（中文）
        if use_cjk:
            pdf.set_xy(M_L, y + 6.5)
            pdf.set_font(sans, "", 8.5)
            pdf.set_text_color(*C_META)
            pdf.cell(80, 4, "词 汇 笔 记 本 · 导 出")
        # 元信息右对齐
        pdf.set_xy(M_L, y)
        pdf.set_font(mono, "", 8)
        pdf.set_text_color(*C_META)
        meta = f"{today}  ·  {len(words):>4} WORDS"
        pdf.cell(CONTENT_W, 6.5, meta, align="R")
        if use_cjk:
            pdf.set_xy(M_L, y + 6.5)
            pdf.set_font(sans, "", 7.5)
            pdf.cell(CONTENT_W, 4, f"导出日期 {today}    共 {len(words)} 个单词", align="R")
        # 双线分割
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.4)
        pdf.line(M_L, M_T + HEADER_BAND_H, M_L + CONTENT_W, M_T + HEADER_BAND_H)
        pdf.set_line_width(0.15)
        pdf.line(M_L, M_T + HEADER_BAND_H + 1.2, M_L + CONTENT_W, M_T + HEADER_BAND_H + 1.2)

    # ── 表头 ──
    def draw_col_header(y: float):
        h = COL_HEADER_H
        pdf.set_fill_color(*C_HEADER_BG)
        pdf.rect(M_L, y, CONTENT_W, h, style="F")
        pdf.set_font(sans if use_cjk else "Helvetica", "B", 8.5)
        pdf.set_text_color(*C_HEADER_FG)
        labels = [
            ("#",       COL_X["num"], COL_NUM_W, "C"),
            ("WORD",    COL_X["word"], COL_WORD_W, "L"),
            ("DEFINITION", COL_X["def"], COL_DEF_W, "L"),
            ("EXAMPLE", COL_X["ex"], COL_EX_W, "L"),
        ]
        for txt, x, w, align in labels:
            pdf.set_xy(x + 2, y + 1.6)
            pdf.cell(w - 4, h - 1.6, txt, align=align)
        return y + h

    # ── 表头后 ──
    def draw_table_separator(y: float):
        pdf.set_draw_color(*C_RULE_LITE)
        pdf.set_line_width(0.15)
        pdf.line(M_L, y, M_L + CONTENT_W, y)
        return y

    # ── 单行 ──
    def draw_row(idx: int, item: dict, y: float, zebra: bool):
        word = html_mod.unescape(item.get("word", "")).strip()
        phonetic = html_mod.unescape(item.get("phonetic", "")).strip()
        definition = html_mod.unescape(item.get("definition", "")).strip()
        example = html_mod.unescape(item.get("example", "")).strip()

        n_def = _estimate_lines(definition, COL_DEF_W - 4, 8.5)
        n_ex = _estimate_lines(example, COL_EX_W - 4, 7.5)
        text_h = n_def * LH_DEF + (n_ex * LH_EX + 1.0 if example else 0)
        row_h = max(MIN_ROW_H, ROW_PAD_TOP + text_h + ROW_PAD_BOT)

        # 斑马背景
        if zebra:
            pdf.set_fill_color(*C_ZEBRA)
            pdf.rect(M_L, y, CONTENT_W, row_h, style="F")

        # 序号（垂直居中）
        pdf.set_font(serif, "B", 8.5)
        pdf.set_text_color(*C_NUM)
        num_h = 4.0
        pdf.set_xy(COL_X["num"], y + (row_h - num_h) / 2)
        pdf.cell(COL_NUM_W, num_h, f"{idx:>3}", align="C")

        # 单词
        pdf.set_xy(COL_X["word"] + 1.5, y + ROW_PAD_TOP)
        pdf.set_font(serif, "B", 10.5)
        pdf.set_text_color(*C_WORD)
        pdf.cell(COL_WORD_W - 3, 4.4, word)
        # 音标
        if phonetic:
            pdf.set_xy(COL_X["word"] + 1.5, y + ROW_PAD_TOP + 4.2)
            pdf.set_font(mono, "I", 7)
            pdf.set_text_color(*C_PHON)
            pdf.cell(COL_WORD_W - 3, 3.2, phonetic)

        # 释义
        pdf.set_xy(COL_X["def"] + 1.5, y + ROW_PAD_TOP)
        pdf.set_font(sans, "", 8.5)
        pdf.set_text_color(*C_DEF)
        lines_def = _wrap_lines(definition, COL_DEF_W - 3, 8.5)
        cy = y + ROW_PAD_TOP
        for ln in lines_def[:max(1, n_def)]:
            pdf.set_xy(COL_X["def"] + 1.5, cy)
            pdf.cell(COL_DEF_W - 3, LH_DEF, ln)
            cy += LH_DEF

        # 例句（缩进 + 斜体）
        if example and n_ex > 0:
            cy += 0.5
            ex_text = f'“{example}”'
            lines_ex = _wrap_lines(ex_text, COL_EX_W - 3, 7.5)
            pdf.set_font(sans, "I", 7.5)
            pdf.set_text_color(*C_EX)
            for ln in lines_ex[:max(1, n_ex)]:
                pdf.set_xy(COL_X["ex"] + 1.5, cy)
                pdf.cell(COL_EX_W - 3, LH_EX, ln)
                cy += LH_EX

        # 行底分割线
        pdf.set_draw_color(*C_RULE_LITE)
        pdf.set_line_width(0.12)
        pdf.line(M_L, y + row_h, M_L + CONTENT_W, y + row_h)
        pdf.set_line_width(0.15)

        return y + row_h

    # ── 文本换行（基于宽度估算） ──
    def _wrap_lines(text: str, max_w_mm: float, font_size_pt: float) -> list[str]:
        """按列宽把文本切成行。CJK 字符可断，Latin 按词断。"""
        if not text:
            return [""]
        em = font_size_pt * 0.3528
        out: list[str] = []
        for para in text.split("\n"):
            cur = ""
            cur_w = 0.0
            # 按字符遍历，CJK 单字断、Latin 按空格切词
            i = 0
            tokens: list[str] = []
            buf = ""
            for ch in para:
                cp = ord(ch)
                if 0x2E80 <= cp <= 0x303E or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
                    if buf:
                        tokens.append(buf)
                        buf = ""
                    tokens.append(ch)  # CJK 单字 token
                elif ch == " ":
                    if buf:
                        tokens.append(buf)
                        buf = ""
                    tokens.append(" ")
                else:
                    buf += ch
            if buf:
                tokens.append(buf)

            for tk in tokens:
                w = 0.0
                for ch in tk:
                    cp = ord(ch)
                    if 0x2E80 <= cp <= 0x303E or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
                        w += em * 1.0
                    elif 0xFF00 <= cp <= 0xFFEF:
                        w += em * 0.85
                    elif ch.isascii() and ch.isalpha():
                        w += em * 0.5
                    else:
                        w += em * 0.55
                if cur_w + w <= max_w_mm or not cur:
                    cur += tk
                    cur_w += w
                else:
                    out.append(cur.rstrip())
                    cur = tk.lstrip() if tk != " " else ""
                    cur_w = w if tk != " " else 0
            if cur:
                out.append(cur.rstrip())
        return out

    # ── 页脚 ──
    def draw_footer():
        pdf.set_xy(M_L, pdf.h - M_B + 4)
        pdf.set_font(sans if use_cjk else "Helvetica", "", 7.5)
        pdf.set_text_color(*C_META)
        left = "Vocab Notebook"
        right = f"{pdf.page_no()} / {pdf.pages_count}"
        pdf.cell(CONTENT_W / 2, 4, left)
        pdf.cell(CONTENT_W / 2, 4, right, align="R")
        # 细线
        pdf.set_draw_color(*C_RULE_LITE)
        pdf.set_line_width(0.15)
        pdf.line(M_L, pdf.h - M_B + 3, M_L + CONTENT_W, pdf.h - M_B + 3)

    # ── 渲染循环 ──
    pdf.add_page()
    draw_header()
    y = M_T + TABLE_TOP_OFFSET
    draw_table_separator(y - 0.5)
    y = draw_col_header(y - 0.5)

    for idx, item in enumerate(words, 1):
        # 预估算行高，检查是否放得下
        definition = html_mod.unescape(item.get("definition", ""))
        example = html_mod.unescape(item.get("example", ""))
        n_def_est = _estimate_lines(definition, COL_DEF_W - 4, 8.5)
        n_ex_est = _estimate_lines(example, COL_EX_W - 4, 7.5)
        text_h_est = n_def_est * LH_DEF + (n_ex_est * LH_EX + 1.0 if example else 0)
        row_h_est = max(MIN_ROW_H, ROW_PAD_TOP + text_h_est + ROW_PAD_BOT)

        # 放不下则分页
        if y + row_h_est > TABLE_BOTTOM:
            draw_footer()
            pdf.add_page()
            draw_header()
            y = M_T + TABLE_TOP_OFFSET
            draw_table_separator(y - 0.5)
            y = draw_col_header(y - 0.5)

        y = draw_row(idx, item, y, zebra=(idx % 2 == 0))

    draw_footer()

    return bytes(pdf.output())


# RLock 允许同一线程重入，_enrich_in_background 可在锁内 load+save
_write_lock = threading.RLock()
cloud = DriveSync(lambda: DATA_FILE, _write_lock, config.get_sync_config)


async def _cloud_sync_loop():
    while True:
        try:
            if cloud.status()["connected"] and not cloud.auth_pending:
                await asyncio.to_thread(cloud.sync)
        except (ValueError, RuntimeError, OSError) as exc:
            cloud.error = str(exc)[:250]
        await asyncio.sleep(config.get_sync_config()["interval_seconds"])


def load_words() -> dict:
    """读取可离线使用的云端词库缓存；旧 words.json 自动无损迁移。"""
    with _write_lock:
        return sync_storage.read(DATA_FILE)


def save_words(data: dict) -> None:
    """原子写入：先写临时文件再替换，防止并发写丢数据和写入中断损坏"""
    with _write_lock:
        sync_storage.commit(DATA_FILE, data)


def now_iso() -> str:
    return datetime.now(CHINA_TZ).isoformat()


# ─── 间隔复习辅助 ────────────────────────────────────────

def _parse_review_time(value: str) -> datetime:
    """解析复习时间；兼容早期可能写入的无时区 ISO 字符串。"""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=CHINA_TZ)
    return parsed.astimezone(CHINA_TZ)


def _review_due_at(srs_state: dict) -> datetime:
    """返回卡片到期时间；旧数据没有 due_at 时按 FSRS 状态回算。"""
    difficulty = float(srs_state["d"])
    stability = float(srs_state["s"])
    if not math.isfinite(difficulty) or not 1.0 <= difficulty <= 10.0:
        raise ValueError("invalid difficulty")
    if not math.isfinite(stability) or stability <= 0:
        raise ValueError("invalid stability")
    last_review = _parse_review_time(srs_state["last_review_at"])
    if srs_state.get("due_at"):
        return _parse_review_time(srs_state["due_at"])
    interval_days = fsrs.next_interval(stability)
    return last_review + timedelta(days=interval_days)


def _new_reviews_today(words: list[dict], now: datetime) -> int:
    """从持久化的首次复习时间计算今日新学量，服务重启后不会清零。"""
    today = now.astimezone(CHINA_TZ).date()
    count = 0
    for word in words:
        first_review = (word.get("srs") or {}).get("first_review_at")
        if first_review:
            try:
                if _parse_review_time(first_review).date() == today:
                    count += 1
            except (TypeError, ValueError):
                continue
    return count


def _predicted_intervals(srs_state: Optional[dict], now: datetime) -> dict[str, str]:
    """预览四档评分对应的下一次复习间隔。"""
    intervals = {}
    for rating in (1, 2, 3, 4):
        if not srs_state:
            next_stability = fsrs.initial_stability(rating)
        else:
            last_review = _parse_review_time(srs_state["last_review_at"])
            elapsed_days = max((now - last_review).total_seconds() / 86400, 0.0)
            difficulty = float(srs_state["d"])
            stability = float(srs_state["s"])
            retrievability = fsrs.retrievability(elapsed_days, stability)
            if rating == 1:
                next_stability = fsrs.next_forget_stability(
                    difficulty, stability, retrievability
                )
            else:
                next_stability = fsrs.next_recall_stability(
                    difficulty, stability, retrievability, rating
                )
        seconds = fsrs.next_interval(next_stability) * 86400
        intervals[str(rating)] = fsrs.format_interval(seconds)
    return intervals


def _review_stats_for(words: list[dict], now: datetime, daily_new_limit: int) -> dict:
    """计算当前复习统计；损坏的 SRS 状态不应拖垮整个列表。"""
    reviewable = [word for word in words if word.get("definition", "").strip()]
    new_words = [word for word in reviewable if not word.get("srs")]
    due_reviews = []
    invalid_count = 0
    for word in reviewable:
        if not word.get("srs"):
            continue
        try:
            if _review_due_at(word["srs"]) <= now:
                due_reviews.append(word)
        except (KeyError, TypeError, ValueError):
            invalid_count += 1

    new_today = _new_reviews_today(reviewable, now)
    new_quota = max(0, daily_new_limit - new_today)
    return {
        "total": len(reviewable),
        "due_today": len(due_reviews) + min(len(new_words), new_quota),
        "new_remaining": len(new_words),
        "review_due": len(due_reviews),
        "new_today": new_today,
        "daily_new_limit": daily_new_limit,
        "invalid_count": invalid_count,
    }


async def enrich_word(word: str, context: str = "") -> tuple[str, str, str]:
    """调用配置好的 Provider 补充音标、释义和例句，返回 (phonetic, definition, example)。失败返回空串。"""
    import logging
    logger = logging.getLogger("uvicorn")

    prompt = f'''For the English word "{word}", provide its dictionary
headword's phonetic, definition, and an English example.

CRITICAL — determine the canonical headword first:
- "{word}" may be a plural, past tense, past participle, or
  present participle. If so, set "word" to the base headword
  form, but in "definition" describe the ACTUAL INPUT — note
  the relationship to the base explicitly:
  - "granules"    → word: "granule",    definition: "n. granule 的复数,颗粒,微粒"
  - "esteemed"    → word: "esteem",     definition: "vt. esteem 的过去式,受尊敬的,受敬重的"
  - "converged"   → word: "converge",   definition: "vi. converge 的过去式,会合,聚集,收敛"
  - "amassing"    → word: "amass",      definition: "vt. amass 的现在分词,积累,正在积聚的"
  - "coordinated" → word: "coordinate", definition: "vt. coordinate 的过去式/过去分词,协调,协作;adj. 同等的,并列的"
- Exception: keep "{word}" as the headword when it IS itself
  an established entry — i.e., it is NOT just a derived form
  of another word but a standalone word that happens to share
  a form. Examples:
  - -ing nouns:  running, swimming, meeting, building, writing,
    cooking, feeling, offspring, sapling, bowstring, fundraising
  - -ed/-ing adjectives:  talented, frightening, fascinating,
    engrossing, compelling, pressing, rugged, alleged, emboldened,
    esteemed, tired, bored, excited, interested, devoted, retired,
    concerted, united, divided, undivided, branded (as adj)
  - Pluralia tantum / common-plural nouns:  millennia, larvae
    (when treated as a collective / established plural form)
  In these cases the input form IS the headword — keep it and
  provide its own definition.
- Do not invent senses for "{word}" that are not in major
  English dictionaries.
- "{word}" may only be an adjective — do not add a noun/verb
  sense that doesn't exist (e.g., "intricate" is adj only).
- For homonyms or polysemous words with distinct meanings
  (e.g., "found" = both "to discover" /faɪnd/ AND
  "to establish" /faʊnd/), list EVERY distinct meaning with
  its POS, Chinese translation, and pronunciation. Do not
  collapse multiple meanings into one or omit any.

CRITICAL — handle unrecognized words honestly:
- If "{word}" is a single word not in standard English
  dictionaries (typo, nonsense, abbreviation you're unsure
  of), return an empty JSON:
  {{"phonetic":"", "definition":"", "example":""}}
  Do NOT fabricate definitions for words you don't recognize.
- If "{word}" is a multi-word phrase (contains a space), it
  is a legitimate entry — treat it as a valid headword and
  return its phrase meaning (e.g., "in advance of", "take
  no notice of", "bottle stoppers"). Do NOT refuse phrases.
- For proper nouns, brand names, or technical jargon you're
  not certain about, also return empty JSON. Better to leave
  a word empty than to invent a fake meaning.
- When uncertain about any field, leave that field empty
  rather than guessing.

Examples:
  "granules"  → headword "granule" (n.)
  "esteemed"  → headword "esteem" (vt. / n.)
  "running"   → headword "running" (n.)
  "amassing"  → headword "amass" (vt.)
  "converged" → headword "converge" (vi.)

The example sentence MUST be in English (not Chinese), short,
and illustrate one of the senses above.

The definition MUST be written in Chinese (中文), even for
common English words. English-only definitions are not
acceptable — translate every sense into Chinese.

Use POS abbreviations: vt. vi. n. adj. adv. prep. conj. pron.
Synonyms of the same POS belong on ONE line, separated by
Chinese comma (，). Every line MUST start with a POS abbreviation.
When listing multiple definitions, put the most common /
primary meaning first (e.g., "pharmacy" — "药店" comes before
"药学"; "bank" — "银行" comes before "河岸").

Reply ONLY with a JSON object, no other text:
{{"phonetic": "/.../", "definition": "n. 释义一，释义二\\nvt. 及物释义", "example": "..."}}'''
    if context:
        prompt += "\nCourse context (use for sense and example selection): " + context[:600]
    try:
        settings = config.get_deepseek_config()
        if not settings["api_key"]:
            return "", "", ""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("https://api.deepseek.com/chat/completions", json={
                "model": settings["model"], "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"},
                "max_tokens": 2048, "stream": False,
            }, headers={"Authorization": "Bearer " + settings["api_key"]})
            resp.raise_for_status()
            text = (resp.json()["choices"][0]["message"]["content"] or "").strip()

        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not match:
            logger.warning("[enrich] DeepSeek 响应中未找到 JSON 对象")
            return "", "", ""
        data = json.loads(match.group())
        fields = tuple(data.get(key, "") for key in ("phonetic", "definition", "example"))
        return fields if all(isinstance(value, str) for value in fields) else ("", "", "")
    except Exception as e:
        code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "unavailable"
        logger.warning("[enrich] DeepSeek 请求失败：%s (%s)", type(e).__name__, code)
        return "", "", ""


# ─── API: SSE 事件流 ──────────────────────────────────────

@app.get("/api/events")
async def event_stream(request: Request):
    """SSE 端点 — 推送 enrichment 完成事件"""

    async def generate():
        if _event_queue is None:
            return
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(_event_queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── API: 健康检查 ────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Check credentials/model availability without a billable generation request."""
    settings = config.get_deepseek_config()
    result = {"provider": "deepseek", "model": settings["model"]}
    if not settings["api_key"]:
        return {**result, "status": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://api.deepseek.com/models", headers={"Authorization": "Bearer " + settings["api_key"]})
            if resp.status_code == 401:
                return {**result, "status": "unauthorized"}
            if resp.is_success:
                available = {item["id"] for item in resp.json().get("data", [])}
                return {**result, "status": "connected" if settings["model"] in available else "model_unavailable"}
    except Exception:
        pass
    return {**result, "status": "disconnected"}


@app.get("/api/ai/settings")
def ai_settings():
    return config.get_ai_settings()


@app.put("/api/ai/settings")
def update_ai_settings(body: dict):
    try:
        return config.save_ai_settings(body.get("api_key", ""), body.get("model", config.DEFAULT_MODEL))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ─── API: 单词 CRUD ───────────────────────────────────────

def _text(body, key, default="", limit=100000):
    value = body.get(key, default)
    if not isinstance(value, str) or len(value) > limit:
        raise HTTPException(422, f"{key} 必须是长度不超过 {limit} 的文本")
    return value.strip()


def _book_words(data, notebook_id):
    if notebook_id:
        if not any(book["id"] == notebook_id for book in data["notebooks"]):
            raise HTTPException(404, "单词本不存在，请重新选择")
        return [word for word in data["words"] if word.get("notebook_id", "default") == notebook_id]
    return data["words"]


@app.get("/api/notebooks")
def list_notebooks():
    data = load_words()
    return {"notebooks": [{**book, "word_count": len(_book_words(data, book["id"]))}
                          for book in data["notebooks"]]}


@app.post("/api/notebooks")
def create_notebook(body: dict):
    name = _text(body, "name", limit=80)
    if not name:
        raise HTTPException(422, "单词本名称不能为空")
    with _write_lock:
        data = load_words()
        book = {"id": uuid.uuid4().hex, "name": name,
                "description": _text(body, "description", limit=500), "created_at": now_iso()}
        data["notebooks"].append(book)
        save_words(data)
    return {"notebook": book}


@app.put("/api/notebooks/{notebook_id}")
def update_notebook(notebook_id: str, body: dict):
    with _write_lock:
        data = load_words()
        for book in data["notebooks"]:
            if book["id"] == notebook_id:
                name = _text(body, "name", book["name"], limit=80)
                if not name:
                    raise HTTPException(422, "单词本名称不能为空")
                book.update(name=name, description=_text(body, "description", book.get("description", ""), limit=500))
                save_words(data)
                return {"notebook": book}
    raise HTTPException(404, "单词本不存在")


@app.get("/api/sync/status")
def sync_status():
    return cloud.status()


@app.post("/api/sync/credentials")
def import_drive_credentials(body: dict):
    try:
        cloud.import_credentials(body)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/sync/connect")
def connect_drive():
    try:
        return cloud.begin_auth()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/sync/folder")
def configure_sync_folder(body: dict):
    try:
        return cloud.configure_folder(_text(body, "folder_path", limit=1000))
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/sync/disconnect")
def disconnect_drive():
    try:
        cloud.disconnect()
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/sync/run")
def run_sync():
    result = cloud.sync()
    if result.get("error"):
        raise HTTPException(503, result["error"])
    return result


@app.get("/api/library/export")
def export_library():
    data = load_words()
    return JSONResponse({"version": sync_storage.VERSION, "operations": list(data["_sync"]["operations"].values()),
                         "words": data["words"], "notebooks": data["notebooks"], "exported_at": now_iso()},
                        headers={"Content-Disposition": "attachment; filename=vocabulary-library.json"})


@app.post("/api/library/import")
def import_library(body: dict):
    if "operations" in body:
        if body.get("version") != sync_storage.VERSION:
            raise HTTPException(422, "备份版本不兼容")
        try:
            with _write_lock:
                count = sync_storage.merge(DATA_FILE, body["operations"])
            return {"imported": count, "message": f"已合并 {count} 条变更及复习记录"}
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, "备份变更记录无效，未导入") from exc
    words, books = body.get("words"), body.get("notebooks", [])
    if not isinstance(words, list) or len(words) > 50000 or not isinstance(books, list) or len(books) > 500:
        raise HTTPException(422, "请选择词库 JSON 备份文件")
    # Validate the entire import before touching the live cache.
    clean_books, clean_words = [], []
    for book in books:
        if not isinstance(book, dict):
            raise HTTPException(422, "单词本格式无效")
        clean_books.append({"id": _text(book, "id", limit=200), "name": _text(book, "name", limit=80),
                            "description": _text(book, "description", limit=500)})
        if not clean_books[-1]["id"] or not clean_books[-1]["name"]:
            raise HTTPException(422, "单词本 ID 与名称不能为空")
    for word in words:
        if not isinstance(word, dict):
            raise HTTPException(422, "单词格式无效")
        cleaned = {key: _text(word, key, limit=200 if key in ("id", "notebook_id") else 100000)
                   for key in ("id", "word", "definition", "phonetic", "example", "created_at", "notebook_id")}
        cleaned["notebook_id"] = cleaned["notebook_id"] or "default"
        if not cleaned["id"] or not cleaned["word"]:
            raise HTTPException(422, "单词 ID 与拼写不能为空")
        if word.get("srs"):
            cleaned["srs"] = word["srs"]
            try:
                _review_due_at(cleaned["srs"])
            except (KeyError, TypeError, ValueError) as exc:
                raise HTTPException(422, "备份中的复习状态无效") from exc
        # A portable backup contains the final SRS state, not replayable old events.
        clean_words.append(cleaned)
    with _write_lock:
        data = load_words()
        known_books = {book["id"] for book in data["notebooks"]}
        for book in clean_books:
            if book["id"] not in known_books:
                data["notebooks"].append(book)
                known_books.add(book["id"])
        known_words = {word["id"] for word in data["words"]}
        imported = 0
        for word in clean_words:
            if word["notebook_id"] not in known_books:
                raise HTTPException(422, "备份引用了不存在的单词本")
            if word["id"] not in known_words:
                # Use a new identity for a previously deleted word, retaining its schedule.
                if any(op["entity_id"] == word["id"] and op["field"] == "deleted"
                       for op in data["_sync"]["operations"].values()):
                    word["id"] = uuid.uuid4().hex
                data["words"].append(word)
                known_words.add(word["id"])
                imported += 1
        save_words(data)
    return {"imported": imported, "message": f"已导入 {imported} 个单词；已有记录保留原样"}

@app.get("/api/words")
def list_words(
    q: str = Query(default=""),
    date: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=10000),
    sort: str = Query(default=""),
    letter: str = Query(default=""),
    notebook_id: str = "",
):
    data = load_words()
    data["words"] = _book_words(data, notebook_id)
    # 先按 q+date+sort 过滤一次，用于计算 available_letters（不含 letter 自身的影响）
    pre_letter = _filter_words(data, q, date, sort)
    available_letters = sorted({
        w["word"][0].lower() for w in pre_letter if w.get("word")
    })

    words = _filter_words(data, q, date, sort, letter)

    total = len(words)
    start = (page - 1) * size
    page_words = words[start : start + size]

    return {
        "words": page_words,
        "total": total,
        "page": page,
        "size": size,
        "pages": max((total + size - 1) // size, 1),
        "available_letters": available_letters,
    }


@app.get("/api/dates")
def list_dates(notebook_id: str = ""):
    data = load_words()
    dates = sorted({
        w["created_at"][:10]
        for w in _book_words(data, notebook_id)
        if "created_at" in w
    }, reverse=True)
    return {"dates": dates}


# ─── API: 间隔复习 ────────────────────────────────────────

@app.get("/api/review/stats")
def review_stats(notebook_id: str = ""):
    """返回导航角标和复习页需要的轻量统计。"""
    now = datetime.now(CHINA_TZ)
    daily_new_limit = config.get_srs_config()["daily_new_limit"]
    return _review_stats_for(_book_words(load_words(), notebook_id), now, daily_new_limit)


@app.get("/api/review/due")
def review_due(limit: int = Query(default=20, ge=1, le=100), notebook_id: str = ""):
    """返回一批到期卡片：逾期复习优先，再用新词填满剩余额度。"""
    now = datetime.now(CHINA_TZ)
    daily_new_limit = config.get_srs_config()["daily_new_limit"]
    words = [
        word for word in _book_words(load_words(), notebook_id)
        if word.get("definition", "").strip()
    ]
    stats = _review_stats_for(words, now, daily_new_limit)

    due_reviews = []
    for word in words:
        if not word.get("srs"):
            continue
        try:
            due_at = _review_due_at(word["srs"])
        except (KeyError, TypeError, ValueError):
            continue
        if due_at <= now:
            due_reviews.append((word, due_at))
    due_reviews.sort(key=lambda item: item[1])

    review_take = [word for word, _ in due_reviews[:limit]]
    remaining_slots = limit - len(review_take)
    new_quota = max(0, daily_new_limit - stats["new_today"])
    new_words = sorted(
        (word for word in words if not word.get("srs")),
        key=lambda word: word.get("created_at", ""),
    )
    new_take = new_words[:min(remaining_slots, new_quota)]

    cards = []
    for word in review_take + new_take:
        cards.append({
            **word,
            "is_new": not bool(word.get("srs")),
            "predicted_intervals": _predicted_intervals(word.get("srs"), now),
        })
    return {"cards": cards, "stats": stats}


@app.post("/api/words/{word_id}/review")
def post_review(word_id: str, body: dict):
    """记录一次评分并原子更新该单词的 FSRS 状态。"""
    rating = body.get("rating")
    if type(rating) is not int or rating not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="rating 必须是 1、2、3 或 4")

    now = datetime.now(CHINA_TZ)
    with _write_lock:
        data = load_words()
        word = next((item for item in data["words"] if item["id"] == word_id), None)
        if word is None:
            raise HTTPException(status_code=404, detail="单词不存在")
        if not word.get("definition", "").strip():
            raise HTTPException(status_code=409, detail="缺少释义的单词暂不能复习")

        previous = word.get("srs")
        if previous:
            try:
                last_review = _parse_review_time(previous["last_review_at"])
                elapsed_days = max((now - last_review).total_seconds() / 86400, 0.0)
                difficulty, stability = fsrs.update(
                    float(previous["d"]),
                    float(previous["s"]),
                    rating,
                    elapsed_days,
                )
                first_review_at = previous.get(
                    "first_review_at", previous["last_review_at"]
                )
                reps = int(previous.get("reps", 0)) + 1
                lapses = int(previous.get("lapses", 0)) + (1 if rating == 1 else 0)
            except (KeyError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail="该单词的复习状态已损坏") from exc
        else:
            difficulty = fsrs.initial_difficulty(rating)
            stability = fsrs.initial_stability(rating)
            first_review_at = now.isoformat()
            reps = 1
            lapses = 1 if rating == 1 else 0

        interval_days = fsrs.next_interval(stability)
        due_at = now + timedelta(days=interval_days)
        word["srs"] = {
            "d": difficulty,
            "s": stability,
            "first_review_at": first_review_at,
            "last_review_at": now.isoformat(),
            "due_at": due_at.isoformat(),
            "reps": reps,
            "lapses": lapses,
        }
        word.setdefault("review_history", []).append({"id": uuid.uuid4().hex, "rating": rating, "at": now.isoformat()})
        save_words(data)

    card = {
        **word,
        "is_new": False,
        "predicted_intervals": _predicted_intervals(word["srs"], now),
    }
    interval_seconds = interval_days * 86400
    return {
        "word": word,
        "card": card,
        "next_interval_seconds": interval_seconds,
        "next_interval": fsrs.format_interval(interval_seconds),
    }


# 注意：/api/words/export 和 /api/words/enrich-missing 路由必须在
# /api/words/{word_id} 之前，否则会被当成 word_id 匹配。
@app.get("/api/words/export")
def export_words(
    format: str = Query(default="json"),
    q: str = Query(default=""),
    date: str = Query(default=""),
    sort: str = Query(default=""),
    notebook_id: str = "",
):
    data = load_words()
    data["words"] = _book_words(data, notebook_id)
    words = _filter_words(data, q, date, sort)
    today = datetime.now(CHINA_TZ).strftime("%Y-%m-%d")

    if format == "csv":
        out = io.StringIO()
        out.write("﻿")  # UTF-8 BOM — Excel 看这个知道是 UTF-8,不会按 GBK 误读
        w = csv.writer(out)
        w.writerow(["单词", "音标", "释义", "例句", "日期"])
        for item in words:
            w.writerow([item["word"], item["phonetic"], item["definition"], item["example"], item["created_at"][:10]])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue().encode("utf-8")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=vocabulary-{today}.csv"},
        )

    if format == "pdf":
        use_cjk = _CJK_FONT_PATH is not None
        pdf_bytes = _build_pdf(words, today, use_cjk, _CJK_FONT_PATH)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=vocabulary-{today}.pdf"},
        )

    # 默认 JSON
    out = io.StringIO()
    json.dump({"words": words, "notebooks": data["notebooks"], "exported_at": now_iso()}, out, ensure_ascii=False, indent=2)
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=vocabulary-{today}.json"},
    )


async def _enqueue_enrich_batch(items: list) -> None:
    """送入 enrich 队列并累加 batch 计数器。

    仅做"入队 + 累加"，不做重置。重置由调用方在合适的时机显式调用
    `_maybe_reset_batch_if_idle()`，这样 enrich-missing 即使在 0 missing 提前
    return 的路径上也能把上一批残留状态清掉。

    调用方必须在同一协程内连续调用（不要跨 await），这样检查 + 入队 + 计数的
    同步段不会被 worker 协程打断，竞态安全。
    """
    global _enrich_batch_total
    if not items:
        return
    now = asyncio.get_event_loop().time()
    added = 0
    for word_id, word_text in items:
        if _enrich_jobs.get(word_id, {}).get("status") in ("queued", "processing"):
            continue
        _enrich_jobs[word_id] = {"status": "queued"}
        _enriching_ids[word_id] = now
        await _enrich_queue.put((word_id, word_text))
        added += 1
    _enrich_batch_total += added


def _maybe_reset_batch_if_idle() -> None:
    """若 worker 空闲 + 队列空 + 上一批已结束，重置 batch 计数器。

    同步函数：调用方必须在 _enrich_queue.put 之前同一同步段内执行，竞态安全。
    """
    global _enrich_batch_total, _enrich_batch_done
    if not _enrich_current and _enrich_queue.qsize() == 0 and _enrich_batch_total > 0:
        _enrich_batch_total = 0
        _enrich_batch_done = 0


@app.post("/api/words/enrich-missing")
async def enrich_missing(notebook_id: str = ""):
    """扫描缺失 definition 的单词，跳过冷却期内已完成/进行中的。"""
    # 入口处先尝试重置上一批残留状态 — 即使下面 0 missing 提前 return，
    # 也能让 batch_total/batch_done 清零，避免污染后续观察。
    _maybe_reset_batch_if_idle()
    now = asyncio.get_event_loop().time()
    data = load_words()
    data["words"] = _book_words(data, notebook_id)
    missing = [
        w for w in data["words"]
        if not w.get("definition", "").strip()
        and _enrich_jobs.get(w["id"], {}).get("status") not in ("queued", "processing")
        and _enriching_ids.get(w["id"], 0) + _ENRICH_COOLDOWN < now
    ]
    if not missing:
        in_cooldown = sum(
            1 for w in data["words"]
            if not w.get("definition", "").strip()
            and _enriching_ids.get(w["id"], 0) + _ENRICH_COOLDOWN >= now
        )
        msg = f"没有需要补全的单词" if not in_cooldown else f"{in_cooldown} 个单词正在补全中或刚尝试过，请稍后"
        return {"enriched": 0, "message": msg}

    await _enqueue_enrich_batch([(w["id"], w["word"]) for w in missing])

    return {
        "enriched": len(missing),
        "word_ids": [w["id"] for w in missing],
        "message": f"已加入 {len(missing)} 个单词到补全队列，逐个处理中",
    }


@app.get("/api/enrich/progress")
def enrich_progress():
    """返回当前 enrichment 队列进度"""
    queue_size = _enrich_queue.qsize() if _enrich_queue else 0
    data = load_words()
    total_missing = sum(
        1 for w in data["words"]
        if not w.get("definition", "").strip()
    )
    return {
        "queue_size": queue_size,
        "current_word": _enrich_current,
        "batch_total": _enrich_batch_total,
        "batch_done": _enrich_batch_done,
        "total_missing": total_missing,
        "is_processing": _enrich_current is not None,
    }


@app.get("/api/words/{word_id}")
def get_word(word_id: str):
    data = load_words()
    for w in data["words"]:
        if w["id"] == word_id:
            return {"word": w, "enrichment": _word_enrichment(w)}
    raise HTTPException(status_code=404, detail="单词不存在")


def _word_enrichment(word):
    if word.get("definition", "").strip():
        return {"status": "ready"}
    if word["id"] in _enrich_jobs:
        return dict(_enrich_jobs[word["id"]])
    return {"status": "idle" if config.get_ai_settings()["configured"] else "not_configured"}


@app.post("/api/words/{word_id}/enrich")
async def retry_word_enrichment(word_id: str):
    word = get_word(word_id)["word"]
    if not word.get("definition", "").strip() and config.get_ai_settings()["configured"]:
        if _enrich_queue is None:
            raise HTTPException(503, "补全服务尚未启动，请重启词汇本")
        await _enqueue_enrich_batch([(word_id, word["word"])])
    return {"word": word, "enrichment": _word_enrichment(word)}


def _normalize_new_word(text: str) -> str:
    """Uppercase the English initial of a new entry without altering the remaining text."""
    if text and "a" <= text[0] <= "z":
        return text[0].upper() + text[1:]
    return text


@app.post("/api/words")
async def create_word(body: dict):
    word_text = _normalize_new_word(_text(body, "word", limit=200))
    if not word_text:
        raise HTTPException(status_code=422, detail="单词不能为空")
    with _write_lock:
        data = load_words()
        notebook_id = _text(body, "notebook_id", "default", limit=200)
        if not notebook_id:
            raise HTTPException(422, "请选择保存到的单词本")
        scoped = _book_words(data, notebook_id)
        existing = next((w for w in scoped if w["word"].casefold() == word_text.casefold()), None)
        if existing is not None:
            raise HTTPException(409, {"message": f"「{existing['word']}」已在这个单词本中，已展示已有内容",
                                      "word": existing, "enrichment": _word_enrichment(existing)})
        word_id = uuid.uuid4().hex
        word_obj = {"id": word_id, "word": word_text, "notebook_id": notebook_id,
                    "definition": _text(body, "definition"), "phonetic": _text(body, "phonetic"),
                    "example": _text(body, "example"), "created_at": now_iso()}
        data["words"].append(word_obj)
        save_words(data)

    # 送入补全队列，后台串行处理（持续累加，不重置 — 用户显式补全缺失才是新一批）
    if not word_obj["definition"] and _enrich_queue is not None and config.get_ai_settings()["configured"]:
        await _enqueue_enrich_batch([(word_id, word_text)])

    return {"word": word_obj, "enrichment": _word_enrichment(word_obj)}


async def _enrich_worker():
    """单 worker 串行调用 DeepSeek，保留人工编辑内容。"""
    global _enrich_current, _enrich_batch_done
    import logging
    logger = logging.getLogger("uvicorn")
    logger.warning("[enrich-worker] started")
    while True:
        word_id, word_text = await _enrich_queue.get()
        _enrich_jobs[word_id] = {"status": "processing"}
        _enrich_current = word_text
        logger.warning(f"[enrich-worker] picked: {word_text!r} id={word_id}")
        try:
            current_data = load_words()
            current_word = next((w for w in current_data["words"] if w["id"] == word_id), None)
            if current_word is None:
                continue
            book = next((b for b in current_data["notebooks"] if b["id"] == current_word.get("notebook_id")), {})
            context = book.get("name", "") + ": " + book.get("description", "")
            phonetic, definition, example = await enrich_word(word_text, context)
            if not phonetic and not definition and not example:
                _enrich_jobs[word_id] = {"status": "failed", "error": "DeepSeek 未返回有效释义，请检查 API Key、余额与网络后重试。"}
                # 全空响应。词组(空格)静默不打扰 — 可能是 deepseek 对该词组不熟;
                # 单个词推 toast 提示 — 可能是拼错/不存在/网络失败。
                logger.warning(f"[enrich] {word_text} — deepseek 返回空")
                if " " not in word_text and _event_queue is not None:
                    await _event_queue.put({
                        "type": "enrich_failed",
                        "word_id": word_id,
                        "word": word_text,
                        "reason": "DeepSeek 未返回有效内容，请检查本机 API Key、余额与网络，或手动填写释义",
                    })
                _enriching_ids.pop(word_id, None)
                continue

            # 后处理校验：拦截拼写错/中文例句/词性误标
            ok, reason = _enrich_post_check(word_text, phonetic, definition, example)
            if not ok:
                _enrich_jobs[word_id] = {"status": "failed", "error": reason}
                logger.warning(f"[enrich-check] {word_text} — 拒绝写回: {reason}")
                if _event_queue is not None:
                    await _event_queue.put({
                        "type": "enrich_failed",
                        "word_id": word_id,
                        "word": word_text,
                        "reason": reason,
                    })
                _enriching_ids.pop(word_id, None)
                continue

            written = None
            with _write_lock:
                data = load_words()
                for w in data["words"]:
                    if w["id"] == word_id and w["word"] == word_text:
                        if phonetic and not w.get("phonetic"):
                            w["phonetic"] = phonetic
                        if definition and not w.get("definition"):
                            w["definition"] = definition
                        if example and not w.get("example"):
                            w["example"] = example
                        save_words(data)
                        written = {key: w[key] for key in ("phonetic", "definition", "example")}
                        break

            _enrich_batch_done += 1
            _enrich_jobs[word_id] = {"status": "ready" if written and written["definition"] else "idle"}
            if written is not None and _event_queue is not None:
                await _event_queue.put({
                    "type": "enriched",
                    "word_id": word_id,
                    **written,
                })
        except Exception as e:
            _enrich_jobs[word_id] = {"status": "failed", "error": "自动补全未完成，单词已保存，可以重试或手动编辑。"}
            # 外层保护:任何意外异常都不让 worker 死,记录后继续下一个
            logger.exception(f"[enrich-worker] UNCAUGHT EXCEPTION: {e}")
            import asyncio as _aio
            await _aio.sleep(1)
        finally:
            if _enrich_jobs.get(word_id, {}).get("status") == "processing":
                _enrich_jobs[word_id] = {"status": "idle"}
            _enriching_ids.pop(word_id, None)
            _enrich_current = None
            _enrich_queue.task_done()


def _enrich_post_check(word: str, phonetic: str, definition: str, example: str) -> tuple[bool, str]:
    """后处理校验 — 返回 (ok, reason)。

    三道闸:拼写(pyenchant) / 例句语种(langdetect) / 释义 POS 行头(纯正则)。
    任一失败 → 严格模式:不写回,清冷却,推 SSE enrich_failed 事件。
    库未装时优雅降级(log warning 后跳过该闸)。
    """
    import logging
    logger = logging.getLogger("uvicorn")

    # 1. 拼写 — 拦截 conffin/cublic/fivre/weav/undeter 这类
    # 词组(空格分隔)按分词查,避免 "bottle stoppers" 整串被误拒
    try:
        import enchant
        d = enchant.Dict("en_US")
        if " " in word:
            bad = [p for p in word.split() if not d.check(p)]
            if bad:
                return False, f"词组中分词拼写错 {bad}: {word!r}"
        else:
            if not d.check(word):
                return False, f"word 不在英语词典(疑似拼写错): {word!r}"
    except ImportError:
        pass  # pyenchant 未装 — 降级跳过
    except Exception as e:
        logger.warning(f"[enrich-check] {word} — 拼写检查异常: {type(e).__name__}: {e}")

    # 2. 例句含中文字符 → 拦截(algebra 中文例句这类)
    # 不做通用语种检测:langdetect 在 < 10 词的例句上误判率 30%+,
    # 会把短英文误判为 ro/af/so 等。直接看是否含中文更稳。
    if example and example.strip() and re.search(r"[一-鿿]", example):
        return False, f"例句包含中文字符: {example!r}"

    # 3. 释义每行以合法 POS 开头 — 拦截 divergent n. / intricate vt. / 冷门义项
    POS = {"vt.", "vi.", "n.", "adj.", "adv.", "prep.", "conj.", "pron."}
    for line in (definition or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if not any(line.startswith(p) for p in POS):
            return False, f"释义行不以 POS 开头: {line!r}"

    return True, ""


@app.put("/api/words/{word_id}")
def update_word(word_id: str, body: dict):
    with _write_lock:
        data = load_words()
        for w in data["words"]:
            if w["id"] == word_id:
                new_word = _text(body, "word", w["word"], limit=200)
                notebook_id = _text(body, "notebook_id", w.get("notebook_id", "default"), limit=200)
                if not notebook_id:
                    raise HTTPException(422, "请选择保存到的单词本")
                scoped = _book_words(data, notebook_id)
                if not new_word:
                    raise HTTPException(422, "单词不能为空")
                if any(other["id"] != word_id and other["word"].casefold() == new_word.casefold() for other in scoped):
                    raise HTTPException(409, "目标单词本中已存在该单词")
                w.update(word=new_word, notebook_id=notebook_id)
                for field in ("definition", "phonetic", "example"):
                    if field in body:
                        w[field] = _text(body, field)
                save_words(data)
                return {"word": w}
    raise HTTPException(status_code=404, detail="单词不存在")


@app.delete("/api/words/{word_id}")
def delete_word(word_id: str):
    with _write_lock:
        data = load_words()
        before = len(data["words"])
        data["words"] = [w for w in data["words"] if w["id"] != word_id]
        if len(data["words"]) == before:
            raise HTTPException(status_code=404, detail="单词不存在")
        save_words(data)
    return {"ok": True}


# ─── 导出辅助函数 ─────────────────────────────────────────

def _filter_words(data: dict, q: str, date: str, sort: str = "", letter: str = "") -> list:
    words = data["words"]
    if date:
        words = [w for w in words if w["created_at"].startswith(date)]
    if q:
        ql = q.lower()
        words = [w for w in words if ql in w["word"].lower() or ql in w["definition"].lower()]
    if letter:
        l = letter.lower()
        words = [w for w in words if w["word"].lower().startswith(l)]
    if sort == "alpha_asc":
        words = sorted(words, key=lambda w: w["word"].lower())
    elif sort == "alpha_desc":
        words = sorted(words, key=lambda w: w["word"].lower(), reverse=True)
    elif sort in ("created_desc", "created_asc"):
        def added_at(word):
            try:
                created = _parse_review_time(word.get("created_at", "")).astimezone(timezone.utc)
            except (ValueError, TypeError, OverflowError):
                created = datetime.min.replace(tzinfo=timezone.utc)
            return created, word["id"]
        words = sorted(words, key=added_at, reverse=sort == "created_desc")
    return words


# ─── 静态文件（生产模式）──────────────────────────────────
# 静态资源挂载必须在 catch-all 路由之前，否则 /assets/* 会被当 SPA 路由吞掉

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/")
async def serve_spa():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="前端未构建。请运行: cd frontend && npm run build",
        )
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/{full_path:path}")
async def serve_spa_fallback(full_path: str):
    """所有非 API/非静态资源路径回退到 SPA，支持浏览器刷新和直接导航"""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端未构建")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# ─── 网络工具 ─────────────────────────────────────────────

def get_lan_ip() -> str:
    """获取本机局域网 IP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return ""


# ─── 启动入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = "127.0.0.1"
    port = 1400
    lan_ip = get_lan_ip()

    print("═" * 52)
    print("  词汇笔记本  Vocabulary Notebook")
    print("═" * 52)
    print(f"  本地访问  →  http://localhost:{port}")
    print("═" * 52)
    print()

    uvicorn.run(app, host=host, port=port, log_level="warning")
