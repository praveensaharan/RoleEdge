"""Urgent statements found by code, so a model that misses one can never lower the alert (same idea as rule S3)."""

from __future__ import annotations

import re
import unicodedata

_I = re.IGNORECASE
RED_FLAGS: dict[str, list[re.Pattern[str]]] = {
    "fall": [re.compile(r"\b(i|i've|i have)\s+(fell|fallen|had a fall|tripped and fell)\b|\bfell (down|over)\b", _I),
             re.compile(r"転んだ|転倒|倒れた|こけた")],
    "chest_pain": [re.compile(r"\bchest\b.{0,20}\b(pain|hurts?|tight|pressure)\b|\bpain in my chest\b", _I),
                   re.compile(r"胸が(痛|苦し|締め)")],
    "breathless": [re.compile(r"\b(can'?t|cannot|hard to|trouble) breath(e|ing)\b|\bshort of breath\b", _I),
                   re.compile(r"息が(苦し|でき|しづら)")],
    "fainted": [re.compile(r"\b(fainted|passed out|blacked out)\b", _I), re.compile(r"気を失|意識がな")],
    "confused": [re.compile(r"\b(don'?t know where i am|can'?t remember where i am)\b", _I),
                 re.compile(r"ここがどこか(わから|分から)")],
}


def red_flags(text: str) -> list[str]:
    """Urgent kinds named in ``text`` (English or Japanese)."""
    normal = unicodedata.normalize("NFKC", text)
    return [kind for kind, patterns in RED_FLAGS.items() if any(p.search(normal) for p in patterns)]
