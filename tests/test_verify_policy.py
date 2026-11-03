from roleedge.content import ContentItem, transform
from roleedge.content.verify import (
    apply_fixes,
    date_mentions,
    recipient_view,
    set_path,
    source_days,
    source_times,
    unsupported_dates,
)
from roleedge.llm import LLM, Usage
from roleedge.models import VerifyIssue

from .conftest import FakeProvider, make_digest


def doc():
    return make_digest().model_dump()


def issue(path, text="नया"):
    return VerifyIssue(path=path, severity="major", problem="p", corrected_text=text)


def test_set_path_nested_and_indexed():
    d = doc()
    assert set_path(d, "storyboard[0].narration", "नई लाइन")
    assert d["storyboard"][0]["narration"] == "नई लाइन"
    assert set_path(d, "reply_suggestions[0]", "हाँ")
    assert d["reply_suggestions"][0] == "हाँ"


def test_set_path_rejects_unknown_or_non_text_fields():
    d = doc()
    assert not set_path(d, "nope.field", "x")
    assert not set_path(d, "actions[9].title_local", "x")
    assert not set_path(d, "storyboard[0].seconds", "9")  # integers are not text
    assert not set_path(d, "", "x")


def test_dates_are_never_changed_automatically():
    d = doc()
    reviewed = apply_fixes(d, [issue("actions[0].due_date", "null"), issue("actions[1].due_time", "09:00")])
    assert [r.needs_review for r in reviewed] == [True, True]
    assert not any(r.applied for r in reviewed)
    assert d["actions"][0]["due_date"] == "2026-11-12"
    assert d["actions"][1]["due_time"] == "18:00"


def test_wording_fixes_are_applied_and_alias_resolved():
    d = doc()
    reviewed = apply_fixes(d, [issue("voice_note_script", "नमस्ते मम्मी"), issue("trust_advice_local", "सावधान")])
    assert all(r.applied for r in reviewed)
    assert d["voice_note_script"] == "नमस्ते मम्मी"
    assert d["trust"]["advice_local"] == "सावधान"


def test_recipient_view_hides_sender_only_fields_but_shows_dates_and_times():
    view = recipient_view(doc())
    assert "simple_summary" not in view and "title" not in view
    assert view["actions"] == [{"title_local": "भुगतान करें", "due_date": "2026-11-12", "due_time": None},
                               {"title_local": "जल्दी भुगतान", "due_date": "2026-11-05", "due_time": "18:00"}]


def test_a_text_fix_that_changes_a_date_or_time_is_held():
    d = doc()
    d["regional"]["article"] = "आख़िरी तारीख 12‑11‑2026 है।"
    d["storyboard"][0]["narration"] = "12 नवंबर तक बिल भरें"
    d["voice_note_script"] = "शाम 6 बजे तक जमा करें"
    d["reply_suggestions"][0] = "Pay by Friday"
    reviewed = apply_fixes(d, [issue("regional.article", "आख़िरी तारीख 15‑11‑2026 है।"),
                               issue("storyboard[0].narration", "12 दिसंबर तक बिल भरें"),
                               issue("voice_note_script", "शाम 7 बजे तक जमा करें"),
                               issue("reply_suggestions[0]", "Pay by Monday")])
    assert [(r.needs_review, r.applied) for r in reviewed] == [(True, False)] * 4
    assert d["regional"]["article"] == "आख़िरी तारीख 12‑11‑2026 है।"
    assert d["storyboard"][0]["narration"] == "12 नवंबर तक बिल भरें"


def test_a_text_fix_that_only_rewords_around_a_date_is_applied():
    d = doc()
    d["regional"]["title"] = "बिजली बिल: ₹1,846 — देय 12‑Nov‑2026"
    d["voice_note_script"] = "Exhibition on 14 Nov, 9:30 AM. बोल रही हूँ"
    reviewed = apply_fixes(d, [issue("regional.title", "बिजली बिल: ₹1,846 — देय 12‑नवम्बर‑2026"),
                               issue("voice_note_script", "Exhibition on 14 November, 09:30 am. Saathi here")])
    assert [(r.needs_review, r.applied) for r in reviewed] == [(False, True)] * 2
    assert d["regional"]["title"].endswith("12‑नवम्बर‑2026")


