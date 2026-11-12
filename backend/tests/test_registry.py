from app.config import Settings
from app.providers.registry import build_registry


def test_gemini_is_not_available_without_a_key() -> None:
    registry = build_registry(Settings(postgres_password="pw", gemini_api_key=None))

    assert registry.models == ["mock-1"]


def test_gemini_is_available_when_a_key_is_set() -> None:
    registry = build_registry(Settings(postgres_password="pw", gemini_api_key="some-key"))

    assert registry.models == ["gemini-flash", "mock-1"]
    assert registry.providers_for("gemini-flash")[0].name == "gemini"


def test_empty_key_is_treated_as_missing() -> None:
    registry = build_registry(Settings(postgres_password="pw", gemini_api_key=""))

    assert registry.models == ["mock-1"]