import uuid

import pytest
from fastapi.testclient import TestClient

from app.api_keys import create_api_key, revoke_api_key
from app.db import SessionLocal
from app.main import app
from app.models import ApiKey

client = TestClient(app)


def test_missing_key_returns_401() -> None:
    response = client.get("/v1/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_wrong_key_returns_401() -> None:
    response = client.get("/v1/me", headers={"Authorization": "Bearer tw_not_a_real_key"})

    assert response.status_code == 401


def test_valid_key_returns_key_info(api_key: tuple[uuid.UUID, str]) -> None:
    key_id, plaintext = api_key

    response = client.get("/v1/me", headers={"Authorization": f"Bearer {plaintext}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(key_id)
    assert body["name"] == "pytest key"
    assert body["key_prefix"] == plaintext[:12]
    assert "key_hash" not in body


def test_revoked_key_returns_401(api_key: tuple[uuid.UUID, str]) -> None:
    key_id, plaintext = api_key
    with SessionLocal() as session:
        assert revoke_api_key(session, key_id) is True

    response = client.get("/v1/me", headers={"Authorization": f"Bearer {plaintext}"})

    assert response.status_code == 401


def test_plaintext_key_is_never_stored(api_key: tuple[uuid.UUID, str]) -> None:
    key_id, plaintext = api_key
    with SessionLocal() as session:
        row = session.get(ApiKey, key_id)

    assert row is not None
    assert plaintext not in (row.name, row.key_prefix, row.key_hash)


def test_blank_name_is_rejected() -> None:
    with SessionLocal() as session, pytest.raises(ValueError):
        create_api_key(session, "   ")