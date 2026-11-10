import logging
import uuid
from enum import StrEnum

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import RequestLog
from app.pricing import estimate_cost

logger = logging.getLogger(__name__)


class Outcome(StrEnum):
    SUCCESS = "success"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    UNKNOWN_MODEL = "unknown_model"
    RATE_LIMITED = "rate_limited"


def record_request(
    session: Session,
    *,
    api_key_id: uuid.UUID,
    model: str,
    provider: str | None,
    status_code: int,
    outcome: Outcome,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_type: str | None = None,
    attempts: int = 1,
) -> None:
    """Save one request log row. A logging failure must never fail the client's request."""
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = estimate_cost(model, input_tokens, output_tokens)

    session.add(
        RequestLog(
            api_key_id=api_key_id,
            model=model,
            provider=provider,
            status_code=status_code,
            outcome=outcome.value,
            error_type=error_type,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            attempts=attempts,
        )
    )
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Failed to record request log for model %s", model)