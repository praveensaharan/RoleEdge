"""Plain data types shared by every provider and by the LLM client.

Messages use the OpenAI Chat Completions shape everywhere inside the codebase:

    {"role": "system" | "user" | "assistant" | "tool", "content": str | list[part], ...}
    part = {"type": "text", "text": ...} | {"type": "image_url", "image_url": {"url": "data:..."}}

Providers convert to their own wire format at the edge (see meta.py).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Generic, TypeVar

Message = dict[str, Any]
T = TypeVar("T")


@dataclass(frozen=True)
class Usage:
    """Token counts for one call. ``cached`` is part of ``input``; ``reasoning`` is part of ``output``."""

    input: int = 0
    cached: int = 0
    output: int = 0
    reasoning: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(self.input + other.input, self.cached + other.cached,
                     self.output + other.output, self.reasoning + other.reasoning)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Usage:
        return cls(**{k: int(data.get(k, 0) or 0) for k in ("input", "cached", "output", "reasoning")})


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text exactly as the model produced it

    def parsed_arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments or "{}")


@dataclass(frozen=True)
class ToolTurn:
    """One assistant turn in a tool-calling conversation: spoken text and/or tool calls."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"content": self.content, "tool_calls": [asdict(c) for c in self.tool_calls]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolTurn:
        return cls(data.get("content"), [ToolCall(**c) for c in data.get("tool_calls", [])])

    def as_assistant_message(self) -> Message:
        """The message to append to the history so the model sees its own turn."""
        message: Message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                                     for c in self.tool_calls]
        return message


@dataclass(frozen=True)
class ChatReply:
    text: str
    usage: Usage
    model: str
    note: str | None = None  # e.g. "incomplete: max_output_tokens"


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    data: T
    usage: Usage
    cached: bool  # True when replayed from the on-disk cache (no API call, no cost)
    latency_s: float


class ProviderError(RuntimeError):
    """The provider answered with an error, or could not be reached."""

    def __init__(self, provider: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status = status
