import time
from collections.abc import Callable

from app.providers.base import (
    ProviderBadRequestError,
    ProviderRateLimitedError,
    ProviderResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas import ChatRequest


class MockProvider:
    """A fake LLM for development and tests. Put a trigger in the last message to make it misbehave:

    [mock:timeout]      raises ProviderTimeoutError
    [mock:error]        raises ProviderUnavailableError
    [mock:rate_limit]   raises ProviderRateLimitedError
    [mock:bad_request]  raises ProviderBadRequestError
    [mock:slow]         waits before replying
    """

    name = "mock"

    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        slow_seconds: float = 2.0,
    ) -> None:
        self._sleep = sleep
        self._slow_seconds = slow_seconds

    def complete(self, request: ChatRequest) -> ProviderResult:
        prompt = request.messages[-1].content

        if "[mock:timeout]" in prompt:
            raise ProviderTimeoutError("Mock provider timed out")
        if "[mock:error]" in prompt:
            raise ProviderUnavailableError("Mock provider returned a server error")
        if "[mock:rate_limit]" in prompt:
            raise ProviderRateLimitedError("Mock provider is rate limiting")
        if "[mock:bad_request]" in prompt:
            raise ProviderBadRequestError("Mock provider rejected the request")
        if "[mock:slow]" in prompt:
            self._sleep(self._slow_seconds)

        words = f"Mock reply to: {prompt}".split()
        if request.max_tokens is not None:
            words = words[: request.max_tokens]

        # Real providers report exact token counts. The mock counts words as a stand-in.
        input_tokens = sum(len(message.content.split()) for message in request.messages)

        return ProviderResult(
            content=" ".join(words),
            model=request.model,
            input_tokens=input_tokens,
            output_tokens=len(words),
        )