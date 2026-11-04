"""Configuration: repository paths and settings from environment variables.

This is the only module that reads ``os.environ``. Everything else receives a ``Settings``
object (or calls ``get_settings()``), so tests can build settings by hand.

Environment variables (put them in ``.env``; see ``.env.example``):

    AZURE_AI_ENDPOINT, AZURE_AI_API_KEY, MODEL_DEPLOYMENT    Azure OpenAI (development)
    META_API_KEY, META_RESPONSES_URL, META_MODEL             Meta API (production target)
    CARECIRCLE_PROVIDER                                      "azure" or "meta" (default: meta when only a Meta key is set)
    ALLOW_CONTRIBUTOR_MODELS                                 "1" to allow Meta *-contributor models
    MODAL_TOKEN_ID, MODAL_TOKEN_SECRET                       Modal (GPU services); ModalTokenID / ModalTokenSecret also read
    ROLEEDGE_RULES                                           "strict" (only Meta models at runtime) or "open"
    ROLEEDGE_GUARD_URL, ROLEEDGE_GUARD_KEY                   the tuned child guard on Modal (docs/GUARD.md)
    ROLEEDGE_STUDIO_SPEND_CAP_USD                            no new model call once the app has spent this much
    ROLEEDGE_LEDGER_BACKUP                                   a file on lasting storage that keeps the spend across restarts

The older Meta names API_KEY / URL / MODEL / MODEL_API_KEY are still read as fallbacks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
OUTPUT_DIR = REPO_ROOT / "output"
CACHE_DIR = REPO_ROOT / ".cache" / "llm"
LEDGER_FILE = OUTPUT_DIR / "usage.jsonl"
WEB_DIR = REPO_ROOT / "web" / "chat"
DEMO_WEB_DIR = REPO_ROOT / "web" / "demo"  # the CareCircle product demo (roleedge chat -> /demo)
APP_WEB_DIR = REPO_ROOT / "web" / "app"  # the roleEdge app (roleedge serve)

DEFAULT_META_URL = "https://api.meta.ai/v1/responses"
DEFAULT_META_MODEL = "muse-spark-1.3"
DEFAULT_AZURE_DEPLOYMENT = "gpt5mini"


class ConfigError(RuntimeError):
    """A provider is missing, misconfigured, or not allowed for this use."""


@dataclass(frozen=True)
class AzureConfig:
    endpoint: str
    api_key: str
    deployment: str


@dataclass(frozen=True)
class MetaConfig:
    api_key: str
    responses_url: str
    model: str


@dataclass(frozen=True)
class ModalConfig:
    token_id: str
    token_secret: str


@dataclass(frozen=True)
class Settings:
    azure: AzureConfig | None
    meta: MetaConfig | None
    pipeline_provider: str = "azure"
    allow_contributor_models: bool = False
    modal: ModalConfig | None = None
    rules: str = "strict"  # strict: every model called at runtime is a Meta model (hackathon rule)
    studio_spend_cap_usd: float = 25.0  # no new model call once the ledger shows this much Meta spend (app/guards.py)
    ledger_backup: str = ""  # a copy of the usage ledger on lasting storage, so the cap survives a restart (Cloud Run)
    notion_token: str = ""  # a Notion internal integration's secret: the share box can then share Notion pages
    guard_url: str = ""  # the tuned child guard on Modal (docs/GUARD.md); empty = Muse Spark reviews children's packs
    guard_key: str = ""  # the shared key the guard endpoint checks (the GUARD_KEY in its Modal secret)
    google_client_id: str = ""  # a Google Cloud OAuth client (web application): lets a family connect Gmail and Calendar
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8100/api/connect/google/callback"
    vault_key: str = ""  # encrypts connected accounts' tokens; generated into output/.vault_key when not set


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)

    azure = None
    endpoint = _first_env("AZURE_AI_ENDPOINT")
    azure_key = _first_env("AZURE_AI_API_KEY")
    if endpoint and azure_key:
        azure = AzureConfig(endpoint.rstrip("/"), azure_key, _first_env("MODEL_DEPLOYMENT", default=DEFAULT_AZURE_DEPLOYMENT))

    meta = None
    meta_key = _first_env("META_API_KEY", "API_KEY", "MODEL_API_KEY")
    if meta_key:
        meta = MetaConfig(
            api_key=meta_key,
            responses_url=_first_env("META_RESPONSES_URL", "URL", default=DEFAULT_META_URL),
            model=_first_env("META_MODEL", "MODEL", default=DEFAULT_META_MODEL),
        )

    modal = None
    token_id = _first_env("MODAL_TOKEN_ID", "ModalTokenID")
    token_secret = _first_env("MODAL_TOKEN_SECRET", "ModalTokenSecret")
    if token_id and token_secret:
        modal = ModalConfig(token_id, token_secret)
        os.environ.setdefault("MODAL_TOKEN_ID", token_id)  # the Modal client reads these names
        os.environ.setdefault("MODAL_TOKEN_SECRET", token_secret)

    return Settings(
        azure=azure,
        meta=meta,
        # with only a Meta key (a judge's copy), Meta is the default; Azure stays the default where it is set up
        pipeline_provider=_first_env("ROLEEDGE_PROVIDER", "CARECIRCLE_PROVIDER", default="meta" if meta and not azure else "azure"),
        allow_contributor_models=_first_env("ALLOW_CONTRIBUTOR_MODELS") == "1",
        modal=modal,
        rules=_first_env("ROLEEDGE_RULES", default="strict"),
        studio_spend_cap_usd=float(_first_env("ROLEEDGE_STUDIO_SPEND_CAP_USD", default="25") or 25),
        ledger_backup=_first_env("ROLEEDGE_LEDGER_BACKUP"),
        notion_token=_first_env("NOTION_TOKEN"),
        guard_url=_first_env("ROLEEDGE_GUARD_URL"),
        guard_key=_first_env("ROLEEDGE_GUARD_KEY"),
        google_client_id=_first_env("ROLEEDGE_GOOGLE_CLIENT_ID"),
        google_client_secret=_first_env("ROLEEDGE_GOOGLE_CLIENT_SECRET"),
        google_redirect_uri=_first_env("ROLEEDGE_GOOGLE_REDIRECT_URI", default="http://localhost:8100/api/connect/google/callback"),
        vault_key=_first_env("ROLEEDGE_VAULT_KEY"),
    )
