import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.providers.base import LLMProvider, ProviderError, ProviderResult
from app.schemas import ChatRequest


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3  # per provider, including the first try
    base_delay: float = 0.2  # seconds
    max_delay: float = 2.0  # seconds

    def delay_for(self, attempt: int, rng: Callable[[], float] = random.random) -> float:
        """Exponential backoff with jitter. `attempt` is the attempt that just failed, from 1."""
        capped = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
        # Wait between half and all of the capped delay, so clients don't retry in lockstep.
        return capped / 2 + rng() * capped / 2


@dataclass(frozen=True)
class CallOutcome:
    result: ProviderResult
    provider: LLMProvider
    attempts: int  # total provider calls made, across all providers


class ProviderCallFailedError(Exception):
    """Every allowed attempt failed, or a non-retryable error stopped us early."""

    def __init__(self, last_error: ProviderError, provider: LLMProvider, attempts: int) -> None:
        super().__init__(str(last_error))
        self.last_error = last_error
        self.provider = provider
        self.attempts = attempts


def complete_with_fallback(
    providers: Sequence[LLMProvider],
    request: ChatRequest,
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> CallOutcome:
    """Try each provider in order, retrying retryable errors with backoff before moving on."""
    if not providers:
        raise ValueError("At least one provider is required")

    attempts = 0
    last_error: ProviderError | None = None
    last_provider: LLMProvider = providers[0]

    for provider in providers:
        for attempt in range(1, policy.max_attempts + 1):
            attempts += 1
            try:
                result = provider.complete(request)
            except ProviderError as exc:
                last_error, last_provider = exc, provider
                if not exc.retryable:
                    raise ProviderCallFailedError(exc, provider, attempts) from exc
                if attempt < policy.max_attempts:
                    sleep(policy.delay_for(attempt, rng))
                continue
            return CallOutcome(result=result, provider=provider, attempts=attempts)

    assert last_error is not None
    raise ProviderCallFailedError(last_error, last_provider, attempts) from last_error


def get_retry_policy() -> RetryPolicy:
    """FastAPI dependency, so tests can swap in a policy with no delays."""
    return RetryPolicy()