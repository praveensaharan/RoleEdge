"""Request/response shapes of the chat playground API (what web/chat/js/api.js sends and reads)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..llm import Message


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = ""
    images: list[str] = Field(default_factory=list)  # data: URLs


class ChatRequest(BaseModel):
    provider: str
    model: str
    effort: str = "low"
    system: str = ""
    messages: list[ChatMessageIn]

    def to_messages(self) -> list[Message]:
        """Browser history -> canonical Chat Completions messages."""
        out: list[Message] = [{"role": "system", "content": self.system}] if self.system.strip() else []
        for m in self.messages:
            if m.role == "user" and m.images:
                parts = [{"type": "text", "text": m.text or "(see image)"}]
                parts += [{"type": "image_url", "image_url": {"url": url}} for url in m.images]
                out.append({"role": "user", "content": parts})
            else:
                out.append({"role": m.role, "content": m.text})
        return out


class ChatResponse(BaseModel):
    text: str
    usage: dict[str, int]
    model: str
    note: str | None
    latency_s: float


class ProviderInfo(BaseModel):
    id: str
    label: str
    models: list[str]  # empty when the provider is not configured
    efforts: list[str]


class ModelsResponse(BaseModel):
    providers: list[ProviderInfo]
    defaults: dict[str, str]
