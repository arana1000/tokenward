from typing import Any

import httpx2

from app.providers.base import (
    ProviderBadRequestError,
    ProviderRateLimitedError,
    ProviderResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas import ChatRequest

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    """Calls Google's Gemini API and translates its replies and failures into Tokenward's."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model_id: str = "gemini-3.8-flash",
        timeout_seconds: float = 30.0,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._model_id = model_id
        # One shared client reuses connections between requests. `transport` lets tests fake the network.
        self._client = httpx2.Client(
            base_url=GEMINI_BASE_URL,
            headers={"x-goog-api-key": api_key},
            timeout=httpx2.Timeout(timeout_seconds, connect=5.0),
            transport=transport,
        )

    def complete(self, request: ChatRequest) -> ProviderResult:
        try:
            response = self._client.post(
                f"/models/{self._model_id}:generateContent",
                json=_build_payload(request),
            )
        except httpx2.TimeoutException as exc:
            raise ProviderTimeoutError("Gemini request timed out") from exc
        except httpx2.TransportError as exc:
            raise ProviderUnavailableError("Could not reach Gemini") from exc

        _raise_for_status(response.status_code)

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailableError("Gemini returned an unreadable response") from exc

        return _parse_result(data, request.model)


def _build_payload(request: ChatRequest) -> dict[str, Any]:
    """Convert Tokenward's request format into Gemini's."""
    system_texts = [m.content for m in request.messages if m.role == "system"]
    contents = [
        # Gemini calls the assistant's role "model".
        {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
        for m in request.messages
        if m.role != "system"
    ]

    payload: dict[str, Any] = {"contents": contents}
    if system_texts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}
    if request.max_tokens is not None:
        payload["generationConfig"] = {"maxOutputTokens": request.max_tokens}
    return payload


def _raise_for_status(status_code: int) -> None:
    """Translate HTTP failures into Tokenward's provider errors."""
    if status_code == 429:
        raise ProviderRateLimitedError("Gemini is rate limiting requests")
    if status_code >= 500:
        raise ProviderUnavailableError(f"Gemini failed with status {status_code}")
    if status_code >= 400:
        raise ProviderBadRequestError(f"Gemini rejected the request with status {status_code}")


def _parse_result(data: Any, model: str) -> ProviderResult:
    """Pull the reply text and token counts out of Gemini's response."""
    if not isinstance(data, dict):
        raise ProviderUnavailableError("Gemini returned an unexpected response")

    candidates = data.get("candidates") or []
    if not candidates:
        # No candidates usually means the prompt was blocked. Retrying won't change that.
        raise ProviderBadRequestError("Gemini returned no answer")

    parts = candidates[0].get("content", {}).get("parts", [])
    # Skip "thought" parts, which are the model's reasoning rather than its answer.
    content = "".join(part.get("text", "") for part in parts if not part.get("thought"))

    usage = data.get("usageMetadata", {})
    return ProviderResult(
        content=content,
        model=model,
        input_tokens=usage.get("promptTokenCount", 0),
        # Thinking tokens are billed as output, so they count towards cost.
        output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
    )