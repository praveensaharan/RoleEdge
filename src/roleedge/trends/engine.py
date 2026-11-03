"""Compare the last two weeks with her own baseline and decide, in code, whether something has changed.

Method (kept simple so a reviewer can follow it):

* **Windows:** the recent window is the last ``recent_days`` (default 14) up to ``as_of``; the baseline is up to
  ``baseline_days`` (default 28) before that.
* **Counted signals** (skipped meals, days she stayed in, ...): compare weekly rates. A line is flagged when the
  recent rate is at least ``max(MIN_EXTRA_PER_WEEK, 2 x the baseline's week-to-week spread)`` above her usual rate.
* **Voice features** (speaking rate, pauses, reply length): compare means. A line is flagged when the recent mean
  moves at least 2 standard deviations of her baseline days, and at least ``MIN_RELATIVE_CHANGE``, in the worse
  direction.
* **Level:** no flagged area = steady; one = small change; two = sustained change; three or more = worth a visit.

Family steps are fixed text chosen by the level. In ``"family"`` mode the report leaves out the visit-notes and
support-centre resources (for submissions where health pointers are not wanted).
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Literal

from ..models import AREA_OF, SignalEvent, TrendLine, TrendReport, VoiceDay

InsightsMode = Literal["full", "family"]

# kind(s) -> (label, unit). Several kinds can share one line.
COUNT_LINES: dict[str, tuple[tuple[str, ...], str]] = {
    "meal_skipped": (("meal_skipped", "not_hungry"), "Skipped meals or not hungry"),
    "slept_badly": (("slept_badly",), "Bad nights"),
    "stayed_in": (("stayed_in",), "Days she stayed in"),
    "talked_to_nobody": (("talked_to_nobody", "lonely"), "Days she talked to nobody or felt lonely"),
    "repeated_question": (("repeated_question", "unsure_of_day", "forgot_plan"), "Repeated questions or forgotten plans"),
    "unwell": (("unwell", "pain", "dizzy", "low_energy"), "Said she felt unwell or tired"),
    "low_mood": (("low_mood", "worried"), "Low or worried moments"),
    "missed_medicine": (("missed_medicine",), "Missed medicine"),
}
# field -> (label, unit, worse direction)
VOICE_LINES: dict[str, tuple[str, str, Literal["up", "down"]]] = {
    "speech_rate_wpm": ("Speaking pace", "words per minute", "down"),
    "pause_ratio": ("Pauses while talking", "share of the reply", "up"),
    "reply_seconds": ("Length of her replies", "seconds", "down"),
}

MIN_EXTRA_PER_WEEK = 2.0
MIN_RELATIVE_CHANGE = 0.08
VOICE_SD_FLOOR = {"speech_rate_wpm": 3.0, "pause_ratio": 0.01, "reply_seconds": 2.0}
MAX_EVIDENCE = 4

STEPS = {
    "steady": ["Nothing has changed much. A short call this week keeps it that way."],
    "small_change": ["Call her tonight and ask how she has been."],
    "sustained_change": ["Call her today.", "Plan a visit or a family video call this week.",
                         "Offer to have lunch delivered on the days she skips meals."],
    "worth_a_visit": ["Call her today.", "Visit this week if you can, or ask someone close to her to drop by.",
                      "Offer to have lunch delivered on the days she skips meals."],
}
VISIT_NOTES_STEP = "If she agrees, bring the visit notes (what she told you, with dates) to her next doctor's appointment."


def build_report(circle_id: str, events: list[SignalEvent], voice_days: list[VoiceDay], *, as_of: date | None = None,
                 recent_days: int = 14, baseline_days: int = 28, mode: InsightsMode = "full",
                 support_centre: dict[str, str] | None = None) -> TrendReport:
    as_of = as_of or _last_day(events, voice_days)
    recent_start = as_of - timedelta(days=recent_days - 1)
    baseline_start = recent_start - timedelta(days=baseline_days)

    def in_recent(day: str) -> bool:
        return recent_start <= date.fromisoformat(day) <= as_of

    def in_baseline(day: str) -> bool:
        return baseline_start <= date.fromisoformat(day) < recent_start

    lines = [_count_line(key, kinds, label, events, in_recent, in_baseline, recent_days, baseline_days, baseline_start)
             for key, (kinds, label) in COUNT_LINES.items()]
    lines += [line for field, (label, unit, worse) in VOICE_LINES.items()
              if (line := _voice_line(field, label, unit, worse, voice_days, in_recent, in_baseline))]

    flagged_areas = sorted({_area_of_line(line.key) for line in lines if line.flagged})
    level = _level(len(flagged_areas))
    steps = list(STEPS[level])
    resources: list[dict[str, str]] = []
    if mode == "full" and level == "worth_a_visit":
        steps.append(VISIT_NOTES_STEP)
        resources.append({"kind": "visit_notes", "label": "Visit notes: what she told you, with dates"})
        if support_centre:
            resources.append({"kind": "support_centre", **support_centre})
    return TrendReport(circle_id=circle_id, as_of=as_of.isoformat(), baseline_days=baseline_days,
                       recent_days=recent_days, level=level, flagged_areas=flagged_areas, lines=lines,
                       family_steps=steps, resources=resources)


def _count_line(key: str, kinds: tuple[str, ...], label: str, events: list[SignalEvent], in_recent, in_baseline,
                recent_days: int, baseline_days: int, baseline_start: date) -> TrendLine:
    mine = [e for e in events if e.kind in kinds]
    recent = [e for e in mine if in_recent(e.day)]
    baseline = [e for e in mine if in_baseline(e.day)]
    recent_rate = len(recent) * 7 / recent_days
    baseline_rate = len(baseline) * 7 / baseline_days
    weekly = [sum(1 for e in baseline if baseline_start + timedelta(days=7 * w) <= date.fromisoformat(e.day)
                  < baseline_start + timedelta(days=7 * (w + 1))) for w in range(max(1, baseline_days // 7))]
    spread = statistics.pstdev(weekly) if len(weekly) > 1 else 0.0
    flagged = recent_rate - baseline_rate >= max(MIN_EXTRA_PER_WEEK, 2 * spread)
    direction = "up" if recent_rate > baseline_rate + 0.5 else "down" if recent_rate < baseline_rate - 0.5 else "steady"
    evidence = sorted(recent, key=lambda e: e.day, reverse=True)[:MAX_EVIDENCE] if flagged else []
    return TrendLine(key=key, label=label, unit="per week", baseline=round(baseline_rate, 1),
                     recent=round(recent_rate, 1), flagged=flagged, direction=direction, evidence=evidence)


def _voice_line(field: str, label: str, unit: str, worse: str, voice_days: list[VoiceDay], in_recent,
                in_baseline) -> TrendLine | None:
    recent = [getattr(v, field) for v in voice_days if in_recent(v.day)]
    baseline = [getattr(v, field) for v in voice_days if in_baseline(v.day)]
    if len(recent) < 3 or len(baseline) < 7:  # too little to say anything
        return None
    base_mean, recent_mean = statistics.fmean(baseline), statistics.fmean(recent)
    sd = max(statistics.pstdev(baseline), VOICE_SD_FLOOR[field])
    change = recent_mean - base_mean
    moved_worse = change < 0 if worse == "down" else change > 0
    flagged = (moved_worse and abs(change) >= 2 * sd
               and abs(change) >= MIN_RELATIVE_CHANGE * max(abs(base_mean), 1e-9))
    direction = "steady" if abs(change) < sd else ("up" if change > 0 else "down")
    digits = 2 if field == "pause_ratio" else 0
    return TrendLine(key=field, label=label, unit=unit, baseline=round(base_mean, digits),
                     recent=round(recent_mean, digits), flagged=flagged, direction=direction)


def _area_of_line(key: str) -> str:
    return "voice" if key in VOICE_LINES else AREA_OF[COUNT_LINES[key][0][0]]


def _level(flagged_area_count: int) -> str:
    if flagged_area_count == 0:
        return "steady"
    if flagged_area_count == 1:
        return "small_change"
    return "sustained_change" if flagged_area_count == 2 else "worth_a_visit"


def _last_day(events: list[SignalEvent], voice_days: list[VoiceDay]) -> date:
    days = [e.day for e in events] + [v.day for v in voice_days]
    return date.fromisoformat(max(days)) if days else date.today()
