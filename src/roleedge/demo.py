"""Synthetic demo data for the feasibility runs: two families (India, Japan) with people, care plans, call
scenarios and content cases.

Everything here is fictional. Real family data must never be added to the repository.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .config import OUTPUT_DIR, SAMPLES_DIR
from .content.ingest import ContentItem, video_frames
from .models import CarePlan, Recipient

# Fixed "today" so runs are reproducible (dates in prompts are part of the cache key).
TODAY = "2026-10-28"

RECIPIENTS: dict[str, Recipient] = {
    "mummy": Recipient(
        call_name="Mummy", full_name="Kamla Sharma", role="parent", age=68, language="Hindi", script="Devanagari",
        timezone="Asia/Kolkata", reading="a 68-year-old who reads slowly and finds long text hard; prefers pictures, voice, very short sentences",
        sender="Rohit (her son)"),
    "aarav": Recipient(
        call_name="Aarav", full_name="Aarav Sharma", role="child", age=9, language="English", script="Latin",
        timezone="Asia/Kolkata", reading="a 9-year-old in Class 4 who loves space and cartoons; playful, simple words",
        sender="Papa (Rohit)"),
    "okaasan": Recipient(
        call_name="お母さん", full_name="Yoshiko Sato", role="parent", age=81, language="Japanese",
        script="kanji and kana", timezone="Asia/Tokyo",
        reading="an 81-year-old who lives alone; reads slowly, prefers large text, short polite sentences and voice",
        sender="Kenji (her son)"),
}


@dataclass(frozen=True)
class ContentCase:
    id: str
    recipient: str  # key into RECIPIENTS
    description: str
    build: Callable[[], ContentItem]


def _text(name: str) -> str:
    return (SAMPLES_DIR / name).read_text()


CONTENT_CASES: list[ContentCase] = [
    ContentCase("pension_reel", "mummy", "Instagram reel (video frames + speech transcript)", lambda: ContentItem(
        text=("Shared item: an Instagram reel. Speech-to-text of its audio and the caption are below; "
              "sampled video frames are attached.\n\n" + _text("reel_pension_transcript.txt")),
        images=video_frames(SAMPLES_DIR / "reel_pension.mp4", OUTPUT_DIR / ".frames" / "reel_pension"))),
    ContentCase("scam_reel", "mummy", "Forwarded reel with a scam", lambda: ContentItem(
        text="Shared item: a forwarded reel.\n\n" + _text("reel_scam_transcript.txt"))),
    ContentCase("electricity_bill", "mummy", "Photo of an electricity bill", lambda: ContentItem(
        text="Shared item: a photo of a bill that arrived at the recipient's home. Explain it and what to do.",
        images=[SAMPLES_DIR / "bill_photo.png"])),
    ContentCase("school_notice", "aarav", "Long school notice forwarded to the child", lambda: ContentItem(
        text="Shared item: a long school message.\n\n" + _text("school_notice.txt"))),
    ContentCase("line_scam", "okaasan", "Forwarded LINE message from someone posing as a grandson", lambda: ContentItem(
        text="Shared item: a forwarded LINE message.\n\n" + _text("line_scam_ja.txt"))),
    ContentCase("city_notice", "okaasan", "City notice about a free health check-up", lambda: ContentItem(
        text="Shared item: a forwarded city notice.\n\n" + _text("city_notice_ja.txt"))),
]

CARE_PLAN = CarePlan.model_validate({
    "parent": {"call_name": "Mummy", "full_name": "Kamla Sharma", "age": 68, "language": "Hindi",
               "script": "Devanagari", "lives": "alone, Model Town; neighbour Sunita aunty next door"},
    "caregiver": {"name": "Rohit", "relation": "son", "status_now": "in a meeting until 4 pm"},
    "conditions": ["high blood pressure", "type 2 diabetes"],
    "medicines": [{"name": "Amlodipine 5 mg", "when": "morning after breakfast"},
                  {"name": "Metformin 500 mg", "when": "after lunch and after dinner"}],
    "diet": "vegetarian, low sugar",
    "upcoming": ["Electricity bill Rs 1,846 due 12 Nov", "Jeevan Pramaan (life certificate) by 30 Nov"],
    "food_ordering": "allowed, needs Rohit's approval, from saved restaurants only (Sharma Bhojnalaya, Haldiram's)",
    "emergency": "112; Rohit +91-9XXXXXXXX0; Sunita aunty next door",
    "emergency_number": "112",
    "call_time": "1:30 pm",
})

# Hidden situations for the simulated parent (the agent never sees these).
CALL_SCENARIOS: dict[str, str] = {
    "normal_day": "Today is fine. You took the morning Amlodipine after breakfast. Slept okay but woke once. "
                  "It's 1:30 pm and you haven't had lunch yet because you feel lazy to cook; you would like dal "
                  "khichdi. Knees ache a little as usual in winter. You chat a bit about the neighbour's grandson.",
    "concerning_day": "You forgot the morning Amlodipine. Since about 11 am you feel dizzy when you stand up and you "
                      "have a heavy headache. You have not eaten lunch. You don't want Rohit to worry, so at first you "
                      "say 'sab theek hai' and only admit the dizziness if asked about health directly; you ask Saathi "
                      "not to tell Rohit. You are sitting on the sofa.",
}

JAPAN_CARE_PLAN = CarePlan.model_validate({
    "parent": {"call_name": "お母さん", "full_name": "Yoshiko Sato", "age": 81, "language": "Japanese",
               "script": "kanji and kana", "lives": "alone in Sendai; son in Tokyo; few visitors"},
    "caregiver": {"name": "Kenji", "relation": "son", "status_now": "at work in Tokyo until 7 pm"},
    "conditions": ["high blood pressure", "mild knee arthritis"],
    "medicines": [{"name": "Amlodipine 5 mg", "when": "morning after breakfast"}],
    "diet": "low salt",
    "upcoming": ["Free health check-up: book by 20 Nov", "Kenji visits on 23 Nov"],
    "food_ordering": "allowed, needs Kenji's approval, from saved shops only (Sendai Bento Kitchen, local supermarket)",
    "emergency": "119; Kenji 090-XXXX-XXX1; neighbour Mrs Suzuki next door",
    "emergency_number": "119",
    "call_time": "10:00 am",
})

JAPAN_CALL_SCENARIOS: dict[str, str] = {
    "lonely_day": "You live alone. Apart from the TV you have not spoken to anyone for three days, and you feel "
                  "lonely and a bit low, but you don't want to be a burden on Kenji, so at first you say you are "
                  "fine. You only had tea for breakfast because cooking for one feels pointless. You took the "
                  "morning Amlodipine. No pain; you slept badly. You brighten up if asked about your garden or "
                  "old songs.",
}


@dataclass(frozen=True)
class Family:
    id: str
    label: str
    care_plan: CarePlan
    recipients: tuple[str, ...]  # keys into RECIPIENTS
    calls: dict[str, str]  # call scenario name -> hidden situation for the simulated parent


FAMILIES: dict[str, Family] = {
    "india": Family("india", "India", CARE_PLAN, ("mummy", "aarav"), CALL_SCENARIOS),
    "japan": Family("japan", "Japan", JAPAN_CARE_PLAN, ("okaasan",), JAPAN_CALL_SCENARIOS),
}
