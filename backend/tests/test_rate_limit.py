import pytest


def test_rate_limit_blocks_after_threshold():
    from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceeded

    limiter = InMemoryRateLimiter(limit_per_day=2)

    first = limiter.check("127.0.0.1", llm_mode="live")
    second = limiter.check("127.0.0.1", llm_mode="live")

    assert first.allowed is True
    assert second.allowed is True
    assert second.remaining == 0

    with pytest.raises(RateLimitExceeded):
        limiter.check("127.0.0.1", llm_mode="live")


def test_rate_limit_returns_structured_error():
    from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceeded

    limiter = InMemoryRateLimiter(limit_per_day=0)

    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("session-1", llm_mode="live")

    detail = exc_info.value.to_detail()

    assert detail == {
        "error": "rate_limit_exceeded",
        "message": "Daily live LLM call limit exceeded.",
        "limit": 0,
        "remaining": 0,
    }


def test_replay_calls_do_not_count_toward_rate_or_cost():
    from app.core.rate_limit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(limit_per_day=1)

    replay_decision = limiter.check("127.0.0.1", llm_mode="replay")
    live_decision = limiter.check("127.0.0.1", llm_mode="live")

    assert replay_decision.counted is False
    assert replay_decision.remaining == 1
    assert live_decision.counted is True
    assert live_decision.remaining == 0
    assert limiter.usage_for("127.0.0.1") == 1
