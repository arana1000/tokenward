import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete

from app.api_keys import create_api_key
from app.db import SessionLocal
from app.models import ApiKey


@pytest.fixture
def api_key() -> Iterator[tuple[uuid.UUID, str]]:
    """Create a real key for the test, then delete it afterwards."""
    with SessionLocal() as session:
        key, plaintext = create_api_key(session, "pytest key")
        key_id = key.id

    yield key_id, plaintext

    with SessionLocal() as session:
        session.execute(delete(ApiKey).where(ApiKey.id == key_id))
        session.commit()


@pytest.fixture
def auth_headers(api_key: tuple[uuid.UUID, str]) -> dict[str, str]:
    _, plaintext = api_key
    return {"Authorization": f"Bearer {plaintext}"}