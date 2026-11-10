import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_api_key
from app.models import ApiKey
from app.providers.base import ProviderError, ProviderTimeoutError
from app.providers.registry import ProviderRegistry, UnknownModelError, get_registry
from app.schemas import ChatRequest, ChatResponse, Usage

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post(
    "/chat",
    responses={
        400: {"description": "Unknown model"},
        401: {"description": "Invalid or missing API key"},
        502: {"description": "Upstream provider error"},
        504: {"description": "Upstream provider timed out"},
    },
)
def chat(
    body: ChatRequest,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
) -> ChatResponse:
    """Send a chat request to whichever provider serves the requested model."""
    try:
        provider = registry.provider_for(body.model)
    except UnknownModelError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model. Available models: {', '.join(registry.models)}",
        ) from None

    started = time.perf_counter()
    try:
        result = provider.complete(body)
    except ProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream provider timed out",
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider error",
        ) from exc
    latency_ms = round((time.perf_counter() - started) * 1000)

    return ChatResponse(
        id=f"chat_{uuid.uuid4().hex}",
        provider=provider.name,
        model=result.model,
        content=result.content,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        latency_ms=latency_ms,
    )