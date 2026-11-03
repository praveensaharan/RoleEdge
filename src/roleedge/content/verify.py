"""The checker: a second model call compares what the recipient will see against the source, and
the fix policy decides what may change automatically.

Policy (see ARCHITECTURE.md, rule S2): wording fixes are applied automatically; dates and times
are never changed by the checker - those issues are held for the sender's review instead.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from ..llm import LLM, LLMResult
from ..models import Recipient, ReviewedIssue, VerifyIssue, VerifyReport, is_iso_date, normalize_date
from ..models.digest import normalize_time
from .ingest import ContentItem, image_part
from .prompts import VERIFY_SYSTEM

STRUCTURED_FIELDS = ("due_date", "due_time")


def recipient_view(draft: dict[str, Any]) -> dict[str, Any]:
    """Only the parts the recipient sees - that is what gets checked."""
    view = {k: draft[k] for k in ("regional", "illustration", "storyboard", "voice_note_script", "reply_suggestions")}
    view["actions"] = [{"title_local": a["title_local"], "due_date": a["due_date"], "due_time": a["due_time"]}
                       for a in draft["actions"]]
    view["trust_advice_local"] = draft["trust"]["advice_local"]
    return view


def run_checker(llm: LLM, case_id: str, item: ContentItem, draft: dict[str, Any], recipient: Recipient,
                today: str) -> LLMResult[dict[str, Any]]:
    system = VERIFY_SYSTEM.format(people=recipient.known_people(), sender=recipient.sender,
                                  language=recipient.language, script=recipient.script, today=today)
    parts = [{"type": "text", "text": "SOURCE:\n" + item.text}] + [image_part(p) for p in item.images]
    parts.append({"type": "text", "text": "DRAFT:\n" + json.dumps(recipient_view(draft), ensure_ascii=False, indent=1)})
    return llm.complete_json(f"verify/{case_id}", [{"role": "system", "content": system},
                                                   {"role": "user", "content": parts}], VerifyReport, "verify")


def apply_fixes(draft: dict[str, Any], issues: list[VerifyIssue]) -> list[ReviewedIssue]:
    """Apply safe fixes to ``draft`` in place; return every issue with what happened to it.

    A fix is held for the sender instead when it targets a date or time field, or when it would change a
    date or time written in the text (e.g. "12 नवंबर" -> "15 नवंबर" in the article). Rewording around
    a date ("12-Nov" -> "12 नवम्बर") is still applied.
    """
    reviewed = []
    for issue in issues:
        r = ReviewedIssue(**issue.model_dump())
        path = issue.path.replace("trust_advice_local", "trust.advice_local")
        if (any(f in issue.path for f in STRUCTURED_FIELDS)
                or date_mentions(get_text(draft, path)) != date_mentions(issue.corrected_text)):
            r.needs_review = True
        else:
            r.applied = set_path(draft, path, issue.corrected_text)
        reviewed.append(r)
    return reviewed


def unreadable_dates(draft: dict[str, Any]) -> list[ReviewedIssue]:
    """Actions whose date the app can't read (not YYYY-MM-DD, even after normalize_date): held for the sender,
    like a questioned date (rule S2), so they never reach a calendar or card as a guess."""
    held = []
    for index, action in enumerate(draft.get("actions") or []):
        written = normalize_date(action.get("due_date"))
        if written is not None and not is_iso_date(written):
            held.append(ReviewedIssue(path=f"actions[{index}].due_date", severity="major", corrected_text=str(written),
                                      problem=f"The date {written!r} isn't one the app can read, so it waits for the "
                                              "sender.", needs_review=True))
    return held


def set_path(doc: dict[str, Any], path: str, value: str) -> bool:
    """Replace the text addressed like ``storyboard[2].narration``. Returns False, changing nothing, unless
    the path leads to existing text: a whole scene, action or list, a number, or a missing field is never
    replaced. "null" (the checker's way to delete a date, and dates are held) never deletes text."""
    tokens = re.findall(_PATH_TOKEN, path)
    if not tokens or value.strip().lower() == "null":
        return False
    try:
        node = _walk(doc, tokens[:-1])
        key: Any = int(tokens[-1][1:-1]) if tokens[-1].startswith("[") else tokens[-1]
        if isinstance(node, list if isinstance(key, int) else dict) and isinstance(node[key], str):
            node[key] = value
            return True
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return False


def get_text(doc: dict[str, Any], path: str) -> str:
    """The text at ``path``, or "" if the path does not lead to text."""
    try:
        value = _walk(doc, re.findall(_PATH_TOKEN, path))
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    return value if isinstance(value, str) else ""


_PATH_TOKEN = r"[A-Za-z_]+|\[\d+\]"


def _walk(node: Any, tokens: list[str]) -> Any:
    for token in tokens:
        node = node[int(token[1:-1])] if token.startswith("[") else node[token]
    return node


# ---------------------------------------------------------------- dates written in text (rule S2)
# Words are mapped to one code per meaning, so "Nov" and "नवम्बर" (or "Friday", "शुक्रवार" and "金曜日") compare equal.

_DATE_WORDS = {code: words.split() for code, words in {
    "M1": "january jan जनवरी", "M2": "february feb फरवरी", "M3": "march mar मार्च",
    "M4": "april apr अप्रैल अप्रेल", "M5": "may मई", "M6": "june jun जून", "M7": "july jul जुलाई",
    "M8": "august aug अगस्त", "M9": "september sept sep सितंबर सितम्बर", "M10": "october oct अक्टूबर अक्तूबर",
    "M11": "november nov नवंबर नवम्बर", "M12": "december dec दिसंबर दिसम्बर",
    "D1": "monday सोमवार", "D2": "tuesday मंगलवार", "D3": "wednesday बुधवार", "D4": "thursday गुरुवार बृहस्पतिवार",
    "D5": "friday शुक्रवार", "D6": "saturday शनिवार", "D7": "sunday रविवार",
    "R0": "today आज", "R1": "tomorrow yesterday कल", "R2": "परसों",
    "P1": "morning सुबह", "P2": "afternoon noon दोपहर", "P3": "evening शाम", "P4": "night tonight रात",
}.items()}
_CODE = {word: code for code, words in _DATE_WORDS.items() for word in words}
_JA_WORDS = re.compile("明後日|一昨日|今日|明日|昨日|今夜|今晩|[月火水木金土日]曜日?")
_JA_CODE = {"今日": "R0", "明日": "R1", "昨日": "R1", "明後日": "R2", "一昨日": "R2", "今夜": "P4", "今晩": "P4"}
_LETTERS = r"[a-z\u0900-\u0963\u0971-\u097f]+"  # Devanagari without dandas and digits
_NORMALISE = str.maketrans("०१२३४५६७८९\u2010\u2011\u2012\u2013\u2014\u2212", "0123456789------", "\u093c")
_MENTION = re.compile(r"""
    (?<!\d)\d{1,4}年(?:\d{1,2}月)?(?:\d{1,2}日)?                       # 2026年11月20日
  | (?<!\d)\d{1,2}月(?:\d{1,2}日)?                                    # 11月20日, 11月
  | (?<!\d)\d{1,2}日                                                   # 20日
  | (?:午前|午後)?(?<!\d)\d{1,2}時(?:\d{1,2}分|半)?                    # 午後5時, 10時30分, 10時半
  | (?<!\d)(?:\d{1,4}\s*-?\s*)?M\d+(?:\s*[-,]?\s*\d{1,4}(?![\d:]))?   # 12 Nov 2026, November 14, नवम्बर
  | (?<!\d)\d{1,2}(?::\d{2})?\s*(?:am|pm)(?![a-z])                    # 6 pm, 9:30 am
  | (?:\d{1,2}(?::\d{2})?|""" + _LETTERS + r""")\s*बजे                   # 6 बजे, डेढ़ बजे
  | (?<!\d)\d{1,2}:\d{2}                                               # 18:00
  | (?<!\d)\d{1,4}[-/.]\d{1,2}(?:[-/.]\d{2,4})?(?!\d)                   # 2026-11-12, 12/11, 05-11-2026, 1-30
  | [DRP]\d                                                            # weekday, today/tomorrow, evening
""", re.VERBOSE)


def date_mentions(text: str) -> list[str]:
    """The dates and times written in ``text``, in one canonical form, sorted. Two texts give the same
    list when they say the same dates and times, whatever the format or language of the words."""
    found = []
    for match in _MENTION.finditer(_normalise(text)):
        mention = re.sub(r"\s*[-/.,]\s*|\s+", "-", match.group().strip())
        mention = re.sub(r"-(am|pm|बजे)$", r"\1", mention)
        found.append(re.sub(r"(?<!\d)0+(?=\d)", "", mention))
    return sorted(found)


def _normalise(text: str) -> str:
    """Lower case, ASCII digits, one dash, 'a.m.' -> 'am', and month, weekday and day words as codes (M11, D5, R1)."""
    text = unicodedata.normalize("NFKD", text).translate(_NORMALISE).lower()  # nukta split; full-width -> ASCII
    text = re.sub(r"\b([ap])\.\s?m\b\.?", r"\1m", text)
    text = _JA_WORDS.sub(lambda m: f" {_ja_code(m.group())} ", text)
    return re.sub(_LETTERS, lambda m: f" {_CODE[m.group()]} " if m.group() in _CODE else m.group(), text)


# ---------------------------------------------------------------- dates and times the source supports (rule S2)
_ORD = r"(?:st|nd|rd|th)?"
_DAY_MONTH = re.compile(rf"(?<!\d)(\d{{1,2}}){_ORD}(?:\s*(?:-|to|से|and|&)\s*(\d{{1,2}}){_ORD})?\s*(?:of\s+)?-?\s*M(\d{{1,2}})(?!\d)")
_MONTH_DAY = re.compile(rf"M(\d{{1,2}})\s*,?\s*(\d{{1,2}}){_ORD}(?![\d:])")
_ISO = re.compile(r"(?<!\d)\d{4}-(\d{1,2})-(\d{1,2})(?!\d)")
_JA_DAY = re.compile(r"(\d{1,2})月(\d{1,2})日")
_NUMERIC_DAY = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})(?:[/.-]\d{2,4})?(?![\d:])")
_CLOCK = re.compile(r"(?<!\d)(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|बजे)?(?![\d%])")
_JA_CLOCK = re.compile(r"(午前|午後)?(\d{1,2})時(?:(\d{1,2})分|(半))?")


