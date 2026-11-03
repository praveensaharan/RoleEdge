"""Azure OpenAI (Foundry) via the OpenAI-compatible v1 Chat Completions endpoint. Used for development."""

from __future__ import annotations

import json
from typing import Any

from ..config import AzureConfig
from .base import MAX_OUTPUT_TOKENS, Provider
from .http import get_json, post_json
from .types import ChatReply, Message, ProviderError, ToolCall, ToolTurn, Usage

# Deployments whose underlying model is not a chat model.
NON_CHAT_MODELS = ("embedding", "whisper", "dall-e", "tts")


class AzureProvider(Provider):
    name = "azure"
    label = "Azure OpenAI"
    efforts = ("minimal", "low", "medium", "high")

    def __init__(self, config: AzureConfig) -> None:
        self.config = config

    @property
    def default_model(self) -> str:
        return self.config.deployment

    # ---------------------------------------------------------------- requests

    def _completions(self, model: str | None, body: dict[str, Any]) -> dict[str, Any]:
        return post_json(self.name, f"{self.config.endpoint}/openai/v1/chat/completions",
                         {"model": model or self.default_model, **body}, {"api-key": self.config.api_key})

    def _first_choice(self, data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0].get("message"), dict):
            raise ProviderError(self.name, f"the reply had no choices: {str(data)[:200]}")
        return choices[0]

    @staticmethod
    def _usage(data: dict[str, Any]) -> Usage:
        u = data.get("usage") or {}
        return Usage(input=u.get("prompt_tokens", 0),
                     cached=(u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                     output=u.get("completion_tokens", 0),
                     reasoning=(u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0)

    # ---------------------------------------------------------------- Provider API

    def list_models(self) -> list[str]:
        try:
            data = get_json(self.name, f"{self.config.endpoint}/openai/deployments", {"api-key": self.config.api_key},
                            params={"api-version": "2022-12-01"})
        except ProviderError:
            return [self.default_model]
        deployments = [d["id"] for d in data.get("data", [])
                       if d.get("status") == "succeeded" and not any(s in d.get("model", "") for s in NON_CHAT_MODELS)]
        return deployments or [self.default_model]

    def chat(self, messages: list[Message], *, model: str | None = None, effort: str = "low",
             max_output_tokens: int = MAX_OUTPUT_TOKENS) -> ChatReply:
        data = self._completions(model, {"messages": messages, "max_completion_tokens": max_output_tokens,
                                         "reasoning_effort": effort})
        choice = self._first_choice(data)
        finish = choice.get("finish_reason")
        return ChatReply(text=choice["message"].get("content") or "", usage=self._usage(data),
                         model=data.get("model", model or self.default_model),
                         note=None if finish in (None, "stop") else f"finish_reason: {finish}")

    def complete_json(self, messages: list[Message], schema: dict[str, Any], schema_name: str, *,
                      effort: str = "low", model: str | None = None) -> tuple[dict[str, Any], Usage]:
        data = self._completions(model, {
            "messages": messages, "reasoning_effort": effort, "max_completion_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
        })
        choice = self._first_choice(data)
        content, finish = choice["message"].get("content"), choice.get("finish_reason")
        if not content or finish == "length":  # cut off, filtered or refused: say which, not a json.loads crash
            refusal = choice["message"].get("refusal")
            raise ProviderError(self.name, f"no complete JSON in the reply (finish_reason: {finish}"
                                + (f"; refusal: {refusal}" if refusal else "") + ")")
        try:
            return json.loads(content), self._usage(data)
        except ValueError as exc:
            raise ProviderError(self.name, f"the reply was not valid JSON ({exc}): {content[:200]!r}") from None

    def call_tools(self, messages: list[Message], tools: list[dict[str, Any]], *, effort: str = "low",
                   model: str | None = None) -> tuple[ToolTurn, Usage]:
        data = self._completions(model, {"messages": messages, "tools": tools, "tool_choice": "auto",
                                         "reasoning_effort": effort, "max_completion_tokens": 8000})
        message = self._first_choice(data)["message"]
        calls = [ToolCall(c["id"], c["function"]["name"], c["function"]["arguments"])
                 for c in (message.get("tool_calls") or [])]
        return ToolTurn(message.get("content"), calls), self._usage(data)
