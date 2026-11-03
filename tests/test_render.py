from datetime import timedelta

from icalendar import Calendar

from roleedge.content.prompts import DIGEST_SYSTEM
from roleedge.demo import RECIPIENTS, TODAY
from roleedge.render import build_calendar, card_html
from roleedge.render.i18n import deadline_phrase, sent_by, trust_badge

from .conftest import make_digest


def test_deadline_phrase_word_order():
    assert deadline_phrase("2026-11-30", "Hindi") == "30 नवंबर तक"
    assert deadline_phrase("2026-11-07", "English") == "by 7 November"
    assert deadline_phrase("2026-11-07", "Tamil") == "by 7 November"  # unknown language falls back to English


def test_card_keeps_css_font_stack_unescaped(digest, hindi_recipient):
    html = card_html(digest, hindi_recipient)
    assert "font-family: 'Inter','Noto Sans Devanagari'" in html  # escaping quotes here broke Hindi rendering


def test_card_escapes_model_text_and_drops_emoji(hindi_recipient):
    d = make_digest(illustration={"layout": "steps", "headline": "<script>x</script> 📅", "panels": []})
    html = card_html(d, hindi_recipient)
    assert "<script>x" not in html and "&lt;script&gt;" in html
    assert "📅" not in html


def test_card_hides_deadline_for_scams_and_held_dates(digest, hindi_recipient):
    assert "5 नवंबर तक" in card_html(digest, hindi_recipient)
    assert "5 नवंबर तक" not in card_html(digest, hindi_recipient, held={1})
    scam = make_digest(trust={"verdict": "likely_scam_or_misleading", "reason": "r", "advice_local": "a"})
    assert "नवंबर तक" not in card_html(scam, hindi_recipient)


def test_calendar_events_and_reminders(digest):
    cal = Calendar.from_ical(build_calendar(digest, "case", timezone="Asia/Kolkata"))
    events = list(cal.walk("VEVENT"))
    assert len(events) == 2
    all_day = events[0]
    assert str(all_day["dtstart"].dt) == "2026-11-12"
    triggers = sorted(a["trigger"].dt for a in all_day.walk("VALARM"))
    assert triggers == [timedelta(days=-7, hours=10), timedelta(days=-1, hours=10)]  # 10:00 local
    timed = events[1]
    assert timed["dtstart"].dt.hour == 18


def test_calendar_skips_held_actions_and_returns_none_when_empty(digest):
    assert len(list(Calendar.from_ical(build_calendar(digest, "c", held={0}, timezone="Asia/Kolkata")).walk("VEVENT"))) == 1
    assert build_calendar(digest, "c", held={0, 1}, timezone="Asia/Kolkata") is None


def test_japanese_labels_and_dates():
    assert deadline_phrase("2026-11-20", "Japanese") == "11月20日まで"
    assert trust_badge("likely_scam_or_misleading", "Japanese") == "詐欺かもしれません"  # the card draws the icon
    assert sent_by("Kenji", "Japanese") == "Kenjiから · Saathiがやさしく説明"


def test_calendar_uses_the_recipients_timezone(digest):
    assert "TZID=Asia/Tokyo" in build_calendar(digest, "x", timezone="Asia/Tokyo").decode()


def test_digest_prompt_for_the_demo_family_is_unchanged():
    assert "today is 2026-10-28 (Asia/Kolkata)." in DIGEST_SYSTEM.format(today=TODAY, **RECIPIENTS["mummy"].model_dump())