def source_days(text: str) -> set[tuple[int, int]]:
    """Every (month, day) the text mentions, in any of its languages: '14 November', 'Nov 14', '1–30 नवम्बर',
    '11月20日', '2026-11-20', '12/11' (both readings, since 12/11 is 12 Nov in India and 11 Dec elsewhere)."""
    t, days = _normalise(text), set()
    for m in _DAY_MONTH.finditer(t):
        days.update((int(m[3]), int(d)) for d in (m[1], m[2]) if d)
    days.update((int(m[1]), int(m[2])) for m in _MONTH_DAY.finditer(t))
    days.update((int(m[1]), int(m[2])) for pattern in (_ISO, _JA_DAY) for m in pattern.finditer(t))
    for m in _NUMERIC_DAY.finditer(t):
        days.update({(int(m[2]), int(m[1])), (int(m[1]), int(m[2]))})
    return {(month, day) for month, day in days if 1 <= month <= 12 and 1 <= day <= 31}


def source_times(text: str) -> set[tuple[int, int]]:
    """Every (hour, minute) the text mentions: '9:30 AM', '6 pm', '18:00', '午後5時', '10時半', '6 बजे'. A time
    with no am/pm is taken both ways (6:00 may be morning or evening); a bare number without minutes is not a time."""
    t, times = _normalise(text), set()
    for m in _CLOCK.finditer(t):
        hour, minute, half = int(m[1]), int(m[2] or 0), m[3]
        if half in ("am", "pm") and 1 <= hour <= 12:
            times.add((hour % 12 + (12 if half == "pm" else 0), minute))
        elif m[2] or half == "बजे":
            times.update({(hour, minute), ((hour + 12) % 24, minute)} if hour <= 12 else {(hour, minute)})
    for m in _JA_CLOCK.finditer(t):
        hour = int(m[2]) % 12 + (12 if m[1] == "午後" else 0) if m[1] else int(m[2])
        times.add((hour, 30 if m[4] else int(m[3] or 0)))
    return {(h, mi) for h, mi in times if h <= 23 and mi <= 59}


