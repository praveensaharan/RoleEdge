"""Synthetic training messages, written by Muse Spark and checked twice.

1. **Write:** for every target (each scam type; a *genuine* message that looks like that type; everyday messages),
   Spark writes Japanese messages as they really arrive by SMS, LINE, WhatsApp, email, phone or DM, with the
   sender as it would show, the scam type, the red-flag phrases and one line of advice. Rounds rotate the channels,
   who receives the message and the situation, so batches don't repeat each other.
2. **Check:** code drops messages with Chinese characters not used in Japanese and keeps only red flags that really
   occur in the message (a scam needs at least one). Then a second, blind Spark pass labels every message without
   seeing the intended label. A message is kept only when both agree on scam or not, and on the type.
3. **Save:** a third of the senders are blanked (real messages often come without one), and the rows go to
   ``data/synthetic/spark_rounds_<first>-<last>.jsonl``. ``build`` merges, deduplicates and splits them later.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build import dedupe
from .meta_api import PRICE_IN, PRICE_OUT, MetaAPI
from .policy import CHANNELS, SCAM_TYPES, flags_in, foreign_hanzi

WRITTEN_TYPES = [code for code in SCAM_TYPES if code != "other"]
LOOKALIKE: dict[str, str] = {
    "family_impersonation": "a real son, daughter or grandchild writing about everyday plans, a visit, a parcel, a "
                            "photo, or a real number change that asks the parent to call back on the number they know",
    "fake_official": "real notices from the police, the city office or a bank: scam warnings, procedures done by "
                     "post or at the counter, security alerts that say they never ask for a PIN by phone",
    "refund": "real refund notices: the money is paid into the registered account automatically or the form comes "
              "by post; never an ATM step",
    "fake_bill": "real bills and reminders from the electricity, gas, water or phone company, with the usual ways "
                 "to pay",
    "investment": "a real brokerage's statement or NISA notice, or friends chatting about saving and investing",
    "romance": "real friends, partners or a dating app's own safety notice",
    "phishing": "real courier, bank, card, shop or mobile-carrier notices that tell you to check in the official "
                "app or website, or give a delivery time",
    "job_task": "real job offers and shift messages from known employers and recruiters",
    "prize": "a real campaign win from a shop or brand the person entered, with no fee to pay",
}
EVERYDAY = "everyday messages: family and friends on LINE, a clinic reminder, the neighbourhood association, a hobby group"
RECIPIENTS = ("a woman in her 70s who lives alone", "a man in his 80s", "a working parent in their 40s",
              "a university student", "a shop owner in their 60s", "a retired couple in their late 60s")
SITUATIONS = ("tax and pension season", "the New Year holidays", "after a typhoon or an earthquake", "Golden Week",
              "a busy weekday", "the end of the month", "a long weekend", "the start of the school year")

_TYPE = {"type": "string", "enum": [*SCAM_TYPES, "none"]}
MESSAGES_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["messages"], "properties": {
    "messages": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["channel", "sender", "text", "scam", "type", "red_flags", "advice"],
        "properties": {"channel": {"type": "string", "enum": list(CHANNELS)}, "sender": {"type": "string"},
                       "text": {"type": "string"}, "scam": {"type": "boolean"}, "type": _TYPE,
                       "red_flags": {"type": "array", "items": {"type": "string"}}, "advice": {"type": "string"}}}}}}
LABELS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["labels"], "properties": {
    "labels": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["index", "scam", "type"],
        "properties": {"index": {"type": "integer"}, "scam": {"type": "boolean"}, "type": _TYPE}}}}}


@dataclass(frozen=True)
class Request:
    target: str  # a scam type, "lookalike:<scam type>" or "everyday"
    round: int

    @property
    def scam(self) -> bool:
        return self.target in SCAM_TYPES

    @property
    def channels(self) -> tuple[str, str, str]:
        codes = list(CHANNELS)
        k = (self.round + len(self.target)) % len(codes)
        return codes[k], codes[(k + 2) % len(codes)], codes[(k + 4) % len(codes)]

    @property
    def recipient(self) -> str:
        return RECIPIENTS[(self.round + len(self.target)) % len(RECIPIENTS)]

    @property
    def situation(self) -> str:
        return SITUATIONS[(self.round * 5 + len(self.target)) % len(SITUATIONS)]


def _types_text() -> str:
    return "\n".join(f"- {code}: {name}. {rule}" for code, (name, rule) in SCAM_TYPES.items())


WRITER = """\
You write training data for a scam checker used in Japan. Write {n} different messages in natural Japanese that
{recipient} might receive around {situation}, spread over these channels: {channels}.
Target: {target}
Scam types:
{types}
For each message give:
- channel, and sender as it would show (a phone number such as +81 or +62, a LINE name, an email address, or "").
- text: the message exactly as it arrives; a phone call is written as the caller's words. Vary the length: most
  are 1 to 6 sentences, and about one in five is a full email or long notice of 8 to 15 lines. Vary how messages
  open; don't start two the same way. Scams in Japan are often polite and copy real wording, so mix obvious and
  convincing ones. Links: not every scam has one, and about half of genuine company notices link to the company's
  real domain. For a scam, invent lookalike links (never a real working site).
