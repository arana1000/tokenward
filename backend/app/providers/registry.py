from app.providers.base import LLMProvider
from app.providers.mock import MockProvider


class UnknownModelError(Exception):
    pass


class ProviderRegistry:
    """Maps model names that clients can request to the provider that serves them."""

    def __init__(self, routes: dict[str, LLMProvider]) -> None:
        self._routes = dict(routes)

    def provider_for(self, model: str) -> LLMProvider:
        try:
            return self._routes[model]
        except KeyError:
            raise UnknownModelError(model) from None

    @property
    def models(self) -> list[str]:
        return sorted(self._routes)


_default_registry = ProviderRegistry({"mock-1": MockProvider()})


def get_registry() -> ProviderRegistry:
    """FastAPI dependency, so tests can swap in a different registry."""
    return _default_registry