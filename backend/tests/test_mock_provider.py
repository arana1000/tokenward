import pytest

from app.providers.base import (
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.mock import MockProvider
from app.schemas import ChatMessage, ChatRequest


def make_request(content: str, max_tokens: int | None = None) -> ChatRequest:
    return ChatRequest(
        model="mock-1",
        messages=[ChatMessage(role="user", content=content)],
        max_tokens=max_tokens,
    )


def test_replies_to_last_message() -> None:
    result = MockProvider().complete(make_request("Hello there"))

    assert result.content == "Mock reply to: Hello there"
    assert result.model == "mock-1"


def test_counts_tokens_across_all_messages() -> None:
    request = ChatRequest(
        model="mock-1",
        messages=[
            ChatMessage(role="system", content="Be brief"),
            ChatMessage(role="user", content="Hello there friend"),
        ],
    )

    result = MockProvider().complete(request)

    assert result.input_tokens == 5
    assert result.output_tokens == 6


def test_max_tokens_truncates_reply() -> None:
    result = MockProvider().complete(make_request("one two three four", max_tokens=3))

    assert result.content == "Mock reply to:"
    assert result.output_tokens == 3


@pytest.mark.parametrize(
    ("trigger", "error_type", "retryable"),
    [
        ("[mock:timeout]", ProviderTimeoutError, True),
        ("[mock:error]", ProviderUnavailableError, True),
        ("[mock:rate_limit]", ProviderRateLimitedError, True),
        ("[mock:bad_request]", ProviderBadRequestError, False),
    ],
)
def test_triggers_raise_the_right_error(
    trigger: str, error_type: type[ProviderError], retryable: bool
) -> None:
    with pytest.raises(error_type) as exc_info:
        MockProvider().complete(make_request(f"please {trigger}"))

    assert exc_info.value.retryable is retryable


def test_slow_trigger_waits_before_replying() -> None:
    waits: list[float] = []
    provider = MockProvider(sleep=waits.append, slow_seconds=2.0)

    result = provider.complete(make_request("[mock:slow] hi"))

    assert waits == [2.0]
    assert result.content.startswith("Mock reply to:")