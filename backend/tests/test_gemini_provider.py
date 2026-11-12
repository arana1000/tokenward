import json
import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import RequestLog
from app.providers.base import (
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.gemini import GeminiProvider
from app.providers.registry import ProviderRegistry, get_registry
from app.schemas import ChatMessage, ChatRequest

client = TestClient(app)

SUCCESS_BODY = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": "Hello "}, {"text": "there"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 12,
        "candidatesTokenCount": 5,
        "thoughtsTokenCount": 20,
        "totalTokenCount": 37,
    },
}

SIMPLE_REQUEST = ChatRequest(
    model="gemini-flash", messages=[ChatMessage(role="user", content="Hi")]
)


def make_provider(handler: Callable[[httpx2.Request], httpx2.Response]) -> GeminiProvider:
    return GeminiProvider(api_key="test-key", transport=httpx2.MockTransport(handler))


def respond_with(status_code: int, body: object) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda request: httpx2.Response(status_code, json=body)


def test_sends_request_in_gemini_format() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, json=SUCCESS_BODY)

    request = ChatRequest(
        model="gemini-flash",
        messages=[
            ChatMessage(role="system", content="Be brief"),
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello"),
            ChatMessage(role="user", content="How are you?"),
        ],
        max_tokens=50,
    )

    make_provider(handler).complete(request)

    [sent] = captured
    assert sent.method == "POST"
    assert "gemini-3.8-flash" in str(sent.url)
    assert str(sent.url).endswith("generateContent")
    assert sent.headers["x-goog-api-key"] == "test-key"
    assert json.loads(sent.content) == {
        "contents": [
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello"}]},
            {"role": "user", "parts": [{"text": "How are you?"}]},
        ],
        "systemInstruction": {"parts": [{"text": "Be brief"}]},
        "generationConfig": {"maxOutputTokens": 50},
    }


def test_parses_reply_and_token_usage() -> None:
    result = make_provider(respond_with(200, SUCCESS_BODY)).complete(SIMPLE_REQUEST)

    assert result.content == "Hello there"
    assert result.model == "gemini-flash"
    assert result.input_tokens == 12
    assert result.output_tokens == 25  # 5 answer tokens plus 20 thinking tokens


@pytest.mark.parametrize(
    ("status_code", "error_type", "retryable"),
    [
        (429, ProviderRateLimitedError, True),
        (500, ProviderUnavailableError, True),
        (400, ProviderBadRequestError, False),
        (401, ProviderBadRequestError, False),
    ],
)
def test_http_errors_become_provider_errors(
    status_code: int, error_type: type[ProviderError], retryable: bool
) -> None:
    provider = make_provider(respond_with(status_code, {"error": {"message": "nope"}}))

    with pytest.raises(error_type) as exc_info:
        provider.complete(SIMPLE_REQUEST)

    assert exc_info.value.retryable is retryable


def test_timeout_becomes_provider_timeout() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("too slow", request=request)

    with pytest.raises(ProviderTimeoutError):
        make_provider(handler).complete(SIMPLE_REQUEST)


def test_network_failure_becomes_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    with pytest.raises(ProviderUnavailableError):
        make_provider(handler).complete(SIMPLE_REQUEST)


def test_blocked_prompt_is_a_bad_request() -> None:
    body = {"promptFeedback": {"blockReason": "SAFETY"}}

    with pytest.raises(ProviderBadRequestError):
        make_provider(respond_with(200, body)).complete(SIMPLE_REQUEST)


def test_thought_parts_are_left_out_of_the_reply() -> None:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": "Let me think", "thought": True}, {"text": "Answer"}]}}
        ],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }

    result = make_provider(respond_with(200, body)).complete(SIMPLE_REQUEST)

    assert result.content == "Answer"


def test_api_key_never_appears_in_error_messages() -> None:
    provider = make_provider(respond_with(401, {"error": {"message": "bad key test-key"}}))

    with pytest.raises(ProviderBadRequestError) as exc_info:
        provider.complete(SIMPLE_REQUEST)

    assert "test-key" not in str(exc_info.value)


def test_chat_endpoint_uses_gemini_and_logs_cost(
    api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key
    provider = make_provider(respond_with(200, SUCCESS_BODY))
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry({"gemini-flash": [provider]})
    try:
        response = client.post(
            "/v1/chat",
            json={"model": "gemini-flash", "messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_registry, None)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "gemini"
    assert body["content"] == "Hello there"
    assert body["usage"] == {"input_tokens": 12, "output_tokens": 25}

    with SessionLocal() as session:
        log = session.scalars(select(RequestLog).where(RequestLog.api_key_id == key_id)).one()
    assert log.provider == "gemini"
    # (12 x $0.30 + 25 x $2.50) per million tokens
    assert log.cost_usd == Decimal("0.0000661")