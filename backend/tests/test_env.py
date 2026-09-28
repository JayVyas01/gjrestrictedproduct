import pytest

from config import env


def test_required_returns_trimmed_value(monkeypatch):
    monkeypatch.setenv("GJ_SAMPLE", " value ")
    assert env.required("GJ_SAMPLE") == "value"


def test_required_fails_fast_when_missing(monkeypatch):
    monkeypatch.delenv("GJ_SAMPLE", raising=False)
    with pytest.raises(env.MissingSetting, match="GJ_SAMPLE"):
        env.required("GJ_SAMPLE")


def test_required_fails_fast_when_blank(monkeypatch):
    monkeypatch.setenv("GJ_SAMPLE", "   ")
    with pytest.raises(env.MissingSetting):
        env.required("GJ_SAMPLE")


def test_optional_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("GJ_SAMPLE", raising=False)
    assert env.optional("GJ_SAMPLE", "fallback") == "fallback"


def test_flag_parses_truthy_and_falsy(monkeypatch):
    monkeypatch.setenv("GJ_FLAG", "True")
    assert env.flag("GJ_FLAG") is True
    monkeypatch.setenv("GJ_FLAG", "0")
    assert env.flag("GJ_FLAG") is False


def test_flag_default_when_unset(monkeypatch):
    monkeypatch.delenv("GJ_FLAG", raising=False)
    assert env.flag("GJ_FLAG", default=True) is True


def test_listed_splits_and_trims(monkeypatch):
    monkeypatch.setenv("GJ_LIST", "a.example, b.example ,")
    assert env.listed("GJ_LIST") == ["a.example", "b.example"]
