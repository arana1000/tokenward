from collections.abc import Sequence

from app.providers.base import LLMProvider
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


_default_registry = ProviderRegistry(
    {"mock-1": [MockProvider(name="mock"), MockProvider(name="mock-backup")]}
)


def get_registry() -> ProviderRegistry:
    """FastAPI dependency, so tests can swap in a different registry."""
    return _default_registry