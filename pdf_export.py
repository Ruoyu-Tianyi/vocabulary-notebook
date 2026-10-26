"""词汇表 PDF 排版及 Unicode 字体校验，与 Web/API 层独立。"""
import html as html_mod
import string
from pathlib import Path
from typing import Optional

from fontTools.ttLib import TTFont, TTLibError
from fpdf import FPDF

from compat import getenv


CJK_FONT_ENV = "VOCOVE_CJK_FONT"
_MACOS_CJK_FONT = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
DEFAULT_CJK_FONT_PATH = str(_MACOS_CJK_FONT) if _MACOS_CJK_FONT.is_file() else None


class PdfExportError(ValueError):
    """导出前向调用方明确报告字体或文本无法完整呈现的问题。"""


def _font_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.suffix.lower() not in (".ttf", ".otf"):
        raise PdfExportError(f"{CJK_FONT_ENV} 需指向静态 .ttf 或 .otf 字体，不支持字体集合或可变字体")
    if not path.is_file():
        raise PdfExportError(f"{CJK_FONT_ENV} 指定的字体文件不存在或不可读取，请检查路径")
    return path


def resolve_cjk_font(default_path: Optional[str] = DEFAULT_CJK_FONT_PATH) -> Optional[str]:
    """显式配置优先；没有 Unicode 字体时仍允许内置字体能覆盖的内容。"""
    configured = getenv(CJK_FONT_ENV, "").strip()
    if configured:
        return str(_font_path(configured))
    if default_path and Path(default_path).is_file():
        return str(_font_path(default_path))
    return None


def _export_text(words: list[dict]) -> str:
    return "\n".join(html_mod.unescape(item.get(key, "")).strip()
                     for item in words for key in ("word", "phonetic", "definition", "example"))


def _validate_font(words: list[dict], use_cjk: bool, font_path: Optional[str]) -> None:
    text = _export_text(words)
    if not use_cjk:
        try:
            text.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise PdfExportError(f"PDF 包含中文、音标或其他 Unicode 字符，请将 {CJK_FONT_ENV} 设置为支持这些字符的静态 TTF/OTF 字体路径后重试；也可先导出 CSV 或 JSON") from exc
        return
    if not font_path:
        raise PdfExportError(f"未找到 Unicode 字体，请配置 {CJK_FONT_ENV}")
    path = _font_path(font_path)
    try:
        with TTFont(path, lazy=True) as font:
            if "fvar" in font:
                raise PdfExportError(f"{CJK_FONT_ENV} 不支持可变字体，请选择静态 TTF/OTF 字体")
            cmap = font.getBestCmap() or {}
            required = text + string.printable + "·导出日期共个单词"
            missing = {char for char in required if not char.isspace() and ord(char) not in cmap}
    except PdfExportError:
        raise
    except (TTLibError, OSError, KeyError, TypeError, ValueError) as exc:
        raise PdfExportError(f"无法读取 {CJK_FONT_ENV} 字体，请选择有效的静态 TTF/OTF 字体") from exc
    if missing:
        sample = "、".join(sorted(missing)[:6])
        raise PdfExportError(f"PDF 字体缺少所需字符（例如：{sample}），请为 {CJK_FONT_ENV} 选择覆盖中文与音标的字体")


def _build_pdf(words: list[dict], today: str, use_cjk: bool, cjk_font_path: Optional[str]) -> bytes:
    """渲染 Vocove PDF：密集表格布局，~20 词/页。

    设计: Scholar's Compact
    - 顶栏: 标题 + 日期 + 计数 + 双线分割
    - 表头: 序号 / 单词 + 音标 / 释义 / 例句
    - 行: 斑马纹（极淡米色），超细分隔线
    - 字: 单词 Times Bold, 音标 Courier Italic, 释义 Helvetica, 例句 Italic
    - 底栏: 页码 + 总数
    """

    _validate_font(words, use_cjk, cjk_font_path)

    pdf = FPDF("P", "mm", "A4")
    if use_cjk:
        for style in ("", "B", "I"):
            pdf.add_font("CJK", style, cjk_font_path)
    pdf.alias_nb_pages()

    # ── 排版常量 ──
    M_L, M_R, M_T, M_B = 16, 16, 14, 16
    pdf.set_margins(M_L, M_T, M_R)
    pdf.set_auto_page_break(False)  # 手动控制分页

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
        title = "Vocove"
        pdf.cell(80, 6.5, title)
        # 副标题（中文）
        if use_cjk:
            pdf.set_xy(M_L, y + 6.5)
            pdf.set_font(sans, "", 8.5)
            pdf.set_text_color(*C_META)
            pdf.cell(80, 4, "Vocove · 导 出")
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

        lines_def = _wrap_lines(definition, COL_DEF_W - 3, 8.5)
        lines_ex = _wrap_lines(f'"{example}"', COL_EX_W - 3, 7.5, "I") if example else []
        n_def, n_ex = len(lines_def), len(lines_ex)
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
        cy = y + ROW_PAD_TOP
        for ln in lines_def:
            pdf.set_xy(COL_X["def"] + 1.5, cy)
            pdf.cell(COL_DEF_W - 3, LH_DEF, ln)
            cy += LH_DEF

        # 例句（缩进 + 斜体）
        if example and n_ex > 0:
            cy += 0.5
            pdf.set_font(sans, "I", 7.5)
            pdf.set_text_color(*C_EX)
            for ln in lines_ex:
                pdf.set_xy(COL_X["ex"] + 1.5, cy)
                pdf.cell(COL_EX_W - 3, LH_EX, ln)
                cy += LH_EX

        # 行底分割线
        pdf.set_draw_color(*C_RULE_LITE)
        pdf.set_line_width(0.12)
        pdf.line(M_L, y + row_h, M_L + CONTENT_W, y + row_h)
        pdf.set_line_width(0.15)

        return y + row_h

    def _wrap_lines(text: str, max_w_mm: float, font_size_pt: float, style: str = "") -> list[str]:
        # 与实际绘制共用字体度量，避免按字符估宽而截断或溢出列宽。
        if not text:
            return [""]
        pdf.set_font(sans, style, font_size_pt)
        return pdf.multi_cell(max_w_mm, font_size_pt * 0.3528, text, dry_run=True, output="LINES")

    # ── 页脚 ──
    def draw_footer():
        pdf.set_xy(M_L, pdf.h - M_B + 4)
        pdf.set_font(sans if use_cjk else "Helvetica", "", 7.5)
        pdf.set_text_color(*C_META)
        left = "Vocove"
        right = f"{pdf.page_no()} / {{nb}}"
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
        # 使用与绘制相同的换行结果，避免按估算高度截掉长释义的尾行。
        definition = html_mod.unescape(item.get("definition", "")).strip()
        example = html_mod.unescape(item.get("example", "")).strip()
        n_def_est = len(_wrap_lines(definition, COL_DEF_W - 3, 8.5))
        n_ex_est = len(_wrap_lines(f'"{example}"', COL_EX_W - 3, 7.5, "I")) if example else 0
        text_h_est = n_def_est * LH_DEF + (n_ex_est * LH_EX + 1.0 if example else 0)
        row_h_est = max(MIN_ROW_H, ROW_PAD_TOP + text_h_est + ROW_PAD_BOT)
        if row_h_est > TABLE_BOTTOM - (M_T + TABLE_TOP_OFFSET - 0.5 + COL_HEADER_H):
            raise PdfExportError("单条词汇内容超过 PDF 单页容量，请缩短释义/例句或改用 CSV、JSON 导出")

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
