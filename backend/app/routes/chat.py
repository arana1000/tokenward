import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.models import ApiKey
from app.providers.base import ProviderTimeoutError
from app.providers.registry import ProviderRegistry, UnknownModelError, get_registry
from app.reliability import (
    ProviderCallFailedError,
    RetryPolicy,
    complete_with_fallback,
    get_retry_policy,
)
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
    retry_policy: Annotated[RetryPolicy, Depends(get_retry_policy)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Send a chat request to the providers for the requested model, with retries and fallback."""
    try:
        providers = registry.providers_for(body.model)
    except UnknownModelError:
        record_request(
            db,
            api_key_id=api_key.id,
            model=body.model,
            provider=None,
            status_code=status.HTTP_400_BAD_REQUEST,
            outcome=Outcome.UNKNOWN_MODEL,
            attempts=0,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model. Available models: {', '.join(registry.models)}",
        ) from None

    started = time.perf_counter()
    try:
        outcome = complete_with_fallback(providers, body, retry_policy)
    except ProviderCallFailedError as failure:
        timed_out = isinstance(failure.last_error, ProviderTimeoutError)
        status_code = (
            status.HTTP_504_GATEWAY_TIMEOUT if timed_out else status.HTTP_502_BAD_GATEWAY
        )
        record_request(
            db,
            api_key_id=api_key.id,
            model=body.model,
            provider=failure.provider.name,
            status_code=status_code,
            outcome=Outcome.TIMEOUT if timed_out else Outcome.PROVIDER_ERROR,
            error_type=type(failure.last_error).__name__,
            latency_ms=_elapsed_ms(started),
            attempts=failure.attempts,
        )
        raise HTTPException(
            status_code=status_code,
            detail="Upstream provider timed out" if timed_out else "Upstream provider error",
        ) from failure

    latency_ms = _elapsed_ms(started)
    result = outcome.result
    record_request(
        db,
        api_key_id=api_key.id,
        model=body.model,
        provider=outcome.provider.name,
        status_code=status.HTTP_200_OK,
        outcome=Outcome.SUCCESS,
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        attempts=outcome.attempts,
    )

    return ChatResponse(
        id=f"chat_{uuid.uuid4().hex}",
        provider=outcome.provider.name,
        model=result.model,
        content=result.content,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        latency_ms=latency_ms,
    )