"""Compose one message for the parent. The send gate (``gates``) runs on the result before it can be sent."""

from __future__ import annotations

from ..llm import LLM
from ..models import Circle, ParentMessage, TraceStep, VoiceChoice
from .prompts import COMPOSE_SYSTEM, COMPOSE_USER, LANGUAGE_RULES, VOICE_ASSISTANT, VOICE_MINE


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
