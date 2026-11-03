"""The provider interface. Add a provider by subclassing ``Provider`` and registering it in providers.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .types import ChatReply, Message, ToolTurn, Usage

MAX_OUTPUT_TOKENS = 16000  # includes hidden reasoning tokens, so keep generous


class Provider(ABC):
    name: str  # stable id used in config, cache keys and the API ("azure", "meta")
    label: str  # human name for the UI
    efforts: tuple[str, ...]  # reasoning-effort values this provider accepts

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Model ids usable for chat. Falls back to the default model if listing fails."""

    @abstractmethod
    def chat(self, messages: list[Message], *, model: str | None = None, effort: str = "low",
             max_output_tokens: int = MAX_OUTPUT_TOKENS) -> ChatReply:
        """Plain conversation turn; returns the assistant's text."""

    @abstractmethod
    def complete_json(self, messages: list[Message], schema: dict[str, Any], schema_name: str, *,
                      effort: str = "low", model: str | None = None) -> tuple[dict[str, Any], Usage]:
        """Structured output: the reply is JSON that matches ``schema`` (strict mode)."""

    @abstractmethod
    def call_tools(self, messages: list[Message], tools: list[dict[str, Any]], *, effort: str = "low",
                   model: str | None = None) -> tuple[ToolTurn, Usage]:
        """One tool-calling turn: the model may speak, call tools, or both."""

    def check(self) -> ChatReply:
        """Cheapest possible request, to confirm the key and model work."""
        return self.chat([{"role": "user", "content": "Reply with just: OK"}], effort="minimal", max_output_tokens=200)
