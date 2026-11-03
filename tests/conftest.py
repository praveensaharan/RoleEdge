"""Shared test fixtures. Tests never call a real model API or read .env."""

from __future__ import annotations

from typing import Any

import pytest

from roleedge.llm import ChatReply, Provider, ToolTurn, Usage
from roleedge.models import Digest, Recipient


class FakeProvider(Provider):
    """Records calls and returns canned answers."""

    name = "fake"
    label = "Fake"
    efforts = ("minimal", "low")

    def __init__(self, json_answer: dict[str, Any] | None = None, fail: Exception | None = None) -> None:
        self.json_answer = json_answer or {}
        self.fail = fail
        self.calls: list[tuple[str, Any]] = []

    @property
    def default_model(self) -> str:
        return "fake-1"

    def list_models(self) -> list[str]:
        return ["fake-1", "fake-2"]

    def chat(self, messages, *, model=None, effort="low", max_output_tokens=16000) -> ChatReply:
        self.calls.append(("chat", messages))
        if self.fail:
            raise self.fail
        return ChatReply(text="hello", usage=Usage(10, 4, 3, 1), model=model or self.default_model)

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append(("json", messages))
        return self.json_answer, Usage(100, 0, 50, 10)

    def call_tools(self, messages, tools, *, effort="low", model=None):
        self.calls.append(("tools", messages))
        return ToolTurn("ok", []), Usage(10, 0, 5, 0)


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def hindi_recipient() -> Recipient:
    return Recipient(call_name="Mummy", full_name="Kamla Sharma", role="parent", age=68, language="Hindi",
                     script="Devanagari", timezone="Asia/Kolkata", reading="reads slowly", sender="Rohit (her son)")


@pytest.fixture
def english_recipient() -> Recipient:
    return Recipient(call_name="Aarav", full_name="Aarav Sharma", role="child", age=9, language="English",
                     script="Latin", timezone="Asia/Kolkata", reading="9-year-old", sender="Papa (Rohit)")


def make_digest(**overrides: Any) -> Digest:
    data: dict[str, Any] = {
        "title": "Pay the bill", "one_line": "Bill due 12 Nov.", "simple_summary": ["Pay the bill."],
        "key_points": [{"icon": "info", "text": "Pay on time"}],
        "trust": {"verdict": "looks_genuine", "reason": "Looks like a real bill.", "advice_local": "ठीक है"},
        "actions": [
            {"title": "Pay", "title_local": "भुगतान करें", "due_date": "2026-11-12", "due_time": None, "how": "Online",
             "remind_days_before": [7, 1], "add_to_calendar": True},
            {"title": "Early rebate", "title_local": "जल्दी भुगतान", "due_date": "2026-11-05", "due_time": "18:00",
             "how": "Pay early", "remind_days_before": [1], "add_to_calendar": True},
        ],
        "regional": {"language": "Hindi", "title": "बिल", "summary": ["बिल भरें"], "article": "लेख"},
        "illustration": {"layout": "steps", "headline": "क्या करना है",
                         "panels": [{"icon": "bill", "heading": "बिल", "caption": "₹1,846"}]},
        "storyboard": [{"icon": "bill", "big_text": "बिल", "caption": "₹1,846", "narration": "बिल भरें", "seconds": 4}],
        "voice_note_script": "नमस्ते", "reply_suggestions": ["ठीक है"],
    }
    data.update(overrides)
    return Digest.model_validate(data)


@pytest.fixture
def digest() -> Digest:
    return make_digest()
