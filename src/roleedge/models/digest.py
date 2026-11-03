"""What Saathi produces from one shared item (reel, photo, long message), and the checker's report.

Field order matters: it is the order of the JSON Schema the model must fill (see llm/schema.py).
Fields ending in ``_local`` and everything under regional / illustration / storyboard /
voice_note_script / reply_suggestions are written in the recipient's language; the rest is
English for the sender's review.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator

TrustVerdict = Literal["looks_genuine", "unverified", "likely_scam_or_misleading"]
# Pictograms are line icons picked by name (render/icons.py draws them); never emoji.
IconName = Literal["phone", "video", "calendar", "clock", "bell", "document", "bill", "money", "bank", "card", "id",
                   "shield", "warning", "lock", "check", "cross", "info", "question", "person", "family", "home",
                   "hospital", "medicine", "heart", "school", "book", "chat", "mail", "location", "food", "cart",
                   "link", "key", "mobile", "checklist"]
CardLayout = Literal["steps", "checklist", "timeline", "warning"]


class KeyPoint(BaseModel):
    icon: IconName
    text: str


class Trust(BaseModel):
    verdict: TrustVerdict
    reason: str  # English, for the sender
    advice_local: str  # recipient's language


_CLOCK = re.compile(r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*(?:([ap])\.?\s*m\.?)?\s*", re.IGNORECASE)
_JA_CLOCK = re.compile(r"\s*(午前|午後)?(\d{1,2})時(?:(\d{1,2})分|(半))?\s*")


def normalize_time(value: Any) -> Any:
    """'10:00 AM', '6 pm', '18.30', '午後5時', '10時半' -> 'HH:MM' (same time, one format). Anything else is
    returned as written: a time is never guessed (rule S2), and the calendar copes with what it can't read."""
    if not isinstance(value, str):
        return value
    if m := _JA_CLOCK.fullmatch(value):
        hour, minute, half = int(m[2]), 30 if m[4] else int(m[3] or 0), {"午前": "a", "午後": "p"}.get(m[1] or "", "")
    elif (m := _CLOCK.fullmatch(value)) and (m[2] or m[3]):  # a bare "10" is too vague
        hour, minute, half = int(m[1]), int(m[2] or 0), (m[3] or "").lower()
    else:
        return value
    if half:
        if not 1 <= hour <= 12:
            return value
        hour = hour % 12 + (12 if half == "p" else 0)
    return f"{hour:02d}:{minute:02d}" if hour <= 23 and minute <= 59 else value


_MONTHS = {name: n for n, names in enumerate(
    ["jan january", "feb february", "mar march", "apr april", "may", "jun june", "jul july", "aug august",
     "sep sept september", "oct october", "nov november", "dec december"], start=1) for name in names.split()}
_YMD = re.compile(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?")
_D_MON_Y = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?,?\s+(\d{4})")
_MON_D_Y = re.compile(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})")
_NUMERIC = re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})")


def is_iso_date(value: Any) -> bool:
    """True for a real calendar date written YYYY-MM-DD."""
    try:
        return isinstance(value, str) and len(value) == 10 and bool(date.fromisoformat(value))
    except ValueError:
        return False


def normalize_date(value: Any) -> Any:
    """'2026/11/20', '2026年11月20日', '20 Nov 2026', 'November 20, 2026', '20/11/2026' -> '2026-11-20' (same date,
    one format). Ambiguous, incomplete or impossible dates ('05/11/2026', '20 Nov', '2026-02-30') are returned as
    written: a date is never guessed (rule S2); the content step holds them for the sender."""
    if not isinstance(value, str) or is_iso_date(value):
        return value
    text = unicodedata.normalize("NFKC", value).strip().lower()  # full-width digits -> ASCII
    ymd = None
    if m := _YMD.fullmatch(text):
        ymd = int(m[1]), int(m[2]), int(m[3])
    elif (m := _D_MON_Y.fullmatch(text)) and m[2] in _MONTHS:
        ymd = int(m[3]), _MONTHS[m[2]], int(m[1])
    elif (m := _MON_D_Y.fullmatch(text)) and m[1] in _MONTHS:
        ymd = int(m[3]), _MONTHS[m[1]], int(m[2])
    elif m := _NUMERIC.fullmatch(text):
        first, second = int(m[1]), int(m[2])
        if first > 12 >= second:
            ymd = int(m[3]), second, first  # 20/11/2026: day first
        elif second > 12 >= first:
            ymd = int(m[3]), first, second  # 11/20/2026: month first
    try:
        return date(*ymd).isoformat() if ymd else value
    except ValueError:
        return value


class Action(BaseModel):
    title: str
    title_local: str
    due_date: Annotated[str | None, BeforeValidator(normalize_date)]  # YYYY-MM-DD
    due_time: Annotated[str | None, BeforeValidator(normalize_time)]  # HH:MM
    how: str
    remind_days_before: list[int]
    add_to_calendar: bool


class Regional(BaseModel):
    language: str
    title: str
    summary: list[str]
    article: str


class Panel(BaseModel):
    icon: IconName
    heading: str
    caption: str


class Illustration(BaseModel):
    layout: CardLayout
    headline: str
    panels: list[Panel]


class Scene(BaseModel):
    icon: IconName
    big_text: str
    caption: str
    narration: str
    seconds: int


class Digest(BaseModel):
    title: str
    one_line: str
    simple_summary: list[str]
    key_points: list[KeyPoint]
    trust: Trust
    actions: list[Action]
    regional: Regional
    illustration: Illustration
    storyboard: list[Scene]
    voice_note_script: str
    reply_suggestions: list[str]

    @property
    def is_scam(self) -> bool:
        return self.trust.verdict == "likely_scam_or_misleading"


# ---------------------------------------------------------------- checker


class VerifyIssue(BaseModel):
    path: str  # JSON path into the digest, e.g. "storyboard[2].narration"
    severity: Literal["minor", "major"]
    problem: str
    corrected_text: str


class VerifyReport(BaseModel):
    issues: list[VerifyIssue]


class ReviewedIssue(VerifyIssue):
    """A checker issue plus what the pipeline did with it."""

    needs_review: bool = False  # True: held for the sender (dates are never changed automatically)
    applied: bool = False


# ---------------------------------------------------------------- saved record


class DigestRecord(BaseModel):
    """Everything saved to output/content/<case>/digest.json."""

    case: str
    recipient: str
    input: str
    media_count: int
    digest: Digest  # after safe fixes were applied
    draft_before_verify: Digest
    verify_issues: list[ReviewedIssue]
    usage: dict[str, int]
    latency_s: float
    cached: bool
    verify_usage: dict[str, int]
    verify_latency_s: float

    @property
    def held_action_indexes(self) -> set[int]:
        """Actions whose date the checker questioned: they wait for the sender's approval."""
        import re

        held = set()
        for issue in self.verify_issues:
            match = re.search(r"actions\[(\d+)\]", issue.path)
            if issue.needs_review and match:
                held.add(int(match.group(1)))
        return held
