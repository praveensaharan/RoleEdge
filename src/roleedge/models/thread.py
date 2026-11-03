"""What travels between the caregiver and the parent, and the record of how it was made.

``ParentMessage`` is the composer's output contract (field order = the order the model fills it, rule A4).
``ThreadItem`` is what the app stores and both screens render. ``TraceStep`` is one line of the activity log, so the
demo can show which model did each step.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Speaker = Literal["person", "assistant"]  # T4: the parent can always tell the caregiver's words from the agent's
ItemKind = Literal["message", "reply", "summary", "trend", "order", "alert", "answer", "approval", "checkin", "reel",
                   "studio", "relay"]
ItemStatus = Literal["draft", "held", "approved", "sent", "played", "answered", "done"]


class ParentMessage(BaseModel):
    """A message rewritten for the parent: spoken words first, then what her screen shows."""

    spoken_text: str  # what the voice says, in the parent's language, warm and short
    screen_title: str  # 2-6 words, in the parent's language
    steps: list[str]  # 0-5 short steps when there is something to do, in the parent's language
    quick_replies: list[str]  # 2-4 big one-tap replies, in the parent's language
    english_gloss: str  # the same message in plain English, for the caregiver's preview and demo subtitles


class GateResult(BaseModel):
    """The final send gate's verdict (PIVOT.md T5). Code decides, not a model."""

    passed: bool
    reasons: list[str] = Field(default_factory=list)  # plain-language, shown to the caregiver when held
    rules: list[str] = Field(default_factory=list)  # rule ids, e.g. "money", "link"


class TraceStep(BaseModel):
    """One step of how an item was made, for the activity log."""

    step: str  # plain words, e.g. "Rewrote for Okaasan"
    engine: str  # e.g. "azure/gpt5mini", "meta/muse-spark-1.3", "code", "browser voice"
    latency_s: float = 0.0
    replayed: bool = False  # served from the recorded-run cache


class ThreadItem(BaseModel):
    id: str
    circle_id: str
    at: str  # ISO timestamp
    kind: ItemKind
    to: Literal["parent", "caregiver", "child"]
    speaker: Speaker
    status: ItemStatus
    voice: Literal["mine", "assistant", "none"] = "none"
    payload: dict[str, Any] = Field(default_factory=dict)
    gate: GateResult | None = None
    trace: list[TraceStep] = Field(default_factory=list)
