from collections.abc import Sequence
from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.gemini import GeminiProvider
from app.providers.mock import MockProvider


class UnknownModelError(Exception):
    pass


class ProviderRegistry:
    """Maps each model name to an ordered list of providers: primary first, then fallbacks."""

    def __init__(self, routes: dict[str, Sequence[LLMProvider]]) -> None:
        for model, providers in routes.items():
            if not providers:
                raise ValueError(f"Model {model!r} has no providers")
        self._routes = {model: tuple(providers) for model, providers in routes.items()}

    def providers_for(self, model: str) -> tuple[LLMProvider, ...]:
        try:
            return self._routes[model]
        except KeyError:
            raise UnknownModelError(model) from None

    @property
    def models(self) -> list[str]:
        return sorted(self._routes)


def build_registry(settings: Settings) -> ProviderRegistry:
    """Decide which models are available from the app's settings."""
    routes: dict[str, Sequence[LLMProvider]] = {
        "mock-1": [MockProvider(name="mock"), MockProvider(name="mock-backup")],
    }

    gemini_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    if gemini_key:
        routes["gemini-flash"] = [
            GeminiProvider(
                api_key=gemini_key,
                model_id=settings.gemini_model,
                timeout_seconds=settings.provider_timeout_seconds,
            )
        ]

    return ProviderRegistry(routes)


@lru_cache
def get_registry() -> ProviderRegistry:
    """FastAPI dependency. Cached so providers and their connections are created once."""
    return build_registry(get_settings())