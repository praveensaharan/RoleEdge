"""A small client for Meta's developer API (Responses format), used only to write and check training data.

Standard library only. Every answer is cached on disk (``.cache/``), so running a step again is free and gives the
same data, and every call's token use is added to ``.cache/usage.jsonl``.

Needs ``META_API_KEY`` (and optionally ``META_MODEL``, ``META_RESPONSES_URL``) in the environment or in ``.env``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
DEFAULT_MODEL = "muse-spark-1.3-contributor"  # cheap; Meta trains on what is sent, fine for synthetic data only
DEFAULT_URL = "https://api.meta.ai/v1/responses"
PRICE_IN, PRICE_OUT = 0.10, 0.20  # USD per 1M tokens for the contributor model (check Meta's price list)
RETRY = {429, 500, 502, 503, 504}


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=value lines from .env into the environment (values already set win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class MetaAPI:
    def __init__(self, api_key: str | None = None, model: str | None = None, url: str | None = None,
                 cache: Path = CACHE) -> None:
        load_env()
        self.api_key = api_key or os.environ.get("META_API_KEY", "")
        self.model = model or os.environ.get("META_MODEL") or DEFAULT_MODEL
        self.url = url or os.environ.get("META_RESPONSES_URL") or DEFAULT_URL
        self.cache = cache
        if not self.api_key:
            raise SystemExit("Set META_API_KEY in scam-checker/.env (see .env.example).")

    def json(self, task: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str,
             effort: str = "low") -> dict[str, Any]:
        """One structured-output call; the answer matches ``schema``. Cached by (model, messages, schema, effort)."""
        body = {"model": self.model, "input": messages, "max_output_tokens": 16000, "reasoning": {"effort": effort},
                "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}}}
        key = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
        path = self.cache / task / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["data"]
        started = time.time()
        reply = self._post(body)
        if reply.get("status") == "incomplete":
            raise RuntimeError(f"no complete answer: {(reply.get('incomplete_details') or {}).get('reason')}")
        text = "".join(c.get("text", "") for item in reply.get("output", []) if item.get("type") == "message"
                       for c in item.get("content", []))
        data = json.loads(text)
        usage = reply.get("usage") or {}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"data": data, "usage": usage}, ensure_ascii=False), encoding="utf-8")
        with open(self.cache / "usage.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"task": task, "model": self.model, "s": round(time.time() - started, 1),
                                 "in": usage.get("input_tokens", 0), "out": usage.get("output_tokens", 0)}) + "\n")
        return data

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRY or attempt == 4:
                    raise RuntimeError(f"Meta API HTTP {exc.code}: {exc.read()[:500]!r}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == 4:
                    raise
            time.sleep(min(60, 2 ** (attempt + 1)))
        raise AssertionError("unreachable")


def spend(cache: Path = CACHE) -> dict[str, float]:
    """Tokens and dollars spent so far (uncached calls only)."""
    path = cache / "usage.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    tokens_in, tokens_out = sum(r["in"] for r in rows), sum(r["out"] for r in rows)
    return {"calls": len(rows), "tokens_in": tokens_in, "tokens_out": tokens_out,
            "usd": round(tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT, 3)}
