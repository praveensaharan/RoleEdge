"""Fixed UI strings per recipient language (never machine-translated at runtime)."""

from __future__ import annotations

from datetime import date

from ..models.digest import TrustVerdict

HINDI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]

TRUST_BADGES: dict[str, dict[TrustVerdict, str]] = {
    "Hindi": {"looks_genuine": "भरोसेमंद लगता है", "unverified": "पक्का नहीं — एक बार जाँच लें",
              "likely_scam_or_misleading": "धोखा हो सकता है"},
    "English": {"looks_genuine": "Looks genuine", "unverified": "Not confirmed — check once",
                "likely_scam_or_misleading": "Could be a scam"},
    "Japanese": {"looks_genuine": "信頼できそうです", "unverified": "未確認です — 一度確かめましょう",
                 "likely_scam_or_misleading": "詐欺かもしれません"},
}

SENT_BY = {"Hindi": "{sender} ने भेजा · Saathi ने आसान बनाया", "English": "Sent by {sender} · made simple by Saathi",
           "Japanese": "{sender}から · Saathiがやさしく説明"}
DEADLINE = {"Hindi": "{day} तक", "English": "by {day}", "Japanese": "{day}まで"}


def _lang(language: str) -> str:
    return language if language in TRUST_BADGES else "English"


BADGE_ICONS: dict[TrustVerdict, str] = {"looks_genuine": "check", "unverified": "question",
                                        "likely_scam_or_misleading": "warning"}


def trust_badge(verdict: TrustVerdict, language: str) -> str:
    return TRUST_BADGES[_lang(language)][verdict]


def sent_by(sender: str, language: str) -> str:
    return SENT_BY[_lang(language)].format(sender=sender)


def format_day(iso_date: str, language: str) -> str:
    """'2026-11-20' in the recipient's words; text that isn't a YYYY-MM-DD date is shown as written."""
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    lang = _lang(language)
    if lang == "Hindi":
        return f"{d.day} {HINDI_MONTHS[d.month - 1]}"
    if lang == "Japanese":
        return f"{d.month}月{d.day}日"
    return d.strftime("%-d %B")


def deadline_phrase(iso_date: str, language: str) -> str:
    """'30 नवंबर तक' in Hindi (postposition), '11月30日まで' in Japanese, 'by 30 November' in English."""
    return DEADLINE[_lang(language)].format(day=format_day(iso_date, language))
