import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: float


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class RateLimiter:
    """An in-memory token bucket per API key.

    Each bucket holds up to `capacity` tokens and refills at `refill_per_second`.
    Every request spends one token. An empty bucket means the request is refused.

    Limitation: buckets live in this process's memory, so limits reset on restart
    and are not shared between several running copies of the app.
    """

    def __init__(
        self,
        capacity: int,
        refill_per_second: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second must be positive")
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._clock = clock
        self._buckets: dict[uuid.UUID, _Bucket] = {}
        # Requests run in several threads at once, so bucket updates must not interleave.
        self._lock = threading.Lock()

    @classmethod
    def per_minute(
        cls, requests: int, clock: Callable[[], float] = time.monotonic
    ) -> "RateLimiter":
        return cls(capacity=requests, refill_per_second=requests / 60, clock=clock)

    def check(self, key_id: uuid.UUID) -> RateLimitDecision:
        """Spend one token for this key if available, and say whether the request may go ahead."""
        with self._lock:
            now = self._clock()
            bucket = self._buckets.get(key_id)
            if bucket is None:
                bucket = _Bucket(tokens=float(self._capacity), updated_at=now)
                self._buckets[key_id] = bucket

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(
                float(self._capacity), bucket.tokens + elapsed * self._refill_per_second
            )
            bucket.updated_at = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return RateLimitDecision(
                    allowed=True,
                    limit=self._capacity,
                    remaining=int(bucket.tokens),
                    retry_after_seconds=0.0,
                )

            wait = (1.0 - bucket.tokens) / self._refill_per_second
            return RateLimitDecision(
                allowed=False, limit=self._capacity, remaining=0, retry_after_seconds=wait
            )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency. Cached so every request shares the same buckets."""
    return RateLimiter.per_minute(get_settings().rate_limit_per_minute)