- Write standard Japanese only: no simplified or traditional Chinese characters.
- scam, and type (a code above, or "none" if genuine).
- red_flags: for a scam, 1 to 4 short phrases copied exactly, character for character, from the text; [] if genuine.
- advice: for a scam, one calm sentence in plain Japanese for an older person; "" if genuine.
Make no two messages alike in wording or situation. This is batch {batch}."""

JUDGE = """\
You check messages that people in Japan received. Label each one on its own: is it a scam, and of which type?
Scam types:
{types}
A genuine message can mention money, refunds, the police or a parcel; judge what it asks the reader to do, and
whether that is what the real sender would ask. Use "none" for a genuine message. Return one label per message
with its index."""


def requests(rounds: int, start: int = 0) -> list[Request]:
    targets = [*WRITTEN_TYPES, *(f"lookalike:{t}" for t in WRITTEN_TYPES), "everyday", "everyday", "everyday"]
    return [Request(target, r) for r in range(start, start + rounds) for target in targets]


def _target_text(request: Request) -> str:
    if request.scam:
        name, rule = SCAM_TYPES[request.target]
        return f"SCAM messages of type {request.target} ({name}: {rule})"
    if request.target == "everyday":
        return f"GENUINE {EVERYDAY}. Type none."
    kind = request.target.split(":", 1)[1]
    return (f"GENUINE messages that look a little like {SCAM_TYPES[kind][0]} but are real: {LOOKALIKE[kind]}. "
            "Type none. These teach the checker not to cry wolf.")


def write(api: MetaAPI, request: Request, per_request: int) -> list[dict[str, Any]]:
    prompt = WRITER.format(n=per_request, recipient=request.recipient, situation=request.situation,
                           channels=", ".join(CHANNELS[c] for c in request.channels), target=_target_text(request),
                           types=_types_text(), batch=request.round + 1)
    data = api.json("write", [{"role": "user", "content": prompt}], MESSAGES_SCHEMA, "scam_messages")
    rows = []
    for m in data["messages"]:
        text = m["text"].strip()
        if not 10 <= len(text) <= 1500 or m["scam"] != request.scam or foreign_hanzi(text):
            continue
        if m["scam"]:
            flags = flags_in(text, m["red_flags"])
            if m["type"] != request.target or not flags or not m["advice"].strip():
                continue
            label = {"scam": True, "type": m["type"], "red_flags": flags, "advice": m["advice"].strip()}
        else:
            label = {"scam": False, "type": "none", "red_flags": [], "advice": ""}
        rows.append({"text": text, "channel": m["channel"], "sender": m["sender"].strip(), **label,
                     "target": request.target, "round": request.round, "source": "spark"})
    return rows


def _check_batch(api: MetaAPI, chunk: list[dict[str, Any]]) -> list[dict[str, Any]]:
    listing = "\n\n".join(f"[{k}] Channel: {CHANNELS[r['channel']]}" + (f" | Sender: {r['sender']}" if r["sender"] else "")
                          + f"\n{r['text']}" for k, r in enumerate(chunk))
    data = api.json("check", [{"role": "system", "content": JUDGE.format(types=_types_text())},
                              {"role": "user", "content": listing}], LABELS_SCHEMA, "scam_labels")
    labels = {x["index"]: x for x in data["labels"]}
    return [row for k, row in enumerate(chunk) if (label := labels.get(k)) is not None
            and label["scam"] == row["scam"] and (not row["scam"] or label["type"] == row["type"])]


def check(api: MetaAPI, rows: list[dict[str, Any]], batch: int = 30, workers: int = 8) -> list[dict[str, Any]]:
    """The rows a blind second label agrees with."""
    chunks = [rows[i:i + batch] for i in range(0, len(rows), batch)]
    with ThreadPoolExecutor(workers) as pool:
        return [row for part in pool.map(lambda c: _check_batch(api, c), chunks) for row in part]


def blank_some_senders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A third of rows lose their sender (real messages are often forwarded without one); repeatable per text."""
    return [{**r, "sender": ""} if int(hashlib.sha256(r["text"].encode()).hexdigest(), 16) % 3 == 0 else r for r in rows]


def estimate(rounds: int, per_request: int, batch: int = 30) -> dict[str, Any]:
    """What ``run`` will do and roughly cost. Tokens per call and per message were measured on a pilot (Nov 3)."""
    writes = len(requests(rounds))
    messages = writes * per_request
    checks = -(-messages // batch)
    tokens_in = writes * 750 + checks * (700 + batch * 90)
    tokens_out = messages * 400 + checks * batch * 60
    return {"write_calls": writes, "check_calls": checks, "messages_before_checks": messages,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "usd": round(tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT, 2)}


def run(api: MetaAPI, out_dir: Path, rounds: int, start: int = 0, per_request: int = 20,
        workers: int = 8) -> tuple[Path, dict[str, Any]]:
    with ThreadPoolExecutor(workers) as pool:
        written = [row for part in pool.map(lambda r: write(api, r, per_request), requests(rounds, start)) for row in part]
    unique = dedupe(written)
    kept = blank_some_senders(check(api, unique, workers=workers))
    path = out_dir / f"spark_rounds_{start:03d}-{start + rounds - 1:03d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    stats = {"asked_for": len(requests(rounds)) * per_request, "passed_code_checks": len(written),
             "unique": len(unique), "kept": len(kept), "dropped_by_blind_check": len(unique) - len(kept),
             "scam_share": round(sum(r["scam"] for r in kept) / max(1, len(kept)), 2)}
    return path, stats
