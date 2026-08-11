import dataclasses

from app import config
from app.router import Decision, route


def _cfg(auto=0.85, review=0.45):
    return dataclasses.replace(config.load(), auto_threshold=auto, review_threshold=review)


def test_high_confidence_goes_auto():
    decision, reason = route(0.9, _cfg())
    assert decision is Decision.AUTO
    assert "0.90" in reason


def test_grey_zone_goes_to_review():
    decision, _ = route(0.6, _cfg())
    assert decision is Decision.REVIEW


def test_low_confidence_is_rejected():
    decision, _ = route(0.1, _cfg())
    assert decision is Decision.REJECT


def test_irreversible_action_never_auto_even_at_full_confidence():
    decision, reason = route(1.0, _cfg(), irreversible=True)
    assert decision is Decision.REVIEW
    assert "человек" in reason


def test_thresholds_come_from_env(monkeypatch):
    monkeypatch.setenv("AUTO_THRESHOLD", "0.99")
    assert config.load().auto_threshold == 0.99
