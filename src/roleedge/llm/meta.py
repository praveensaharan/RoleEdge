"""Meta developer API (api.meta.ai/v1/responses, OpenAI Responses-style). The production target.

Verified on 2026-10-27 against muse-spark-1.1/1.2/1.3: text, multi-turn history, image input,
reasoning efforts minimal..max. Tool calling follows the documented Responses format (flat function tools;
``function_call`` / ``function_call_output`` items; only ``tool_choice: auto``); history is rebuilt on every turn,
so no ``previous_response_id`` is needed.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import MetaConfig
from .base import MAX_OUTPUT_TOKENS, Provider
from .http import get_json, post_json
from .types import ChatReply, Message, ProviderError, ToolCall, ToolTurn, Usage

CHAT_MODEL_PREFIXES = ("muse-spark", "muse-wonder")  # the other Meta models are image, voice or segmentation


class MetaProvider(Provider):
    name = "meta"
    label = "Meta AI"
    efforts = ("minimal", "low", "medium", "high", "xhigh", "max")

    def __init__(self, config: MetaConfig) -> None:
        self.config = config

    @property
    def default_model(self) -> str:
        return self.config.model

    @property
    def base_url(self) -> str:
        return self.config.responses_url.rsplit("/responses", 1)[0]

    # ---------------------------------------------------------------- wire format

    @staticmethod
    def to_responses_input(messages: list[Message]) -> list[dict[str, Any]]:
        """Chat Completions messages -> Responses API ``input`` items (tool calls and results included)."""
        items: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "tool":
                items.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": m["content"]})
                continue
            if m["role"] == "assistant" and m.get("tool_calls"):
                if m.get("content"):
                    items.append({"role": "assistant", "content": m["content"]})
                items.extend({"type": "function_call", "call_id": c["id"], "name": c["function"]["name"],
                              "arguments": c["function"]["arguments"]} for c in m["tool_calls"])
                continue
            content = m["content"]
            if isinstance(content, list):
                content = [{"type": "input_text", "text": p["text"]} if p["type"] == "text"
                           else {"type": "input_video", "video_url": p["video_url"]["url"]} if p["type"] == "video_url"
                           else {"type": "input_image", "image_url": p["image_url"]["url"]} for p in content]
            items.append({"role": m["role"], "content": content})
        return items

    @staticmethod
    def output_text(data: dict[str, Any]) -> str:
        return "".join(c.get("text", "") for item in data.get("output", []) if item.get("type") == "message"
                       for c in item.get("content", []))

    @staticmethod
    def _usage(data: dict[str, Any]) -> Usage:
        u = data.get("usage") or {}
        return Usage(input=u.get("input_tokens", 0),
                     cached=(u.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0,
                     output=u.get("output_tokens", 0),
                     reasoning=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0) or 0)

    def _respond(self, body: dict[str, Any]) -> dict[str, Any]:
        return post_json(self.name, self.config.responses_url, body, {"Authorization": f"Bearer {self.config.api_key}"})

    # ---------------------------------------------------------------- Provider API

    def list_models(self) -> list[str]:
        try:
            data = get_json(self.name, f"{self.base_url}/models", {"Authorization": f"Bearer {self.config.api_key}"})
        except ProviderError:
            return [self.default_model]
        ids = [m["id"] for m in data.get("data", [])]
        return sorted((i for i in ids if i.startswith(CHAT_MODEL_PREFIXES)), reverse=True) or [self.default_model]

    def chat(self, messages: list[Message], *, model: str | None = None, effort: str = "low",
             max_output_tokens: int = MAX_OUTPUT_TOKENS) -> ChatReply:
        model = model or self.default_model
        data = self._respond({"model": model, "input": self.to_responses_input(messages),
                              "max_output_tokens": max_output_tokens, "reasoning": {"effort": effort}})
        note = None
        if data.get("status") == "incomplete":
            note = f"incomplete: {(data.get('incomplete_details') or {}).get('reason', 'unknown')}"
        return ChatReply(self.output_text(data), self._usage(data), data.get("model", model), note)

    def complete_json(self, messages: list[Message], schema: dict[str, Any], schema_name: str, *,
                      effort: str = "low", model: str | None = None) -> tuple[dict[str, Any], Usage]:
        data = self._respond({
            "model": model or self.default_model, "input": self.to_responses_input(messages),
            "max_output_tokens": MAX_OUTPUT_TOKENS, "reasoning": {"effort": effort},
            "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        })
        if data.get("status") == "incomplete":  # cut off: say why, instead of failing inside json.loads
            reason = (data.get("incomplete_details") or {}).get("reason", "unknown")
            raise ProviderError(self.name, f"no complete JSON in the reply (incomplete: {reason})")
        text = self.output_text(data)
        try:
            return json.loads(text), self._usage(data)
        except ValueError as exc:
            raise ProviderError(self.name, f"the reply was not valid JSON ({exc}): {text[:200]!r}") from None

    @staticmethod
    def to_responses_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Chat Completions tool definitions (nested under ``function``) -> the flat Responses form."""
        return [{"type": "function", **t["function"]} if "function" in t else t for t in tools]

    @staticmethod
    def tool_calls(data: dict[str, Any]) -> list[ToolCall]:
        return [ToolCall(id=item["call_id"], name=item["name"], arguments=item.get("arguments") or "{}")
                for item in data.get("output", []) if item.get("type") == "function_call"]

    def call_tools(self, messages: list[Message], tools: list[dict[str, Any]], *, effort: str = "low",
                   model: str | None = None) -> tuple[ToolTurn, Usage]:
        data = self._respond({"model": model or self.default_model, "input": self.to_responses_input(messages),
                              "tools": self.to_responses_tools(tools), "max_output_tokens": MAX_OUTPUT_TOKENS,
                              "reasoning": {"effort": effort}})
        return ToolTurn(self.output_text(data) or None, self.tool_calls(data)), self._usage(data)
