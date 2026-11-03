"""The trend engine flags a sustained drift from her own baseline, and stays quiet on a normal history."""

from datetime import date, timedelta

from roleedge.models import SignalEvent, VoiceDay
from roleedge.trends import build_report

START = date(2026, 9, 21)


def _history(drift: bool) -> tuple[list[SignalEvent], list[VoiceDay]]:
    """42 days: one skipped meal and one stay-in day a week; in the last 14 days, more of both if ``drift``."""
    events, voice = [], []
    for i in range(42):
        day = (START + timedelta(days=i)).isoformat()
        late = drift and i >= 28
        if i % 7 == 2 or (late and i % 2 == 0):
            events.append(SignalEvent(day=day, kind="meal_skipped", area="eating", quote="I didn't eat lunch"))
        if i % 7 == 5 or (late and i % 3 != 0):
            events.append(SignalEvent(day=day, kind="stayed_in", area="social", quote="I stayed home"))
        rate = 150 + (i % 3) - (18 if late else 0)
        voice.append(VoiceDay(day=day, speech_rate_wpm=rate, pause_ratio=0.18 + (0.07 if late else 0),
                              reply_seconds=20))
    return events, voice


def test_normal_history_is_steady():
    events, voice = _history(drift=False)
    report = build_report("c1", events, voice)
    assert report.level == "steady"
    assert report.flagged_areas == []
    assert report.resources == []


def test_drift_flags_several_areas_with_evidence():
    events, voice = _history(drift=True)
    report = build_report("c1", events, voice)
    flagged = {line.key for line in report.lines if line.flagged}
    assert {"meal_skipped", "stayed_in", "speech_rate_wpm", "pause_ratio"} <= flagged
    assert report.level == "worth_a_visit"
    meals = next(line for line in report.lines if line.key == "meal_skipped")
    assert meals.evidence and all(e.quote for e in meals.evidence)
    assert meals.recent > meals.baseline


def test_family_mode_leaves_out_health_resources():
    events, voice = _history(drift=True)
    full = build_report("c1", events, voice, support_centre={"label": "Local support centre"})
    family = build_report("c1", events, voice, mode="family", support_centre={"label": "Local support centre"})
    assert [r["kind"] for r in full.resources] == ["visit_notes", "support_centre"]
    assert family.resources == []
    assert not any("doctor" in step for step in family.family_steps)


def test_steps_come_from_code_not_text_from_the_model():
    events, voice = _history(drift=True)
    report = build_report("c1", events, voice)
    assert report.family_steps[0] == "Call her today."


def test_too_little_voice_data_adds_no_voice_lines():
    events, _ = _history(drift=False)
    report = build_report("c1", events, [VoiceDay(day=START.isoformat(), speech_rate_wpm=150, pause_ratio=0.2,
                                                  reply_seconds=20)])
    assert not any(line.key == "speech_rate_wpm" for line in report.lines)
