"""Which providers exist, which are configured, and which one the product pipelines use."""

from __future__ import annotations

from ..config import ConfigError, Settings, get_settings
from .azure import AzureProvider
from .base import Provider
from .meta import MetaProvider

# Every provider the code knows, in display order. Configured or not, the UI lists them.
PROVIDER_CLASSES: dict[str, type[Provider]] = {"meta": MetaProvider, "azure": AzureProvider}


def configured_providers(settings: Settings | None = None) -> dict[str, Provider]:
    """Providers that have credentials in the environment, keyed by id."""
    settings = settings or get_settings()
    found: dict[str, Provider] = {}
    if settings.meta:
        found["meta"] = MetaProvider(settings.meta)
    if settings.azure:
        found["azure"] = AzureProvider(settings.azure)
    return found


def get_provider(name: str, settings: Settings | None = None) -> Provider:
    providers = configured_providers(settings)
    if name not in providers:
        raise ConfigError(f"Provider '{name}' is not configured. Check .env (see .env.example).")
    return providers[name]


def is_contributor_model(model: str) -> bool:
    """Meta's *-contributor models are cheap because Meta trains on the content sent to them."""
    return model.endswith("-contributor")


def pipeline_provider(settings: Settings | None = None) -> Provider:
    """The provider the content and check-in pipelines run on (CARECIRCLE_PROVIDER).

    Refuses training-contributor models unless ALLOW_CONTRIBUTOR_MODELS=1, because product
    pipelines handle family, health and children's data.
    """
    settings = settings or get_settings()
    provider = get_provider(settings.pipeline_provider, settings)
    if is_contributor_model(provider.default_model) and not settings.allow_contributor_models:
        raise ConfigError(f"'{provider.default_model}' trains on your data and is blocked for pipelines. "
                          "Use a non-contributor model, or set ALLOW_CONTRIBUTOR_MODELS=1 for synthetic tests only.")
    return provider
