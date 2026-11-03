"""Compose one message for the parent. The send gate (``gates``) runs on the result before it can be sent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..llm import LLM
from ..models import Circle, ParentMessage, TraceStep, VoiceChoice
from .prompts import COMPOSE_SYSTEM, COMPOSE_USER, INTENT_SYSTEM, LANGUAGE_RULES, VOICE_ASSISTANT, VOICE_MINE


class ShareIntent(BaseModel):
    kind: Literal["message", "explain"]
    reason_en: str  # a few words, shown to the caregiver


def read_intent(llm: LLM, circle: Circle, text: str) -> tuple[ShareIntent, TraceStep]:
    """One quick call: a message to pass on, or something to explain. Anything unexpected counts as "explain", the
    careful path."""
    caregiver = circle.caregiver.call_name
    messages = [{"role": "system", "content": INTENT_SYSTEM.format(caregiver=caregiver, parent_call=circle.parent.call_name)},
                {"role": "user", "content": COMPOSE_USER.format(caregiver=caregiver, text=text.strip())}]
    try:
        result = llm.complete_json("intent", messages, ShareIntent, "share_intent", effort="low")
        intent = ShareIntent.model_validate(result.data)
        latency, cached = result.latency_s, result.cached
    except Exception:  # noqa: BLE001 - a failed guess must never block the share
        intent, latency, cached = ShareIntent(kind="explain", reason_en="could not tell"), 0.0, False
    step = TraceStep(step=f"Read what you meant: {'a message to pass on' if intent.kind == 'message' else 'something to explain'}"
                          f" ({intent.reason_en})", engine=llm.engine, latency_s=latency, replayed=cached)
    return intent, step


def compose(llm: LLM, circle: Circle, text: str, voice: VoiceChoice) -> tuple[ParentMessage, TraceStep]:
    caregiver, parent = circle.caregiver.call_name, circle.parent
    voice_rule = (VOICE_MINE if voice == "mine" else VOICE_ASSISTANT).format(caregiver=caregiver)
    system = COMPOSE_SYSTEM.format(
        caregiver=caregiver, parent_call=parent.local_name, parent_name=parent.name, age=parent.age or "",
        language=parent.language_name, voice_rule=voice_rule, language_rule=LANGUAGE_RULES[parent.language],
        names=f"{parent.local_name} and {caregiver}")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": COMPOSE_USER.format(caregiver=caregiver, text=text.strip())}]
    result = llm.complete_json("compose", messages, ParentMessage, "parent_message", effort="low")
    message = ParentMessage.model_validate(result.data)
    step = TraceStep(step=f"Rewrote it for {parent.call_name} ({parent.language_name})", engine=llm.engine,
                     latency_s=result.latency_s, replayed=result.cached)
    return message, step
