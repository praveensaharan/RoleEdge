"""Bad replies from model servers and odd model output fail with clear messages, or are handled, never with a
confusing crash deep inside json or datetime."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from roleedge.config import AzureConfig, MetaConfig
from roleedge.content import ContentItem, transform
from roleedge.llm import LLM, ProviderError, Usage, http
from roleedge.llm.azure import AzureProvider
from roleedge.llm.meta import MetaProvider
from roleedge.models import Action
from roleedge.render import build_calendar, card_html
from roleedge.render.i18n import format_day

from .conftest import FakeProvider, make_digest


def replies(monkeypatch, *responses):
    """Make httpx.post answer with `responses` in order, and record every sleep instead of sleeping."""
    queue, sleeps = list(responses), []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: queue.pop(0))
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    return sleeps


def test_retry_after_may_be_a_date_or_seconds_and_is_capped(monkeypatch):
    soon = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    sleeps = replies(monkeypatch, httpx.Response(429, headers={"retry-after": soon}),
                     httpx.Response(503, headers={"retry-after": "9999"}),
                     httpx.Response(503, headers={"retry-after": "soon-ish"}), httpx.Response(200, json={"ok": 1}))
    assert http.post_json("azure", "https://x.example", {}, {}) == {"ok": 1}
    assert 20 <= sleeps[0] <= 30 and sleeps[1] == http.MAX_RETRY_WAIT and sleeps[2] == 8  # garbage -> backoff


def test_a_reply_that_is_not_json_is_a_clear_provider_error(monkeypatch):
    replies(monkeypatch, httpx.Response(200, text="<html>Bad gateway</html>"))
    with pytest.raises(ProviderError, match="not JSON.*Bad gateway"):
        http.post_json("azure", "https://x.example", {}, {})
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, text="oops",
                                                                       request=httpx.Request("GET", "https://x")))
    with pytest.raises(ProviderError, match="not JSON"):
        http.get_json("meta", "https://x.example", {})


def azure(monkeypatch, data):
    provider = AzureProvider(AzureConfig("https://x.example", "k", "gpt5mini"))
    monkeypatch.setattr(provider, "_completions", lambda model, body: data)
    return provider


def test_azure_cut_off_or_empty_replies_say_why(monkeypatch):
    cut = {"choices": [{"message": {"content": '{"reply": "हा'}, "finish_reason": "length"}], "usage": {}}
    with pytest.raises(ProviderError, match="no complete JSON.*finish_reason: length"):
        azure(monkeypatch, cut).complete_json([], {}, "x")
    with pytest.raises(ProviderError, match="no choices"):
        azure(monkeypatch, {"error": "busy"}).chat([])
    broken = {"choices": [{"message": {"content": "{nope"}, "finish_reason": "stop"}], "usage": {}}
    with pytest.raises(ProviderError, match="not valid JSON"):
        azure(monkeypatch, broken).complete_json([], {}, "x")


def test_meta_incomplete_replies_say_why(monkeypatch):
    provider = MetaProvider(MetaConfig("k", "https://api.meta.ai/v1/responses", "muse-spark-1.3"))
    partial = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
               "output": [{"type": "message", "content": [{"text": '{"reply": "हा'}]}]}
    monkeypatch.setattr(provider, "_respond", lambda body: partial)
    with pytest.raises(ProviderError, match="no complete JSON.*max_output_tokens"):
        provider.complete_json([], {}, "x")


def action(due_time):
    return Action(title="Book", title_local="予約", due_date="2026-11-20", due_time=due_time, how="phone",
                  remind_days_before=[1], add_to_calendar=True)


def test_common_time_formats_are_read_as_hh_mm():
    assert [action(t).due_time for t in ("10:00 AM", "6 pm", "6:30 p.m.", "18.30", "12 am", "午後5時", "10時半", None)] \
        == ["10:00", "18:00", "18:30", "18:30", "00:00", "17:00", "10:30", None]
    assert action("around noon").due_time == "around noon"  # unreadable: kept as written, never guessed


def test_calendar_keeps_an_unreadable_time_instead_of_crashing():
    digest = make_digest(actions=[action("around noon").model_dump()])
    ics = build_calendar(digest, "x", timezone="Asia/Tokyo").decode()
    assert "DTSTART;VALUE=DATE:20261120" in ics and "(around noon)" in ics


def action_on(due_date):
    return Action(title="Book", title_local="予約", due_date=due_date, due_time=None, how="phone",
                  remind_days_before=[1], add_to_calendar=True)


def test_common_date_formats_are_read_as_iso():
    written = ("2026/11/20", "2026年11月20日", "２０２６年１１月２０日", "20 Nov 2026", "November 20, 2026",
               "20th November 2026", "20/11/2026", "11/20/2026", "2026-11-20")
    assert [action_on(d).due_date for d in written] == ["2026-11-20"] * len(written)
    assert action_on(None).due_date is None
    for vague in ("05/11/2026", "20 Nov", "next Friday", "2026-02-30"):  # ambiguous, no year, or impossible
        assert action_on(vague).due_date == vague  # kept as written, never guessed


def digest_with_dates(first, second="2026-11-05"):
    actions = make_digest().model_dump()["actions"]
    actions[0]["due_date"], actions[1]["due_date"] = first, second
    return make_digest(actions=actions)


class BadDateDigest(FakeProvider):
    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        if schema_name == "care_digest":
            return digest_with_dates("next Friday").model_dump(), Usage(1, 0, 1, 0)
        return {"issues": []}, Usage(1, 0, 1, 0)


def test_an_unreadable_date_is_held_for_the_sender(tmp_path, hindi_recipient):
    llm = LLM(BadDateDigest(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    record = transform(llm, "bill", "a bill", ContentItem("Bill: early payment by 5 Nov at 6 pm"), "mummy", hindi_recipient, "2026-10-28")
    assert record.held_action_indexes == {0}
    assert [(i.path, i.needs_review, i.applied) for i in record.verify_issues] == [("actions[0].due_date", True, False)]


def test_the_renderer_never_crashes_on_an_unreadable_date(hindi_recipient):
    digest = digest_with_dates("next Friday")
    assert build_calendar(digest, "x", timezone="Asia/Kolkata").decode().count("BEGIN:VEVENT") == 1  # the good one
    assert "5 नवंबर" in card_html(digest, hindi_recipient)  # the readable deadline still shows
    assert format_day("next Friday", "Hindi") == "next Friday"
