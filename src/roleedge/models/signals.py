"""Everyday-life signals from the parent's replies and check-ins, and the trend report built from them.

Two speeds (PIVOT.md 2.1): a ``TodaySignal`` comes from one conversation and goes straight into the caregiver's
summary; a trend needs weeks and is computed by code in ``trends/`` from stored ``SignalEvent``s.

The model only reports what she said (with her exact words as evidence). It never interprets health; that rule
also keeps the project clear of "AI medical advice".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Area = Literal["eating", "sleep", "medicine", "body", "mood", "memory", "social", "routine", "home"]
SignalKind = Literal[
    "meal_skipped", "not_hungry", "little_water", "slept_badly", "napped_a_lot", "missed_medicine",
    "unwell", "pain", "dizzy", "low_energy", "low_mood", "lonely", "worried", "unsure_of_day",
    "forgot_plan", "repeated_question", "stayed_in", "talked_to_nobody", "went_out", "saw_someone",
    "fall", "chest_pain", "breathless", "fainted", "confused", "other",
]
Lane = Literal["tonight", "staples", "medicine"]

AREA_OF: dict[str, str] = {
    "meal_skipped": "eating", "not_hungry": "eating", "little_water": "eating",
    "slept_badly": "sleep", "napped_a_lot": "sleep", "missed_medicine": "medicine",
    "unwell": "body", "pain": "body", "dizzy": "body", "low_energy": "body",
    "low_mood": "mood", "lonely": "mood", "worried": "mood",
    "unsure_of_day": "memory", "forgot_plan": "memory", "repeated_question": "memory",
    "stayed_in": "social", "talked_to_nobody": "social", "went_out": "social", "saw_someone": "social",
    "fall": "body", "chest_pain": "body", "breathless": "body", "fainted": "body", "confused": "memory",
    "other": "routine",
}
URGENT_KINDS = frozenset({"fall", "chest_pain", "breathless", "fainted", "confused"})
POSITIVE_KINDS = frozenset({"went_out", "saw_someone"})


class TodaySignal(BaseModel):
    kind: SignalKind
    observation: str  # plain English, what she reported, no interpretation ("Skipped lunch today")
    quote: str  # her exact words (in her language) that support it


class Need(BaseModel):
    item: str  # in English, e.g. "onions"
    item_local: str  # in the parent's language
    lane: Lane
    quantity: str  # e.g. "3", "1 bag"; "" when not said
    quote: str  # her words that show the need


class ReplyReading(BaseModel):
    """The reply reader's contract: what the caregiver needs to know from one reply."""

    summary_for_caregiver: str  # max 2 sentences, English
    signals: list[TodaySignal]
    needs: list[Need]
    question_for_caregiver: str  # something she asked that needs the caregiver; "" if none
    reply_to_parent: str  # a short, warm acknowledgement in her language, spoken by the assistant
    reply_to_parent_english: str  # the same acknowledgement in English (caregiver preview, demo subtitles)


class SignalEvent(BaseModel):
    """A stored signal: one day, one kind, with the evidence behind it."""

    day: str  # ISO date
    kind: SignalKind
    area: Area
    quote: str = ""
    source: Literal["reply", "checkin", "voice", "app", "synthetic"] = "reply"


class VoiceDay(BaseModel):
    """Measured voice features for one day (averaged over her replies)."""

    day: str
    speech_rate_wpm: float  # words per minute
    pause_ratio: float  # share of the reply that is silence, 0..1
    reply_seconds: float  # average length of a voice reply


class TrendLine(BaseModel):
    key: str  # e.g. "meal_skipped" or "speech_rate_wpm"
    label: str  # plain words, e.g. "Skipped meals"
    unit: str  # e.g. "per week", "words per minute"
    baseline: float
    recent: float
    flagged: bool
    direction: Literal["up", "down", "steady"]
    evidence: list[SignalEvent] = Field(default_factory=list)  # recent events behind a flag (dates + her words)


class TrendReport(BaseModel):
    circle_id: str
    as_of: str  # ISO date
    baseline_days: int
    recent_days: int
    level: Literal["steady", "small_change", "sustained_change", "worth_a_visit"]
    flagged_areas: list[str]
    lines: list[TrendLine]
    family_steps: list[str]  # chosen by code from the level (never by the model)
    resources: list[dict[str, str]] = Field(default_factory=list)  # e.g. visit notes, local support centre
