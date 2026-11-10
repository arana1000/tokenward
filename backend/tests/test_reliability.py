import pytest

from app.providers.base import (
    ProviderBadRequestError,
    ProviderError,
    ProviderResult,
    ProviderUnavailableError,
)
from app.reliability import ProviderCallFailedError, RetryPolicy, complete_with_fallback
from app.schemas import ChatMessage, ChatRequest

REQUEST = ChatRequest(model="mock-1", messages=[ChatMessage(role="user", content="hi")])
NO_DELAY = RetryPolicy(max_attempts=3, base_delay=0.0, max_delay=0.0)


class ScriptedProvider:
    """A fake provider that follows a script: None means succeed, an error means raise it."""

    def __init__(self, name: str, script: list[ProviderError | None]) -> None:
        self.name = name
        self._script = list(script)
        self.calls = 0

    def complete(self, request: ChatRequest) -> ProviderResult:
        self.calls += 1
        step = self._script.pop(0)
        if step is not None:
            raise step
        return ProviderResult(
            content=f"ok from {self.name}", model=request.model, input_tokens=1, output_tokens=1
        )


def unavailable() -> ProviderUnavailableError:
    return ProviderUnavailableError("down")


def test_success_on_first_attempt() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider("primary", [None])

    outcome = complete_with_fallback([provider], REQUEST, NO_DELAY, sleep=sleeps.append)

    assert outcome.provider is provider
    assert outcome.attempts == 1
    assert sleeps == []


def test_retries_retryable_errors_then_succeeds() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider("primary", [unavailable(), unavailable(), None])
    policy = RetryPolicy(max_attempts=3, base_delay=0.2, max_delay=2.0)

    outcome = complete_with_fallback(
        [provider], REQUEST, policy, sleep=sleeps.append, rng=lambda: 1.0
    )

    assert outcome.attempts == 3
    assert provider.calls == 3
    assert sleeps == pytest.approx([0.2, 0.4])


def test_non_retryable_error_is_not_retried_or_failed_over() -> None:
    primary = ScriptedProvider("primary", [ProviderBadRequestError("bad")])
    backup = ScriptedProvider("backup", [None])

    with pytest.raises(ProviderCallFailedError) as exc_info:
        complete_with_fallback([primary, backup], REQUEST, NO_DELAY)

    assert exc_info.value.attempts == 1
    assert isinstance(exc_info.value.last_error, ProviderBadRequestError)
    assert backup.calls == 0


def test_falls_back_to_next_provider_after_retries_exhausted() -> None:
    primary = ScriptedProvider("primary", [unavailable(), unavailable(), unavailable()])
    backup = ScriptedProvider("backup", [None])

    outcome = complete_with_fallback([primary, backup], REQUEST, NO_DELAY)

    assert outcome.provider is backup
    assert outcome.attempts == 4
    assert primary.calls == 3


def test_raises_when_every_provider_fails() -> None:
    primary = ScriptedProvider("primary", [unavailable()] * 3)
    backup = ScriptedProvider("backup", [unavailable()] * 3)

    with pytest.raises(ProviderCallFailedError) as exc_info:
        complete_with_fallback([primary, backup], REQUEST, NO_DELAY)

    assert exc_info.value.attempts == 6
    assert exc_info.value.provider is backup
    assert isinstance(exc_info.value.last_error, ProviderUnavailableError)


def test_backoff_doubles_is_capped_and_jittered() -> None:
    policy = RetryPolicy(base_delay=0.2, max_delay=1.0)

    # rng 1.0 gives the full delay: 0.2, 0.4, 0.8, then capped at 1.0
    full = [policy.delay_for(attempt, rng=lambda: 1.0) for attempt in (1, 2, 3, 4, 10)]
    assert full == pytest.approx([0.2, 0.4, 0.8, 1.0, 1.0])

    # rng 0.0 gives the minimum: half the delay
    assert policy.delay_for(3, rng=lambda: 0.0) == pytest.approx(0.4)