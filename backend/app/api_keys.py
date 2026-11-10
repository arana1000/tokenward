import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey
from app.security import generate_api_key, hash_api_key

MAX_NAME_LENGTH = 100


def create_api_key(session: Session, name: str) -> tuple[ApiKey, str]:
    """Create a key and return the saved row plus the plaintext key (shown once)."""
    name = name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be 1 to {MAX_NAME_LENGTH} characters")

    generated = generate_api_key()
    api_key = ApiKey(name=name, key_prefix=generated.prefix, key_hash=generated.key_hash)
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key, generated.plaintext


def find_active_key(session: Session, plaintext: str) -> ApiKey | None:
    """Look a key up by its hash. Revoked keys are never returned."""
    statement = select(ApiKey).where(
        ApiKey.key_hash == hash_api_key(plaintext),
        ApiKey.revoked_at.is_(None),
    )
    return session.scalars(statement).first()


def list_api_keys(session: Session) -> list[ApiKey]:
    return list(session.scalars(select(ApiKey).order_by(ApiKey.created_at)))


def revoke_api_key(session: Session, key_id: uuid.UUID) -> bool:
    """Mark a key as revoked. Returns False if it doesn't exist or is already revoked."""
    api_key = session.get(ApiKey, key_id)
    if api_key is None or api_key.revoked_at is not None:
        return False
    api_key.revoked_at = datetime.now(UTC)
    session.commit()
    return True