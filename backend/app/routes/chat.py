import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.models import ApiKey
from app.providers.base import ProviderError, ProviderTimeoutError
from app.providers.registry import ProviderRegistry, UnknownModelError, get_registry
from app.request_logs import Outcome, record_request
from app.schemas import ChatRequest, ChatResponse, Usage

router = APIRouter(prefix="/v1", tags=["chat"])


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


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
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Send a chat request to whichever provider serves the requested model."""
    try:
        provider = registry.provider_for(body.model)
    except UnknownModelError:
        record_request(
            db,
            api_key_id=api_key.id,
            model=body.model,
            provider=None,
            status_code=status.HTTP_400_BAD_REQUEST,
            outcome=Outcome.UNKNOWN_MODEL,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model. Available models: {', '.join(registry.models)}",
        ) from None

    started = time.perf_counter()
    try:
        result = provider.complete(body)
    except ProviderTimeoutError as exc:
        record_request(
            db,
            api_key_id=api_key.id,
            model=body.model,
            provider=provider.name,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            outcome=Outcome.TIMEOUT,
            error_type=type(exc).__name__,
            latency_ms=_elapsed_ms(started),
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream provider timed out",
        ) from exc
    except ProviderError as exc:
        record_request(
            db,
            api_key_id=api_key.id,
            model=body.model,
            provider=provider.name,
            status_code=status.HTTP_502_BAD_GATEWAY,
            outcome=Outcome.PROVIDER_ERROR,
            error_type=type(exc).__name__,
            latency_ms=_elapsed_ms(started),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider error",
        ) from exc

    latency_ms = _elapsed_ms(started)
    record_request(
        db,
        api_key_id=api_key.id,
        model=body.model,
        provider=provider.name,
        status_code=status.HTTP_200_OK,
        outcome=Outcome.SUCCESS,
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    return ChatResponse(
        id=f"chat_{uuid.uuid4().hex}",
        provider=provider.name,
        model=result.model,
        content=result.content,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        latency_ms=latency_ms,
    )