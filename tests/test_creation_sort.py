"""Creation-time ordering does not mutate stored vocabulary or review progress."""
import pytest
from tests.local_client import TestClient
import app


def word(word_id, created_at, **extra):
    return {"id": word_id, "word": word_id, "definition": "n. 测试", "phonetic": "",
            "example": "This is a test.", "created_at": created_at, **extra}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    return app.DATA_FILE


def test_time_order_matches_pagination_and_json_csv_exports_without_rewriting(isolated):
    app.save_words({"words": [word("older", "2026-10-18T09:00:00+08:00", srs={"reps": 3}),
                              word("newest", "2026-10-18T03:00:00Z"),
                              word("middle", "2026-10-18T10:00:00")]})
    original = isolated.read_bytes()
    client = TestClient(app.app)
    result = client.get("/api/words", params={"sort": "created_desc", "size": 2}).json()
    assert [w["id"] for w in result["words"]] == ["newest", "middle"]
    result = client.get("/api/words", params={"sort": "created_desc", "size": 2, "page": 2}).json()
    assert [w["id"] for w in result["words"]] == ["older"]
    exported = client.get("/api/words/export", params={"sort": "created_desc"}).json()
    assert [w["id"] for w in exported["words"]] == ["newest", "middle", "older"]
    csv = client.get("/api/words/export", params={"sort": "created_desc", "format": "csv"}).text
    assert csv.index("newest") < csv.index("middle") < csv.index("older")
    result = client.get("/api/words", params={"sort": "created_asc", "q": "test"}).json()
    assert result["words"] == []
    result = client.get("/api/words", params={"sort": "created_asc"}).json()
    assert [w["id"] for w in result["words"]] == ["older", "middle", "newest"]
    assert isolated.read_bytes() == original


def test_legacy_invalid_dates_and_equal_instants_have_stable_order(isolated):
    data = {"words": [word("z", "2026-10-18T10:00:00+08:00"), word("a", "2026-10-18T02:00:00Z"),
                      word("invalid", "bad-date"), word("missing", None)]}
    assert [w["id"] for w in app._filter_words(data, "", "", "created_desc")] == ["z", "a", "missing", "invalid"]
    assert [w["id"] for w in app._filter_words(data, "", "", "alpha_asc")] == ["a", "invalid", "missing", "z"]
    assert app._filter_words(data, "", "") == data["words"]


@pytest.mark.parametrize("value", ["2026-10-18T03:00:00Z", "2026-10-18T03:00:00.123456Z"])
def test_utc_suffix_matches_explicit_offset_on_older_python(value):
    assert app._parse_review_time(value) == app._parse_review_time(value[:-1] + "+00:00")
