import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import ApiKey


def test_api_key_can_be_saved_and_loaded() -> None:
    """Integration test: needs Postgres running and migrations applied."""
    with SessionLocal() as session:
        key = ApiKey(name="test client", key_prefix="tw_test", key_hash="a" * 64)
        session.add(key)
        session.flush()
        session.refresh(key)

        assert key.id is not None
        assert key.created_at is not None
        assert key.revoked_at is None

        session.rollback()


def test_duplicate_key_hash_is_rejected() -> None:
    """The database itself must refuse two keys with the same hash."""
    with SessionLocal() as session:
        session.add(ApiKey(name="first", key_prefix="tw_one", key_hash="b" * 64))
        session.flush()

        session.add(ApiKey(name="second", key_prefix="tw_two", key_hash="b" * 64))
        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()