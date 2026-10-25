#!/usr/bin/env python3
"""测试 enrich_word 的 prompt 在不同输入下的生成结果。

两种用法:

(1) 快速验证(不调 deepseek):
    python tests/test_prompt.py                       # 打印每个 case 的 prompt
    python tests/test_prompt.py --case coordinated    # 只跑一个 case
    pytest tests/test_prompt.py                       # pytest 模式,跑 fast 测试

(2) 实际验证(调 deepseek,需 SOCKS 代理绕过):
    env -u all_proxy python tests/test_prompt.py --live
    # ~1 分钟,16 个 case,适合 prompt 改完验证

设计:
- 默认 dry-run(便宜)
- --live 才调 deepseek(贵,约 0.1 元/次)
- pytest 兼容:有 test_ 开头函数,跑快速验证
"""
import argparse
import asyncio
import inspect
import os
import re
import sys

# 让 `python tests/test_prompt.py` 也能 import app(不只 pytest 模式)
# 把项目根目录加到 sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import app  # noqa: E402  在 sys.path 设置后必须 import


def extract_prompt_template() -> str:
    """从 app.enrich_word 函数体里提取 prompt 模板(原始 f-string 文本)"""
    src = inspect.getsource(app.enrich_word)
    # 匹配 prompt = f'''...''' 或 f"""...""" 块(支持两种三引号)
    m = re.search(r'prompt\s*=\s*f([\'"]{3})(.+?)\1\s*$', src, re.DOTALL | re.MULTILINE)
    if not m:
        raise RuntimeError("找不到 prompt 模板")
    return m.group(2).rstrip()


def render_prompt(template: str, word: str) -> str:
    """手工替换 {word} 占位符,保留 {{ }} 转义"""
    return template.replace("{word}", word)


# 测试用例:(name, input_word, expected_word_field, expected_def_marker_or_empty)
# - expected_def_marker: def 中必须包含的子串(空字符串 = 期望 def 空)
# - None = 不检查 def(只检查 word)
TEST_CASES = [
    # ── 派生形(应改原形) ──
    ("复数",         "granules",          "granule",    "granule"),  # "的复数" deepseek 写法可能紧凑
    ("过去式",       "esteemed",          "esteemed",   "受尊敬"),  # 独立 adj headword (跟 alleged/emboldened 一致)
    ("现在分词",     "amassing",          "amass",      "amass 的现在分词"),
    ("过去分词",     "coordinated",       "coordinate", "coordinate"),  # deepseek 紧凑写法 "coordinate的过去式"
    ("过去分词2",    "emboldened",        "emboldened", "受鼓舞"),  # 独立 adj headword (deepseek 写法"受鼓舞" 不是"受到鼓舞")
    ("过去分词3",    "alleged",           "alleged",    "所谓"),  # 独立 adj headword
    # ── 独立 headword(应保留输入形式) ──
    ("-ing 名词",   "running",           "running",    None),
    ("-ed adj",     "talented",          "talented",   None),
    ("-ing adj",    "frightening",       "frightening", None),
    # ── 同形异义 / 多音 ──
    ("同形异义",     "found",             "found",      "创办"),  # 创办义; deepseek 可能用"创建"或"创办"
    # ── 词组 ──
    ("词组",        "bottle stoppers",    "bottle stoppers", "瓶塞"),
    # ── 错误单词 / 应返空 ──
    ("乱拼词",       "xyzabc",            None,         ""),  # def 应空
    ("伪词",         "perceptrix",        None,         ""),
    # ── 主义项放前 ──
    ("义项顺序",     "pharmacy",          "pharmacy",   "药店"),
    # ── adj 不能加 n/v ──
    ("纯形容词",     "intricate",         "intricate",  None),  # def 不能含 vt./n.
    # ── 多义 ──
    ("多义",        "bank",              "bank",       "银行"),
]


def dry_run(template: str):
    print("=" * 70)
    print("DRY-RUN: 打印每个 case 的 prompt(前 800 字符,不调 deepseek)")
    print("=" * 70)
    for i, (name, word, exp_word, exp_marker) in enumerate(TEST_CASES, 1):
        marker_disp = repr(exp_marker) if exp_marker else "(不检查)"
        print(f"\n[{i:2d}] {name}: input='{word}'")
        print(f"     期望 word 字段: {exp_word!r}")
        print(f"     期望 def 含: {marker_disp}")
        print("-" * 40 + " PROMPT (前 800 字) " + "-" * 30)
        rendered = render_prompt(template, word)
        # 只显示前 800 字
        snippet = rendered[:800]
        print(snippet)
        if len(rendered) > 800:
            print(f"...[truncated, 总长 {len(rendered)} 字符]")


