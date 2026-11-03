"""Code checks on a finished pack, before it can reach her (rules S2 and T5).

* Every date and time the pack mentions must be one the shared item mentions (``source_days`` / ``source_times``
  read English, Hindi and Japanese); anything else is a soft hold the caregiver must look at.
* The final send gate runs on every line she will see or hear, including the conversation starter shown with it.
"""

from __future__ import annotations

import re
from typing import Any

from ..content.verify import source_days, source_times
from ..gates import check_outgoing
from ..models import GateResult

# Emoji and pictographs (with a joiner, variation selector or trailing space). The product uses line icons only.
EMOJI = re.compile("(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A\u231B\u23E9-\u23FA][\uFE0F\u200D\u20E3]*)+ ?")
DATE_RULE = "date_not_in_source"
CHILD_RULE = "child_guardian"  # a soft hold: the parent may send it anyway after reading it
VERIFIER_RULE = "verifier"  # a soft hold: the verifier (Muse Wonder) wants the caregiver to look first
DATE_REASON = "It mentions a date or time that isn't in what you shared. Check it before sending."


def recipient_texts(outputs: dict[str, dict[str, Any]]) -> list[str]:
    """Every string she will see or hear (the English summaries for the caregiver are left out)."""
    found: list[str] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, str):
            if not key.endswith("_en") and key not in ("icon", "speaker", "format", "image"):
                found.append(value)
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)

    walk(outputs)
    return found


def without_emoji(value: Any) -> Any:
    """``value`` with emoji removed from every string in it (models add them despite being told not to)."""
    if isinstance(value, str):
        return EMOJI.sub("", value)
    if isinstance(value, dict):
        return {k: without_emoji(v) for k, v in value.items()}
    if isinstance(value, list):
        return [without_emoji(v) for v in value]
    return value


def check_pack(outputs: dict[str, dict[str, Any]], source_text: str, extra_source: list[str] = (),
               also_shown: list[str] = (), allow_soft: bool = False, warning: bool = False) -> GateResult:
    """``also_shown``: other lines she sees with the pack (the plan's conversation starter), checked the same way.
    ``warning``: the research found a scam, so the pack may name what the scam asks for (a soft hold, not a hard one)."""
    texts = [*recipient_texts(outputs), *(t for t in also_shown if t)]
    gate = check_outgoing(*texts, allow_soft=allow_soft, warning=warning)
    source = "\n".join([source_text, *extra_source])
    said = "\n".join(texts)
    new_days = source_days(said) - source_days(source)
    new_times = source_times(said) - source_times(source)
    if (new_days or new_times) and not allow_soft:
        return GateResult(passed=False, reasons=[*gate.reasons, DATE_REASON], rules=[*gate.rules, DATE_RULE])
    return gate


# ---------------------------------------------------------------- the family's voice, checked by code

# Habits that make a message sound like a report about a reel instead of the family talking (the user's review of the
# moments, 2026-11-03): introducing yourself, narrating the reel, disclaimers nobody needs, labels about the reel.
ROBOTIC = [
    (re.compile(r"\b(the|this) (reel|video|clip)\b", re.I), "talks about the reel instead of telling the content"),
    (re.compile(r"\bin (this|the) (reel|video|clip)\b", re.I), "talks about the reel instead of telling the content"),
    (re.compile(r"\b(i am|i'm|this is|it is|it's) (maya|kenji|mom|dad)\b", re.I), "introduces the sender, as if it were a first message"),
    (re.compile(r"\bi (saved|found) this for you\b", re.I), "introduces the sender, as if it were a first message"),
    (re.compile(r"\b(you )?(do not|don't|never) need to (follow|comment|write|buy|try|do|share|pay)\b", re.I), "a disclaimer she doesn't need"),
    (re.compile(r"\bno need to (follow|comment|try|buy|write)\b", re.I), "a disclaimer she doesn't need"),
    (re.compile(r"\b(is |are |was )?not proven\b|\bno proof\b|\bthere is no evidence\b", re.I), "a disclaimer she doesn't need"),
    (re.compile(r"\bonly (her|his|their) (own )?(opinion|taste|view|favou?rites)\b|\bjust (her|his) (own )?(opinion|view)\b", re.I), "a disclaimer she doesn't need"),
    (re.compile(r"\bwe do not know( for sure)? who\b", re.I), "a disclaimer she doesn't need"),
    (re.compile(r"\bthis is a scam\b", re.I), "names it a scam instead of warning as news"),
    (re.compile(r"\b(reel promise|check found|song words|reel title)\b", re.I), "a label about the reel instead of the content"),
    (re.compile(r"(この|その)(リール|動画)|動画では|リールでは"), "talks about the reel instead of telling the content"),
    (re.compile(r"\b(his|her|their) (\w+ )?(shirt|coat|dress|jacket|hat|glasses|outfit|clothes)\b|\b(he|she) (is )?wear(s|ing)\b", re.I),
     "describes the person in the reel instead of telling the content"),
    (re.compile(r"\b(he|she) (makes|is making|does|is doing|shows|points)\b", re.I), "describes what the person in the reel does"),
]
REFUSAL = re.compile(r"\bnot for us\b|\bwe'?ll skip\b|\bskip (it|this|these|that)\b|\bnot (really )?our (kind of )?thing\b", re.I)


def robotic(texts: list[str]) -> list[str]:
    """Each robotic habit found in what she will see or hear, with the words that show it (empty if none)."""
    found = []
    for text in texts:
        for pattern, why in ROBOTIC:
            match = pattern.search(text)
            if match:
                found.append(f'{why}: "{match.group(0)}"')
    refusals = [t for t in texts if REFUSAL.search(t)]
    if len(refusals) >= 2:  # once is kind; after every item it is a list of refusals
        found.append(f'says it isn\'t for her after each item ({len(refusals)} times): "{REFUSAL.search(refusals[1]).group(0)}"')
    return list(dict.fromkeys(found))
