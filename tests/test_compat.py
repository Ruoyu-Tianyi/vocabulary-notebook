"""历史环境配置仍可启动；显式新配置优先，不意外回退到旧路径或凭据。"""
import pytest

from compat import getenv


@pytest.mark.parametrize("current,previous", [
    ("VOCOVE_DATA_FILE", "VOCAB_DATA_FILE"),
    ("VOCOVE_DESKTOP_TOKEN", "VOCAB_DESKTOP_TOKEN"),
    ("VOCOVE_CJK_FONT", "VOCABULARY_CJK_FONT"),
])
def test_previous_environment_is_used_only_when_new_name_is_absent(monkeypatch, current, previous):
    monkeypatch.delenv(current, raising=False)
    monkeypatch.delenv(previous, raising=False)
    assert getenv(current, "default") == "default"
    monkeypatch.setenv(previous, "previous-value")
    assert getenv(current) == "previous-value"
    monkeypatch.setenv(current, "current-value")
    assert getenv(current) == "current-value"
    monkeypatch.setenv(current, "")
    assert getenv(current) == ""


def test_unrelated_environment_names_are_not_aliased():
    with pytest.raises(ValueError, match="VOCOVE_"):
        getenv("UNRELATED_SETTING")
