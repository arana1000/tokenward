from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api_keys import find_active_key
from app.db import get_db
from app.models import ApiKey

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    # Same response for missing, wrong and revoked keys, so attackers learn nothing.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiKey:
    """FastAPI dependency: returns the caller's API key or rejects the request with 401."""
    if credentials is None:
        raise _unauthorized()

    api_key = find_active_key(db, credentials.credentials)
    if api_key is None:
        raise _unauthorized()

    return api_key