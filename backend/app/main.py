import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.models import ApiKey

app = FastAPI(title="Tokenward API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["ok"]


class KeyInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime


@app.get("/health")
def health() -> HealthResponse:
    """Liveness check: confirms the API process is running and answering requests."""
    return HealthResponse(status="ok")


@app.get("/ready", responses={503: {"description": "Database unavailable"}})
def ready(db: Annotated[Session, Depends(get_db)]) -> ReadinessResponse:
    """Readiness check: confirms the API can reach the database."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return ReadinessResponse(status="ready", database="ok")


@app.get("/v1/me", responses={401: {"description": "Invalid or missing API key"}})
def me(api_key: Annotated[ApiKey, Depends(require_api_key)]) -> KeyInfoResponse:
    """Returns details of the API key used to make this request."""
    return KeyInfoResponse.model_validate(api_key)