def test_date_mentions_are_compared_in_one_form():
    assert date_mentions("देय 12‑Nov‑2026, 9:30 AM") == date_mentions("देय १२ नवम्बर 2026, 09:30am")
    assert date_mentions("1–30 नवम्बर") != date_mentions("1–31 नवम्बर")
    assert date_mentions("कल आइए") != date_mentions("परसों आइए")
    assert date_mentions("₹1,846 और 214 यूनिट") == []  # amounts are not dates


def test_set_path_only_replaces_text_with_text():
    d = doc()
    assert not set_path(d, "storyboard[0]", "बिल भरें")  # a whole scene
    assert not set_path(d, "actions[0]", "x")  # a whole action
    assert not set_path(d, "regional.summary", "x")  # a whole list
    assert not set_path(d, "voice_note_script", "null")  # "null" is for dates, which are held; text is never deleted
    assert d == doc()


class ScriptedChecker(FakeProvider):
    """The first call writes the digest; the checker then returns fixes that do not fit the digest."""

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append(("json", messages))
        if schema_name == "care_digest":
            return make_digest().model_dump(), Usage(100, 0, 50, 0)
        return {"issues": [issue("storyboard[0]", "बिल भरें").model_dump(), issue("voice_note_script", "null").model_dump(),
                           issue("regional.article", "नया लेख").model_dump()]}, Usage(100, 0, 50, 0)


def test_fixes_that_do_not_fit_are_skipped_and_the_content_step_still_finishes(tmp_path, hindi_recipient):
    llm = LLM(ScriptedChecker(), cache_dir=tmp_path / "cache", ledger_file=tmp_path / "usage.jsonl")
    record = transform(llm, "bill", "a bill", ContentItem("Bill: pay by 12 Nov; early payment by 5 Nov, 6 pm"), "mummy", hindi_recipient, "2026-10-28")
    assert [i.applied for i in record.verify_issues] == [False, False, True]
    assert record.digest.storyboard == record.draft_before_verify.storyboard
    assert record.digest.voice_note_script == "नमस्ते" and record.digest.regional.article == "नया लेख"


def test_japanese_dates_and_times_are_recognised():
    assert date_mentions("予約締切：11月20日（金曜日）午後5時まで") == date_mentions("予約は１１月２０日(金曜)午後５時までです")
    assert date_mentions("11月20日まで") != date_mentions("11月27日まで")
    assert date_mentions("明日の10時半") != date_mentions("明後日の10時半")
    assert set(date_mentions("期間：2026年11月4日〜12月11日")) == {"2026年11月4日", "12月11日"}


def test_a_japanese_fix_that_moves_a_date_is_held_and_rewording_is_applied():
    d = doc()
    d["regional"]["article"] = "予約締切は11月20日です。"
    d["voice_note_script"] = "予約締切は11月20日です。"
    reviewed = apply_fixes(d, [issue("regional.article", "予約締切は11月27日です。"),
                               issue("voice_note_script", "予約のしめきりは11月20日です。")])
    assert [(r.needs_review, r.applied) for r in reviewed] == [(True, False), (False, True)]
    assert d["regional"]["article"] == "予約締切は11月20日です。"


def test_dates_and_times_are_read_from_the_source_text():
    text = ("Held on Friday, 14 November 2026 from 9:30 AM to 12:30 PM. Submit by 7 Nov. 1–30 नवम्बर, शाम 6 बजे. "
            "予約締切：11月20日（金曜日）午後5時まで. Due 12/11/2026.")
    assert {(11, 14), (11, 7), (11, 1), (11, 30), (11, 20), (11, 12), (12, 11)} <= source_days(text)
    assert {(9, 30), (12, 30), (18, 0), (17, 0)} <= source_times(text)


def test_a_date_or_time_the_shared_text_never_mentions_is_held():
    d = doc()  # actions: 2026-11-12 (no time) and 2026-11-05 at 18:00
    held = unsupported_dates(d, "Pay by 12 November. Early payment by 5 Nov gets a rebate.", has_images=False)
    assert [(i.path, i.needs_review, i.applied) for i in held] == [("actions[1].due_time", True, False)]
    assert unsupported_dates(d, "Pay by 12 November. Early payment by 5 Nov, 6 pm.", has_images=False) == []
    # a photo whose text has no dates at all: the dates came from the image, so the checker stays responsible
    assert unsupported_dates(d, "Shared item: a photo of a bill.", has_images=True) == []
    # text that does mention dates, just not these: still held, even with images
    assert [i.path for i in unsupported_dates(d, "From 1st October.", has_images=True)] == \
        ["actions[0].due_date", "actions[1].due_date"]
