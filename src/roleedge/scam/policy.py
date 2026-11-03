"""The scam checker's task: the scam types, the prompts, and the answer format.

Standard library only. The same file is in the training kit (scam-checker/scamcheck/policy.py) and in the app
(src/roleedge/scam/policy.py); a test keeps the two identical.

Two prompts: the **full** one lists every scam type and the rules, and is what untrained models get (base Glimmer,
Muse Spark, GPT, Claude). The **short** one is what the tuned Glimmer is trained and asked with: it has learned the
types and rules, and a prompt about 10 times shorter makes training several times cheaper.

One message received in Japan (SMS, LINE, WhatsApp, email, a phone call written out, a social-media DM) goes in.
The answer is one JSON object:

    {"scam": true, "type": "refund", "red_flags": ["ATMで手続き", "本日中"], "advice": "電話を切って、家族に確認してください。"}

``red_flags`` are exact phrases copied from the message, so they can be checked by code. A genuine message has
type "none", no red flags and an empty advice line.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

SCAM_TYPES: dict[str, tuple[str, str]] = {
    "family_impersonation": ("Pretending to be family (オレオレ詐欺)",
                             "A son, grandson or relative with a new number, a lost phone, an accident or trouble at "
                             "work who needs money now, often with someone else coming to collect it."),
    "fake_official": ("Pretending to be police or officials",
                      "Police, prosecutors, a ministry, the city office or a bank's security team saying your account "
                      "is involved in a crime, asking for a video call, cards, PINs or a transfer to 'check' money."),
    "refund": ("Fake refund (還付金詐欺)",
               "A refund of medical costs, insurance or pension that can only be received by going to an ATM or "
               "using online banking now."),
    "fake_bill": ("Fake bill (架空料金請求)",
                  "Unpaid fees for a website, a lawsuit or a debt, paid with gift cards, convenience-store codes or a "
                  "transfer, or legal action follows."),
    "investment": ("Investment scam (SNS型投資詐欺)",
                   "A famous person or 'teacher' with a sure way to make money, a LINE or WhatsApp group, an app to "
                   "deposit into, profits that need a fee to withdraw."),
    "romance": ("Romance scam (SNS型ロマンス詐欺)",
                "Someone met online who becomes close quickly, then needs money, or brings in an investment."),
    "phishing": ("Fake link from a company (フィッシング)",
                 "A courier, bank, card, shop, mobile carrier, tax office or ETC notice with a link to log in, pay or "
                 "confirm details."),
    "job_task": ("Job or task scam (副業・タスク詐欺, 闇バイト)",
                 "Easy pay for likes, reviews or simple tasks, then a deposit to unlock earnings; or a high-pay job "
                 "that turns out to be carrying cash or other crimes."),
    "prize": ("Fake prize (当選詐欺)",
              "A prize, lottery or campaign win that needs a fee, card details or personal details to claim."),
    "other": ("Other scam", "Any other attempt to take money, accounts or personal details by deceit."),
}
CHANNELS: dict[str, str] = {"sms": "SMS", "line": "LINE", "whatsapp": "WhatsApp", "email": "Email",
                            "phone": "Phone call (written out)", "sns_dm": "Social-media DM"}
MAX_FLAGS = 4

SYSTEM = """\
You check one message that a person in Japan received, and decide whether it is a scam.

Scam types:
{types}

Answer with one JSON object and nothing else:
{{"scam": true or false, "type": one of {codes} or "none", "red_flags": [...], "advice": "..."}}
- red_flags: up to {max_flags} short phrases copied exactly from the message that show it is a scam; [] if not a scam.
- advice: if a scam, one short, calm sentence in plain Japanese for an older person on what to do now; "" if not.
- A genuine message can mention money, refunds, the police or a parcel. Judge what it asks the reader to do, and
  whether that is what the real sender would ask."""


@dataclass(frozen=True)
class Answer:
    scam: bool
    type: str = "none"  # a SCAM_TYPES code, or "none" when not a scam
    red_flags: list[str] = field(default_factory=list)
    advice: str = ""
    parsed: bool = True  # False when the model's answer was not valid JSON in the format (counted as a scam)


SHORT_SYSTEM = ("You check one message that a person in Japan received for scams. Answer with one JSON object: "
                "scam, type, red_flags, advice.")


def system_prompt() -> str:
    types = "\n".join(f"- {code}: {name}. {rule}" for code, (name, rule) in SCAM_TYPES.items())
    return SYSTEM.format(types=types, codes=", ".join(f'"{c}"' for c in SCAM_TYPES), max_flags=MAX_FLAGS)


def user_prompt(text: str, channel: str = "", sender: str = "") -> str:
    parts = [f"Channel: {CHANNELS.get(channel, channel)}"] if channel else []
    if sender:
        parts.append(f"Sender: {sender}")
    parts.append(f"Message:\n{text.strip()}")
    return "\n".join(parts)


def messages(row: dict, short: bool = False) -> list[dict[str, str]]:
    """The chat messages for one row: ``short`` for the tuned Glimmer, the full prompt for every other model."""
    return [{"role": "system", "content": SHORT_SYSTEM if short else system_prompt()},
            {"role": "user", "content": user_prompt(row["text"], row.get("channel", ""), row.get("sender", ""))}]


def target(row: dict) -> str:
    """What the checker should answer for ``row`` (the training target), as compact JSON."""
    if row["scam"] and row.get("type") not in SCAM_TYPES:
        raise ValueError("a scam needs a type from SCAM_TYPES")
    answer = ({"scam": True, "type": row["type"], "red_flags": row.get("red_flags", [])[:MAX_FLAGS],
               "advice": row.get("advice", "")} if row["scam"]
              else {"scam": False, "type": "none", "red_flags": [], "advice": ""})
    return json.dumps(answer, ensure_ascii=False, separators=(",", ":"))


def parse_answer(text: str) -> Answer:
    """Read any model's answer. Anything not in the format counts as a scam, so a confused checker warns instead of
    letting a message through."""
    match = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("scam"), bool):
        return Answer(scam=True, type="other", parsed=False)
    if not data["scam"]:
        return Answer(scam=False)
    kind = data.get("type") if data.get("type") in SCAM_TYPES else "other"
    flags = [str(f) for f in data.get("red_flags") or [] if str(f).strip()][:MAX_FLAGS]
    return Answer(scam=True, type=kind, red_flags=flags, advice=str(data.get("advice") or ""))


def normalise(text: str) -> str:
    """For comparing phrases: full-width and half-width forms unified, spaces removed."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def flags_in(text: str, flags: list[str]) -> list[str]:
    """The red flags that really occur in ``text`` (models sometimes paraphrase instead of copying)."""
    body = normalise(text)
    return [f for f in flags if normalise(f) and normalise(f) in body]


def foreign_hanzi(text: str) -> str:
    """Chinese characters that are not used in Japanese (generated text sometimes slips into Chinese: 确定申告)."""
    out = []
    for ch in unicodedata.normalize("NFKC", text):
        if "CJK UNIFIED" in unicodedata.name(ch, ""):
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                out.append(ch)
    return "".join(out)
