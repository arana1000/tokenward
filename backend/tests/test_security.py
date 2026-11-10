import hashlib

from app.security import DISPLAY_PREFIX_LENGTH, KEY_PREFIX, generate_api_key, hash_api_key


def test_generated_key_has_expected_format() -> None:
    generated = generate_api_key()

    assert generated.plaintext.startswith(KEY_PREFIX)
    assert len(generated.plaintext) > 40


def test_prefix_is_start_of_key() -> None:
    generated = generate_api_key()

    assert generated.prefix == generated.plaintext[:DISPLAY_PREFIX_LENGTH]


def test_hash_is_sha256_of_key() -> None:
    generated = generate_api_key()

    expected = hashlib.sha256(generated.plaintext.encode("utf-8")).hexdigest()
    assert generated.key_hash == expected
    assert hash_api_key(generated.plaintext) == expected


def test_generated_keys_are_unique() -> None:
    keys = {generate_api_key().plaintext for _ in range(100)}

    assert len(keys) == 100