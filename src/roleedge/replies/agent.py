"""Read one reply: a model call fills ``ReplyReading``; code adds red flags, the alert level and storable events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

from ..llm import LLM
from ..models import AREA_OF, URGENT_KINDS, Circle, ReplyReading, SignalEvent, SignalKind, TodaySignal, TraceStep
from .flags import red_flags
from .prompts import REPLY_SYSTEM, REPLY_USER

WATCH_KINDS = frozenset({"missed_medicine", "unwell", "pain", "dizzy", "meal_skipped", "lonely", "low_mood"})
Alert = Literal["none", "watch", "urgent"]


@dataclass
class ReadReply:
    reading: ReplyReading
    alert: Alert
    events: list[SignalEvent]
    trace: list[TraceStep] = field(default_factory=list)


def read_reply(llm: LLM, circle: Circle, text: str, *, day: str, context: list[str] | None = None) -> ReadReply:
    parent, caregiver = circle.parent, circle.caregiver.call_name
    kinds = ", ".join(k for k in get_args(SignalKind) if k != "other")
    system = REPLY_SYSTEM.format(parent_call=parent.call_name, caregiver=caregiver, age=parent.age or "",
                                 kinds=kinds, language=parent.language_name,
                                 context="\n".join(context or []) or "(none)")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": REPLY_USER.format(parent_call=parent.call_name, text=text.strip())}]
    result = llm.complete_json("reply", messages, ReplyReading, "reply_reading", effort="low")
    reading = ReplyReading.model_validate(result.data)
    trace = [TraceStep(step=f"Read {parent.call_name}'s reply", engine=llm.engine, latency_s=result.latency_s,
                       replayed=result.cached)]

    found_kinds = {s.kind for s in reading.signals}
    for kind in red_flags(text):  # code catches what the model may have missed
        if kind not in found_kinds:
            reading.signals.append(TodaySignal(kind=kind, observation=f"Said something urgent ({kind.replace('_', ' ')})",
                                               quote=text.strip()[:200]))
    trace.append(TraceStep(step="Checked for urgent words (fall, chest pain, breathing, fainting)", engine="code"))

    kinds_now = {s.kind for s in reading.signals}
    alert: Alert = "urgent" if kinds_now & URGENT_KINDS else "watch" if kinds_now & WATCH_KINDS else "none"
    events = [SignalEvent(day=day, kind=s.kind, area=AREA_OF.get(s.kind, "routine"), quote=s.quote, source="reply")
              for s in reading.signals]
    return ReadReply(reading, alert, events, trace)
