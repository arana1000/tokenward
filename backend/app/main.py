from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(title="Tokenward API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["ok"]


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