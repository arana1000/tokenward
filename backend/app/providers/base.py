from dataclasses import dataclass
from typing import Protocol

from app.schemas import ChatRequest


@dataclass(frozen=True)
class ProviderResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """Base class for provider failures. `retryable` says whether trying again could succeed."""

    retryable: bool = False


class ProviderTimeoutError(ProviderError):
    retryable = True


class ProviderUnavailableError(ProviderError):
    """The provider had a server-side failure, such as an HTTP 5xx."""

    retryable = True


class ProviderRateLimitedError(ProviderError):
    """The provider is limiting our requests, such as an HTTP 429."""

    retryable = True


class ProviderBadRequestError(ProviderError):
    """The provider rejected the request itself. Sending it again won't help."""

    retryable = False


class LLMProvider(Protocol):
    """Anything with a `name` and a `complete` method like this counts as a provider."""

    name: str

    def complete(self, request: ChatRequest) -> ProviderResult: ...