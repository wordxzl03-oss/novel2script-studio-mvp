from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LLMMode = Literal["live", "record", "replay"]


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    counted: bool
    limit: int
    remaining: int


class RateLimitExceeded(RuntimeError):
    def __init__(self, *, limit: int, remaining: int = 0) -> None:
        super().__init__("Daily live LLM call limit exceeded.")
        self.limit = limit
        self.remaining = remaining

    def to_detail(self) -> dict:
        return {
            "error": "rate_limit_exceeded",
            "message": "Daily live LLM call limit exceeded.",
            "limit": self.limit,
            "remaining": self.remaining,
        }


class InMemoryRateLimiter:
    def __init__(self, *, limit_per_day: int) -> None:
        self.limit_per_day = max(0, limit_per_day)
        self._live_usage_by_subject: dict[str, int] = {}

    def check(self, subject: str, *, llm_mode: LLMMode | str) -> RateLimitDecision:
        if llm_mode != "live":
            return RateLimitDecision(
                allowed=True,
                counted=False,
                limit=self.limit_per_day,
                remaining=self._remaining(subject),
            )

        used = self._live_usage_by_subject.get(subject, 0)
        if used >= self.limit_per_day:
            raise RateLimitExceeded(limit=self.limit_per_day, remaining=0)

        used += 1
        self._live_usage_by_subject[subject] = used
        return RateLimitDecision(
            allowed=True,
            counted=True,
            limit=self.limit_per_day,
            remaining=max(0, self.limit_per_day - used),
        )

    def usage_for(self, subject: str) -> int:
        return self._live_usage_by_subject.get(subject, 0)

    def _remaining(self, subject: str) -> int:
        return max(0, self.limit_per_day - self._live_usage_by_subject.get(subject, 0))
