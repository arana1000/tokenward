import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal
from app.main import app
from app.models import RequestLog
from app.request_logs import Outcome, record_request

client = TestClient(app)


def chat_body(content: str = "Hello there", model: str = "mock-1") -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": content}]}


def logs_for(key_id: uuid.UUID) -> list[RequestLog]:
    with SessionLocal() as session:
        statement = (
            select(RequestLog)
            .where(RequestLog.api_key_id == key_id)
            .order_by(RequestLog.created_at)
        )
        return list(session.scalars(statement))


def count_all_logs() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(RequestLog)) or 0


def test_successful_request_is_logged(
    api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key

    response = client.post("/v1/chat", json=chat_body(), headers=auth_headers)

    assert response.status_code == 200
    [log] = logs_for(key_id)
    assert log.outcome == Outcome.SUCCESS
    assert log.status_code == 200
    assert log.provider == "mock"
    assert log.model == "mock-1"
    assert log.input_tokens == 2
    assert log.output_tokens == 5
    assert log.cost_usd == Decimal("0.000012")
    assert log.latency_ms is not None and log.latency_ms >= 0
    assert log.error_type is None


def test_provider_error_is_logged(
    api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key

    client.post("/v1/chat", json=chat_body("[mock:error]"), headers=auth_headers)

    [log] = logs_for(key_id)
    assert log.outcome == Outcome.PROVIDER_ERROR
    assert log.status_code == 502
    assert log.error_type == "ProviderUnavailableError"
    assert log.input_tokens is None
    assert log.cost_usd is None


def test_timeout_is_logged(
    api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key

    client.post("/v1/chat", json=chat_body("[mock:timeout]"), headers=auth_headers)

    [log] = logs_for(key_id)
    assert log.outcome == Outcome.TIMEOUT
    assert log.status_code == 504
    assert log.error_type == "ProviderTimeoutError"


def test_unknown_model_is_logged(
    api_key: tuple[uuid.UUID, str], auth_headers: dict[str, str]
) -> None:
    key_id, _ = api_key

    client.post("/v1/chat", json=chat_body(model="gpt-nonexistent"), headers=auth_headers)

    [log] = logs_for(key_id)
    assert log.outcome == Outcome.UNKNOWN_MODEL
    assert log.status_code == 400
    assert log.provider is None
    assert log.model == "gpt-nonexistent"


def test_unauthenticated_request_is_not_logged() -> None:
    before = count_all_logs()

    response = client.post("/v1/chat", json=chat_body())

    assert response.status_code == 401
    assert count_all_logs() == before


class FailingSession:
    """Pretends to be a database session whose commit always fails."""

    def __init__(self) -> None:
        self.rolled_back = False

    def add(self, obj: object) -> None:
        pass

    def commit(self) -> None:
        raise OperationalError("INSERT", {}, Exception("database down"))

    def rollback(self) -> None:
        self.rolled_back = True


def test_logging_failure_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    session = FailingSession()

    record_request(
        session,  # type: ignore[arg-type]
        api_key_id=uuid.uuid4(),
        model="mock-1",
        provider="mock",
        status_code=200,
        outcome=Outcome.SUCCESS,
    )

    assert session.rolled_back is True
    assert "Failed to record request log" in caplog.text