def unsupported_dates(draft: dict[str, Any], source_text: str, has_images: bool) -> list[ReviewedIssue]:
    """Rule S2 in code: an action's date and time must be ones the shared text mentions, or they wait for the sender.
    If the text mentions no date (or no time) at all but images were shared, the value came from the images;
    the checker, which sees them, stays responsible for it."""
    days, times, held = source_days(source_text), source_times(source_text), []
    for index, action in enumerate(draft.get("actions") or []):
        due_date, due_time = normalize_date(action.get("due_date")), normalize_time(action.get("due_time"))
        checks = [("due_date", "date", due_date, (int(due_date[5:7]), int(due_date[8:])) if is_iso_date(due_date) else None, days),
                  ("due_time", "time", due_time, _hh_mm(due_time), times)]
        for field, word, written, value, found in checks:
            if value is None or value in found or (has_images and not found):
                continue
            held.append(ReviewedIssue(path=f"actions[{index}].{field}", severity="major", corrected_text=str(written),
                                      problem=f"The {word} {written} isn't in the shared text, so it waits for the sender.",
                                      needs_review=True))
    return held


def _hh_mm(value: Any) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d{2}):(\d{2})", value) if isinstance(value, str) else None
    return (int(match[1]), int(match[2])) if match else None


def _ja_code(word: str) -> str:
    return _JA_CODE.get(word) or f"D{'月火水木金土日'.index(word[0]) + 1}"  # 月曜 -> D1 ... 日曜 -> D7