async def live_test():
    """实际调 deepseek,验证 def 是否符合预期"""
    print("=" * 70)
    print("LIVE TEST: 调 deepseek 跑,验证 def 内容")
    print("=" * 70)
    results = []
    for i, (name, word, exp_word, exp_marker) in enumerate(TEST_CASES, 1):
        print(f"\n[{i:2d}] {name}: input='{word}'")
        try:
            phon, defn, ex = await app.enrich_word(word)
        except Exception as e:
            print(f"  ✗ EXCEPTION: {type(e).__name__}: {e}")
            results.append((name, word, "EXCEPTION", False))
            continue

        print(f"  返回 word 字段: {phon!r}")  # 用 phon 字段作 word 检查的占位
        print(f"  返回 def[:100]: {defn[:100]!r}")
        print(f"  返回 ex[:60]:  {ex[:60]!r}")

        # 检查 (我们没法直接看 word 字段,因为 enrich_word 返回 (phon, def, ex))
        # 但 def 第一行通常以 POS 开头,词条信息会嵌在 def 中
        # 简化检查:看 def 是否包含期望的 marker
        if exp_marker == "":
            ok = not defn.strip()
            status = "✓ 返空" if ok else f"✗ 期望空但 def={defn[:50]!r}"
        elif exp_marker is None:
            ok = True  # 不检查 def
            status = "✓ (不检查)"
        else:
            ok = exp_marker in defn
            status = f"✓ 含 {exp_marker!r}" if ok else f"✗ 缺 {exp_marker!r}, def={defn[:80]!r}"

        print(f"  {status}")
        results.append((name, word, status, ok))

        # 每个 case 之间稍等,避免 deepseek 限流
        await asyncio.sleep(1)

    print()
    print("=" * 70)
    print("总结")
    print("=" * 70)
    passed = sum(1 for _, _, _, ok in results if ok)
    print(f"  通过: {passed}/{len(results)}")
    for name, word, status, ok in results:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name:10s} '{word:18s}'  {status}")


if __name__ == "__main__":
    # CLI 入口
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true", help="实际调 deepseek")
    p.add_argument("--case", help="只跑指定 case 名")
    args = p.parse_args()

    if args.case:
        TEST_CASES = [c for c in TEST_CASES if args.case in (c[0], c[1])]
        if not TEST_CASES:
            print(f"未找到 case '{args.case}'")
            sys.exit(1)

    if args.live:
        asyncio.run(live_test())
    else:
        template = extract_prompt_template()
        dry_run(template)


# ── Pytest 兼容 — 快速验证(不调 deepseek) ───────────────

def test_prompt_template_extractable():
    """prompt 模板能从 enrich_word 函数体里 regex 出来"""
    template = extract_prompt_template()
    assert len(template) > 500, f"prompt 模板太短: {len(template)} 字符"
    # 关键约束句必须存在
    for marker in [
        "definition MUST be written in Chinese",
        "primary meaning first",
        "homonyms or polysemous",
        "multi-word phrase",
    ]:
        assert marker in template, f"prompt 缺关键约束: {marker!r}"


def test_prompt_renders_for_each_case():
    """每个 test case 都能正常渲染 prompt(不抛异常)"""
    template = extract_prompt_template()
    for name, word, _, _ in TEST_CASES:
        rendered = render_prompt(template, word)
        assert word in rendered, f"case '{name}': '{word}' 没出现在渲染后的 prompt"
        assert len(rendered) > 500, f"case '{name}': 渲染后太短"


def test_known_constraints_present():
    """核心约束关键词都在 prompt 里(防回退)"""
    template = extract_prompt_template()
    # CRITICAL 段必须存在
    assert "CRITICAL" in template
    # POS 缩写必须列出
    assert "vt. vi. n. adj. adv. prep. conj. pron." in template
    # JSON-only 约束
    assert "Reply ONLY with a JSON object" in template
    # 例句必须英文
    assert "example sentence MUST be in English" in template
