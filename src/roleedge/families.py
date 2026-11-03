"""The two demo circles (English and Japanese) and their synthetic six-week history.

Everything here is fictional (rule S7). The history is generated from a fixed seed so every run, test and demo
recording sees the same weeks: four ordinary weeks, then two weeks in which she skips more meals, stays in more,
talks to nobody more often, repeats a question, and speaks more slowly with longer pauses.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from .models import Circle, DisclosureRule, Member, Playbook, SignalEvent, SpendingLimit, VoiceDay

DEMO_TODAY = date(2026, 11, 2)  # fixed so demo runs are reproducible
HISTORY_DAYS = 42
DRIFT_FROM_DAY = 28  # days 28..41 are the changed two weeks

PLAYBOOKS = [
    Playbook(id="daily_checkin", label="Daily check-in", detail="10:00 every day"),
    Playbook(id="weekly_summary", label="Weekly summary", detail="Sunday evening"),
    Playbook(id="answer_schedule", label="Answer questions about my schedule and deliveries"),
    Playbook(id="tonight_food", label="Suggest food for tonight when she's missing something"),
    Playbook(id="watch_staples", label="Watch prices on staples and daily items"),
]
DISCLOSURE = [
    DisclosureRule(category="schedule", label="My schedule (busy or free)", policy="share"),
    DisclosureRule(category="whereabouts", label="Where I am, city level", policy="share"),
    DisclosureRule(category="travel", label="Travel plans", policy="share"),
    DisclosureRule(category="family_events", label="Family events", policy="share"),
    DisclosureRule(category="deliveries", label="Deliveries to her (verified senders only)", policy="share"),
    DisclosureRule(category="work", label="Work details", policy="ask"),
    DisclosureRule(category="health", label="My health", policy="ask"),
    DisclosureRule(category="money", label="Money", policy="ask"),
    DisclosureRule(category="other_people", label="Other people's information", policy="ask"),
    DisclosureRule(category="secrets", label="Passwords, finances, confidential work", policy="never"),
]


def _circle_ja() -> Circle:
    return Circle(
        id="sato", label="Kenji and Okaasan",
        caregiver=Member(id="kenji", name="Kenji Sato", call_name="Kenji", call_name_local="ケンジ", role="caregiver",
                         language="en",
                         timezone="Asia/Tokyo", relation="her son"),
        parent=Member(id="yoshiko", name="Yoshiko Sato", call_name="Okaasan", call_name_local="お母さん", role="parent",
                      language="ja",
                      timezone="Asia/Tokyo", age=81, relation="his mother", emergency_number="119"),
        children=[Member(id="hana", name="Hana Sato", call_name="Hana", call_name_local="はなちゃん", role="child",
                         language="ja", timezone="Asia/Tokyo", age=8, relation="his daughter", calls_caregiver="パパ",
                         calls_grandparent="おばあちゃん")],
        paired=True, playbooks=PLAYBOOKS, disclosure=DISCLOSURE, spending=SpendingLimit(currency="JPY"),
    )


def _circle_en() -> Circle:
    return Circle(
        id="chen", label="Maya and Mom",
        caregiver=Member(id="maya", name="Maya Chen", call_name="Maya", role="caregiver", language="en",
                         timezone="America/Los_Angeles", relation="her daughter"),
        parent=Member(id="linda", name="Linda Chen", call_name="Mom", role="parent", language="en",
                      timezone="America/Los_Angeles", age=79, relation="her mother", emergency_number="911"),
        children=[Member(id="leo", name="Leo Chen", call_name="Leo", role="child", language="en",
                         timezone="America/Los_Angeles", age=9, relation="her son", calls_caregiver="Mom",
                         calls_grandparent="Grandma")],
        paired=True, playbooks=PLAYBOOKS, disclosure=DISCLOSURE,
        spending=SpendingLimit(currency="USD", per_order=30, per_month=200),
    )


CIRCLES: dict[str, Circle] = {c.id: c for c in (_circle_ja(), _circle_en())}

SUPPORT_CENTRES: dict[str, dict[str, str]] = {
    "sato": {"label": "Her local community support centre (chiiki hokatsu shien senta)",
             "detail": "Every area of Sendai has one; the city's website lists hers by address."},
    "chen": {"label": "Her local Area Agency on Aging",
             "detail": "The county's website lists the office that covers her address."},
}

# (kind, quote) pools per language; quotes are her words, used as evidence on trend lines.
QUOTES: dict[str, dict[str, list[str]]] = {
    "en": {
        "meal_skipped": ["I didn't really have lunch today.", "I skipped dinner, I wasn't hungry.", "Just tea this afternoon."],
        "stayed_in": ["I stayed home all day.", "I didn't go out, it felt like too much.", "Didn't leave the house today."],
        "talked_to_nobody": ["Nobody called today.", "I haven't talked to anyone since Tuesday.", "It was quiet, no visitors."],
        "slept_badly": ["I slept badly again.", "I was up at three and couldn't get back to sleep."],
        "repeated_question": ["When are you coming again? Did I ask you that already?", "What day is the doctor? I forgot."],
        "unwell": ["I feel a bit tired today.", "My knee hurts more than usual."],
        "went_out": ["I walked to the shop this morning.", "I went to the community center."],
    },
    "ja": {
        "meal_skipped": ["今日はお昼を食べなかった。", "夕飯は食べる気がしなくて。", "午後はお茶だけ。"],
        "stayed_in": ["今日は一日家にいたよ。", "出かける気がしなくて。", "今日は外に出なかった。"],
        "talked_to_nobody": ["今日は誰とも話してない。", "火曜日から誰とも話してないの。", "静かな一日だったよ。"],
        "slept_badly": ["また眠れなかった。", "三時に目が覚めて、それから眠れなくて。"],
        "repeated_question": ["今度いつ来るの？前にも聞いたかな。", "病院は何曜日だっけ？忘れちゃった。"],
        "unwell": ["今日はちょっと疲れてる。", "膝がいつもより痛いの。"],
        "went_out": ["朝、近くのスーパーまで歩いたよ。", "公民館に行ってきた。"],
    },
}
AREA = {"meal_skipped": "eating", "stayed_in": "social", "talked_to_nobody": "social", "slept_badly": "sleep",
        "repeated_question": "memory", "unwell": "body", "went_out": "social"}
# weekly rates (ordinary weeks, changed weeks)
RATES = {"meal_skipped": (1, 4), "stayed_in": (1.5, 5), "talked_to_nobody": (1, 4), "slept_badly": (1, 2),
         "repeated_question": (0.25, 2.5), "unwell": (1, 1.5), "went_out": (4, 1)}


def history(circle_id: str, *, drift: bool = True) -> tuple[list[SignalEvent], list[VoiceDay]]:
    """Six weeks of synthetic signals and voice measurements, ending the day before ``DEMO_TODAY``."""
    circle = CIRCLES[circle_id]
    rng = random.Random(f"{circle_id}-{drift}")
    quotes = QUOTES[circle.parent.language]
    start = DEMO_TODAY - timedelta(days=HISTORY_DAYS)
    events: list[SignalEvent] = []
    voice: list[VoiceDay] = []
    base_rate = 150.0 if circle.parent.language == "en" else 310.0  # Japanese pace is counted in characters
    phase = {kind: rng.random() for kind in RATES}  # spreads each kind over the week, same every run
    due = dict(phase)
    for i in range(HISTORY_DAYS):
        day = (start + timedelta(days=i)).isoformat()
        changed = drift and i >= DRIFT_FROM_DAY
        for kind, (usual, later) in RATES.items():
            due[kind] += (later if changed else usual) / 7  # exact weekly rates, so the story never depends on luck
            if due[kind] >= 1:
                due[kind] -= 1
                events.append(SignalEvent(day=day, kind=kind, area=AREA[kind], quote=rng.choice(quotes[kind]),
                                          source="synthetic"))
        slow = 0.86 if changed else 1.0
        voice.append(VoiceDay(day=day, speech_rate_wpm=round(base_rate * slow + rng.gauss(0, base_rate * 0.025), 1),
                              pause_ratio=round(min(0.6, (0.26 if changed else 0.18) + rng.gauss(0, 0.015)), 3),
                              reply_seconds=round(max(4.0, (14 if changed else 22) + rng.gauss(0, 2)), 1)))
    return events, voice
