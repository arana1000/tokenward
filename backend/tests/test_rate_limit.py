import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import RequestLog
from app.rate_limit import RateLimiter, get_rate_limiter
from app.request_logs import Outcome

client = TestClient(app)


class FakeClock:
    """A clock the test controls, so nothing has to actually wait."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_requests_up_to_capacity_then_blocks() -> None:
    limiter = RateLimiter(capacity=3, refill_per_second=1.0, clock=FakeClock())
    key = uuid.uuid4()

    results = [limiter.check(key).allowed for _ in range(4)]

    assert results == [True, True, True, False]


def test_tokens_refill_over_time() -> None:
    clock = FakeClock()
    limiter = RateLimiter(capacity=2, refill_per_second=1.0, clock=clock)
    key = uuid.uuid4()
    limiter.check(key)
    limiter.check(key)
    assert limiter.check(key).allowed is False

    clock.advance(1.0)

    assert limiter.check(key).allowed is True
    assert limiter.check(key).allowed is False


def test_retry_after_says_how_long_to_wait() -> None:
    limiter = RateLimiter(capacity=1, refill_per_second=0.5, clock=FakeClock())
    key = uuid.uuid4()
    limiter.check(key)

    decision = limiter.check(key)

    assert decision.allowed is False
    assert decision.retry_after_seconds == pytest.approx(2.0)


def test_each_key_has_its_own_bucket() -> None:
    limiter = RateLimiter(capacity=1, refill_per_second=1.0, clock=FakeClock())
    first, second = uuid.uuid4(), uuid.uuid4()

    assert limiter.check(first).allowed is True
    assert limiter.check(first).allowed is False
    assert limiter.check(second).allowed is True


def test_bucket_never_holds_more_than_capacity() -> None:
    clock = FakeClock()
    limiter = RateLimiter(capacity=3, refill_per_second=1.0, clock=clock)
    key = uuid.uuid4()
    limiter.check(key)

    clock.advance(1000.0)

    results = [limiter.check(key).allowed for _ in range(4)]
    assert results == [True, True, True, False]


def test_remaining_counts_down() -> None:
    limiter = RateLimiter(capacity=3, refill_per_second=1.0, clock=FakeClock())
    key = uuid.uuid4()

    remaining = [limiter.check(key).remaining for _ in range(4)]

    assert remaining == [2, 1, 0, 0]


def test_per_minute_limit() -> None:
    limiter = RateLimiter.per_minute(60, clock=FakeClock())
    key = uuid.uuid4()

    allowed = [limiter.check(key).allowed for _ in range(60)]
    blocked = limiter.check(key)

    assert all(allowed)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == pytest.approx(1.0)


def test_concurrent_requests_never_exceed_capacity() -> None:
    limiter = RateLimiter(capacity=100, refill_per_second=1.0, clock=FakeClock())
    key = uuid.uuid4()

    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(pool.map(lambda _: limiter.check(key), range(500)))

    assert sum(decision.allowed for decision in decisions) == 100


# The tests below go through the real endpoint with a limit of 2 requests.


@pytest.fixture
def tight_limiter() -> Iterator[RateLimiter]:
    limiter = RateLimiter(capacity=2, refill_per_second=1.0, clock=FakeClock())
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield limiter
    app.dependency_overrides.pop(get_rate_limiter, None)


def chat_body() -> dict[str, Any]:
    return {"model": "mock-1", "messages": [{"role": "user", "content": "Hello there"}]}


def test_chat_returns_429_when_limit_exceeded(
    tight_limiter: RateLimiter, auth_headers: dict[str, str]
) -> None:
    first = client.post("/v1/chat", json=chat_body(), headers=auth_headers)
    second = client.post("/v1/chat", json=chat_body(), headers=auth_headers)
    third = client.post("/v1/chat", json=chat_body(), headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json() == {"detail": "Rate limit exceeded"}
    assert third.headers["retry-after"] == "1"


def test_rate_limited_request_is_logged(
    tight_limiter: RateLimiter, api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key
    for _ in range(3):
        client.post("/v1/chat", json=chat_body(), headers=auth_headers)

    with SessionLocal() as session:
        statement = select(RequestLog).where(
            RequestLog.api_key_id == key_id,
            RequestLog.outcome == Outcome.RATE_LIMITED.value,
        )
        [log] = list(session.scalars(statement))

    assert log.status_code == 429
    assert log.provider is None
    assert log.attempts == 0


def test_successful_response_has_rate_limit_headers(
    tight_limiter: RateLimiter, auth_headers: dict[str, str]
) -> None:
    response = client.post("/v1/chat", json=chat_body(), headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "2"
    assert response.headers["x-ratelimit-remaining"] == "1"