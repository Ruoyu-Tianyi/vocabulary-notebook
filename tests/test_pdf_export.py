"""PDF 字体检查与生成使用临时字体，不依赖 CI 的系统字体或真实词库。"""
import string
import re
import zlib
from contextlib import nullcontext

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import app
import pdf_export
from tests.local_client import TestClient


def word(**changes):
    return {"id": "pdf-test", "notebook_id": "default", "word": "Contract", "phonetic": "",
            "definition": "n. an agreement", "example": "They signed the contract.",
            "created_at": "2026-10-25T10:00:00+08:00", **changes}


def make_font(path, characters):
    """生成最小静态 TTF，验证字体读取/嵌入链路；不假借操作系统的字体覆盖。"""
    characters = sorted(set(characters) - {"\n", "\r", "\t", "\v", "\f"})
    cmap = {ord(char): f"uni{ord(char):04X}" for char in characters}
    glyph_order = [".notdef", *cmap.values()]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    glyphs = {}
    for glyph in glyph_order:
        pen = TTGlyphPen(None)
        if glyph != "uni0020":
            pen.moveTo((50, 0))
            pen.lineTo((550, 0))
            pen.lineTo((550, 700))
            pen.lineTo((50, 700))
            pen.closePath()
        glyphs[glyph] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({glyph: (600, 50) for glyph in glyph_order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupNameTable({"familyName": "Vocove PDF Test", "styleName": "Regular",
                            "uniqueFontIdentifier": "VocovePdfTest-Regular", "fullName": "Vocove PDF Test Regular",
                            "psName": "VocovePdfTest-Regular", "version": "Version 1.0"})
    builder.setupPost()
    builder.save(path)
    return str(path)


@pytest.fixture
def unicode_font(tmp_path):
    characters = string.printable + "·Vocove导出日期共个单词合同əæɒˈ"
    return make_font(tmp_path / "test-unicode.ttf", characters)


def test_explicit_font_configuration_overrides_default(unicode_font, monkeypatch):
    monkeypatch.setenv(pdf_export.CJK_FONT_ENV, unicode_font)
    assert pdf_export.resolve_cjk_font("missing-default.ttf") == unicode_font


def test_missing_default_allows_latin1_export(monkeypatch):
    monkeypatch.delenv(pdf_export.CJK_FONT_ENV, raising=False)
    assert pdf_export.resolve_cjk_font("missing-default.ttf") is None
    result = pdf_export._build_pdf([word(word="Café")], "2026-10-25", False, None)
    assert result.startswith(b"%PDF-")
    assert b"/Type /Page" in result


@pytest.mark.parametrize("filename", ["missing.ttf", "collection.ttc", "variable.woff2"])
def test_invalid_explicit_font_never_silently_falls_back(tmp_path, monkeypatch, filename):
    monkeypatch.setenv(pdf_export.CJK_FONT_ENV, str(tmp_path / filename))
    with pytest.raises(pdf_export.PdfExportError, match="VOCOVE_CJK_FONT"):
        pdf_export.resolve_cjk_font()


@pytest.mark.parametrize("changes", [
    {"definition": "n. 合同"}, {"phonetic": "/ˈkɒntrækt/"},
    {"definition": "n. &#21512;&#21516;"}, {"example": "“Contract”"},
])
def test_unicode_content_requires_font_instead_of_losing_characters(changes):
    with pytest.raises(pdf_export.PdfExportError, match="VOCOVE_CJK_FONT"):
        pdf_export._build_pdf([word(**changes)], "2026-10-25", False, None)


def test_real_unicode_font_is_embedded_in_generated_pdf(unicode_font, caplog):
    result = pdf_export._build_pdf([word(definition="n. 合同", phonetic="/ˈkɒntrækt/")],
                                   "2026-10-25", True, unicode_font)
    assert result.startswith(b"%PDF-")
    assert b"/ToUnicode" in result
    assert "missing" not in caplog.text.lower()


def test_font_without_required_glyphs_is_rejected(tmp_path):
    path = make_font(tmp_path / "latin-only.ttf", string.printable)
    with pytest.raises(pdf_export.PdfExportError, match="缺少所需字符"):
        pdf_export._build_pdf([word(definition="n. 合同")], "2026-10-25", True, path)


def test_corrupt_font_has_actionable_error(tmp_path):
    path = tmp_path / "broken.ttf"
    path.write_bytes(b"not a font")
    with pytest.raises(pdf_export.PdfExportError, match="有效的静态 TTF/OTF"):
        pdf_export._build_pdf([word()], "2026-10-25", True, str(path))


def test_variable_font_is_rejected_explicitly(unicode_font, monkeypatch):
    monkeypatch.setattr(pdf_export, "TTFont", lambda *args, **kwargs: nullcontext({"fvar": object()}))
    with pytest.raises(pdf_export.PdfExportError, match="不支持可变字体"):
        pdf_export._build_pdf([word()], "2026-10-25", True, unicode_font)


def test_total_page_count_is_consistent_on_earlier_pages():
    result = pdf_export._build_pdf([word(word=f"Contract {index}") for index in range(45)],
                                   "2026-10-25", False, None)
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", result, re.DOTALL)
    content = b"\n".join(zlib.decompress(stream) for stream in streams)
    content = content.replace(b") Tj (", b"")
    page_numbers = re.findall(rb"\((\d+) / (\d+)\)", content)
    assert len(page_numbers) > 1
    assert [int(page) for page, _ in page_numbers] == list(range(1, len(page_numbers) + 1))
    assert {int(total) for _, total in page_numbers} == {len(page_numbers)}


def test_long_wrapped_content_keeps_final_lines():
    definition = "n. " + "extraordinary " * 26 + "DEFINITION_END"
    example = "extraordinary " * 12 + "EXAMPLE_END"
    result = pdf_export._build_pdf([word(definition=definition, example=example)],
                                   "2026-10-25", False, None)
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", result, re.DOTALL)
    content = b"\n".join(zlib.decompress(stream) for stream in streams)
    assert b"DEFINITION_END" in content
    assert b"EXAMPLE_END" in content


def test_single_row_beyond_page_capacity_fails_instead_of_clipping():
    with pytest.raises(pdf_export.PdfExportError, match="单页容量"):
        pdf_export._build_pdf([word(definition="n. definition\n" * 200)], "2026-10-25", False, None)


def test_pdf_api_returns_font_error_without_reading_or_writing_live_data(monkeypatch):
    monkeypatch.delenv(pdf_export.CJK_FONT_ENV, raising=False)
    monkeypatch.setattr(app, "_CJK_FONT_PATH", None)
    monkeypatch.setattr(app, "load_words", lambda: {"words": [word(definition="n. 合同")]})
    result = TestClient(app.app).get("/api/words/export", params={"format": "pdf"})
    assert result.status_code == 422
    assert "VOCOVE_CJK_FONT" in result.json()["detail"]


def test_pdf_api_uses_explicit_font_and_preserves_attachment(unicode_font, monkeypatch):
    monkeypatch.setenv(pdf_export.CJK_FONT_ENV, unicode_font)
    monkeypatch.setattr(app, "load_words", lambda: {"words": [word(definition="n. 合同")]})
    result = TestClient(app.app).get("/api/words/export", params={"format": "pdf"})
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/pdf"
    assert "attachment; filename=vocove-" in result.headers["content-disposition"]
    assert result.content.startswith(b"%PDF-")
