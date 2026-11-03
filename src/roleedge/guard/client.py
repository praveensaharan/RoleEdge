"""The app's side of the tuned guard: send a pack's lines to the endpoint on Modal, get a verdict per line.

The endpoint (modal_apps/guard_lora.py) scales to zero, so the first call after a quiet spell waits for a GPU to
start; the caller falls back to the Muse Spark guardian if it doesn't answer in time.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from ..config import get_settings
from .policy import CATEGORIES, Verdict

MAX_LINES = 64  # the endpoint refuses more in one call


class TunedGuard:
    engine = "modal/llama-guard-3-1b+lora"

    def __init__(self, url: str, key: str, timeout_s: float = 60.0) -> None:
        self.url, self.key, self.timeout_s = url, key, timeout_s

    def classify(self, lines: Sequence[str], age: int | None = None, language: str = "") -> list[Verdict]:
        verdicts: list[Verdict] = []
        for start in range(0, len(lines), MAX_LINES):
            chunk = list(lines[start:start + MAX_LINES])
            response = httpx.post(self.url, json={"lines": chunk, "age": age, "language": language},
                                  headers={"Authorization": f"Bearer {self.key}"}, timeout=self.timeout_s)
            response.raise_for_status()
            results = response.json().get("results", [])
            if len(results) != len(chunk):
                raise ValueError(f"the guard answered {len(results)} of {len(chunk)} lines")
            verdicts += [Verdict(safe=bool(r.get("safe")), categories=[c for c in r.get("categories", []) if c in CATEGORIES],
                                 parsed=bool(r.get("parsed", True))) for r in results]
        return verdicts


def tuned_guard_from_settings() -> TunedGuard | None:
    """The deployed guard if ROLEEDGE_GUARD_URL and ROLEEDGE_GUARD_KEY are set, else None (Muse Spark reviews)."""
    settings = get_settings()
    return TunedGuard(settings.guard_url, settings.guard_key) if settings.guard_url and settings.guard_key else None
