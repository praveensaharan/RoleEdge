"""The final send gate (PIVOT.md T5): the last step before anything reaches the parent, whoever wrote it.

It looks for what scams need: money, codes, card numbers, links, a number to call, pressure to act now, and
secrecy. Code decides, so a prompt injection or a model slip cannot talk its way past it.

* **Hard rules** (money, code, card, link, secrecy) hold the message and cannot be overridden from the app.
* **Soft rules** (phone, pressure) hold the message until the caregiver taps "send anyway".
* **A scam warning** (``warning=True``: the research found the shared item is a scam) has to name what the scam
  wants ("don't pay the $4.99", "never share the code"), so money, code and secrecy become one soft hold the
  caregiver reads once. Links and card numbers stay hard: a warning never needs one.

English and Japanese patterns are both checked, whatever the message language.
"""

from __future__ import annotations

import re
import unicodedata

from ..models import GateResult

_I = re.IGNORECASE
RULES: dict[str, tuple[str, list[re.Pattern[str]]]] = {
    "money": ("asks for money or a payment", [
        re.compile(r"\b(send|transfer|wire|pay|deposit|lend|withdraw)\b.{0,40}\b(money|cash|yen|dollars?|bank|account|atm)\b", _I),
        re.compile(r"\b(atm|gift ?cards?|bank transfer|wire transfer)\b", _I),
        re.compile(r"振込|振り込|送金|お金を(送|貸|下ろ|振)|ATM|口座|キャッシュカード|電子マネー|ギフトカード|立て替え"),
    ]),
    "code": ("asks for a code or password", [
        re.compile(r"\b(otp|pin|password|passcode|one[- ]time code|verification code|security code)\b", _I),
        re.compile(r"暗証番号|パスワード|認証コード|確認コード|ワンタイム"),
    ]),
    "card": ("contains a card or account number", [re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")]),
    "link": ("contains a link", [
        re.compile(r"https?://|www\.", _I),
        re.compile(r"\b[a-z0-9-]+\.(com|net|org|jp|co|io|ly|info|xyz|top|click)\b", _I),
    ]),
    "secrecy": ("asks her to keep it secret", [
        re.compile(r"\b(don'?t|do not) tell (anyone|anybody|your|kenji|him|her)\b|\bkeep (it|this) (a )?secret\b", _I),
        re.compile(r"誰にも言わない|内緒|秘密に"),
    ]),
    "phone": ("asks her to call a number", [
        re.compile(r"\b(call|dial|ring|text)\b.{0,30}\+?\d[\d -]{7,}\d", _I),
        re.compile(r"(?<!\d)0\d{1,4}-\d{1,4}-\d{3,4}(?!\d)"),
        re.compile(r"電話.{0,20}\d{2,4}-?\d{2,4}-?\d{3,4}"),
    ]),
    "pressure": ("pushes her to act right now", [
        re.compile(r"\b(right now|immediately|urgent(ly)?|today only|asap|before it'?s too late|hurry)\b", _I),
        re.compile(r"今すぐ|至急|急いで|大至急|本日中"),
    ]),
}
HARD_RULES = frozenset({"money", "code", "card", "link", "secrecy"})
NAMED_IN_A_WARNING = ("money", "code", "secrecy")  # what a scam warning has to name
SCAM_NAMED = "scam_named"


def check_outgoing(*texts: str, allow_soft: bool = False, warning: bool = False) -> GateResult:
    """Check every text that will be spoken or shown. ``allow_soft`` = the caregiver tapped "send anyway";
    ``warning`` = it warns about a scam the research found (see the module notes)."""
    joined = unicodedata.normalize("NFKC", "\n".join(t for t in texts if t))
    hits = [rule for rule, (_, patterns) in RULES.items() if any(p.search(joined) for p in patterns)]
    reasons = {r: RULES[r][0] for r in hits}
    if warning and (named := [r for r in hits if r in NAMED_IN_A_WARNING]):
        hits = [r for r in hits if r not in NAMED_IN_A_WARNING] + [SCAM_NAMED]
        reasons[SCAM_NAMED] = ("it warns about a scam, so it names what the scam wants ("
                               + ", ".join(RULES[r][0] for r in named) + "); read it once before it goes")
    blocking = [r for r in hits if r in HARD_RULES or not allow_soft]
    return GateResult(passed=not blocking, reasons=[reasons[r] for r in blocking], rules=blocking)
