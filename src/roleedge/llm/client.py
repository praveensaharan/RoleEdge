"""``LLM``: the one object feature code uses to call a model.

It wraps a ``Provider`` with two things every call needs:

* a disk cache keyed by (provider, model, messages, schema/tools, effort): reruns are free and
  give identical output, which makes pipeline changes reviewable;
* a usage ledger (one JSON line per call) that the cost report reads.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..config import CACHE_DIR, LEDGER_FILE
from .base import Provider
from .schema import strict_schema
from .types import LLMResult, Message, ToolTurn, Usage


class LLM:
    def __init__(self, provider: Provider, cache_dir: Path = CACHE_DIR, ledger_file: Path = LEDGER_FILE) -> None:
        self.provider = provider
        self.cache_dir = cache_dir
        self.ledger_file = ledger_file

    @property
    def engine(self) -> str:
        """'provider/model', as shown in the activity log."""
        return f"{self.provider.name}/{self.provider.default_model}"

    def engine_for(self, model: str | None) -> str:
        """The activity-log name of a call on ``model`` (the default model when None)."""
        return f"{self.provider.name}/{model or self.provider.default_model}"

    def complete_json(self, task: str, messages: list[Message], schema: type[BaseModel], schema_name: str,
                      effort: str = "low", model: str | None = None) -> LLMResult[dict[str, Any]]:
        """Structured output matching ``schema``. Returns the raw dict (key order as the model wrote it);
        validate with ``schema.model_validate(result.data)`` where typed access is needed. ``model`` picks another
        model of the same provider for this call (the verifier runs on Muse Wonder)."""
        json_schema = strict_schema(schema)

        def call() -> tuple[dict[str, Any], Usage]:
            return self.provider.complete_json(messages, json_schema, schema_name, effort=effort, model=model)

        return self._cached(task, {"m": messages, "s": json_schema, "e": effort}, call, lambda d: d, lambda d: d,
                            model=model)

    def tool_turn(self, task: str, messages: list[Message], tools: list[dict[str, Any]],
                  effort: str = "low") -> LLMResult[ToolTurn]:
        def call() -> tuple[ToolTurn, Usage]:
            return self.provider.call_tools(messages, tools, effort=effort)

        return self._cached(task, {"m": messages, "t": tools, "e": effort}, call, ToolTurn.to_dict, ToolTurn.from_dict)

    # ---------------------------------------------------------------- cache + ledger

    def _cached(self, task: str, payload: dict[str, Any], call: Callable[[], tuple[Any, Usage]],
                encode: Callable[[Any], Any], decode: Callable[[Any], Any], model: str | None = None) -> LLMResult[Any]:
        model = model or self.provider.default_model
        key = hashlib.sha256(json.dumps({"provider": self.provider.name, "model": model, **payload},
                                        sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
        path = self.cache_dir / task / f"{key}.json"
        if path.exists():
            entry = json.loads(path.read_text(encoding="utf-8"))
            usage = Usage.from_dict(entry["usage"])
            self._log(task, usage, cached=True, latency=entry["latency_s"], model=model)
            return LLMResult(decode(entry["data"]), usage, True, entry["latency_s"])

        started = time.time()
        data, usage = call()
        latency = round(time.time() - started, 2)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"data": encode(data), "usage": usage.to_dict(), "latency_s": latency},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        self._log(task, usage, cached=False, latency=latency, model=model)
        return LLMResult(data, usage, False, latency)

    def _log(self, task: str, usage: Usage, cached: bool, latency: float, model: str | None = None) -> None:
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "task": task,
                "provider": self.provider.name, "model": model or self.provider.default_model,
                "replayed_from_cache": cached, "latency_s": latency, **usage.to_dict()}
        with open(self.ledger_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
