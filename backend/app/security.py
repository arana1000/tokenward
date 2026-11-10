import hashlib
import secrets
from dataclasses import dataclass

KEY_PREFIX = "tw_"
DISPLAY_PREFIX_LENGTH = 12


@dataclass(frozen=True)
class GeneratedKey:
    plaintext: str  # shown to the client once, never stored
    prefix: str  # safe to store and display, e.g. "tw_AbC123xY"
    key_hash: str  # what the database stores


def hash_api_key(plaintext: str) -> str:
    """SHA-256 is right for long random keys; passwords would need a slow hash like bcrypt."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedKey:
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedKey(
        plaintext=plaintext,
        prefix=plaintext[:DISPLAY_PREFIX_LENGTH],
        key_hash=hash_api_key(plaintext),
    )