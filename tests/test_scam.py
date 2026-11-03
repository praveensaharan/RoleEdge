"""The scam checker's prompt and answer format as the app uses them (the training kit in scam-checker/ has its own
tests for the data, scoring and Modal helpers)."""

from __future__ import annotations

from pathlib import Path

import pytest

from roleedge.scam import SCAM_TYPES, messages, parse_answer, target
from roleedge.scam.policy import SHORT_SYSTEM, flags_in, foreign_hanzi

ROOT = Path(__file__).resolve().parents[1]
REFUND = "【市役所】医療費の還付金があります。本日中にお近くのATMで手続きしてください。"


def test_the_app_and_the_training_kit_use_the_same_policy_file():
    kit = ROOT / "scam-checker" / "scamcheck" / "policy.py"
    if not kit.exists():
        pytest.skip("the training kit has been moved out of the repository")
    assert kit.read_text(encoding="utf-8") == (ROOT / "src" / "roleedge" / "scam" / "policy.py").read_text(encoding="utf-8")


def test_untrained_models_get_every_scam_type_and_the_tuned_one_the_short_prompt():
    row = {"text": REFUND, "channel": "phone", "sender": "+81 3-0000-0000"}
    system, user = messages(row)
    assert all(f"- {code}:" in system["content"] for code in SCAM_TYPES)
    assert user["content"] == f"Channel: Phone call (written out)\nSender: +81 3-0000-0000\nMessage:\n{REFUND}"
    assert messages(row, short=True)[0]["content"] == SHORT_SYSTEM
    assert "Sender" not in messages({"text": "こんにちは"})[1]["content"]


def test_answers_are_read_strictly_and_anything_odd_counts_as_a_scam():
    scam = {"text": REFUND, "scam": True, "type": "refund", "red_flags": ["ATMで手続き"], "advice": "家族に確認しましょう。"}
    assert parse_answer(target(scam)).type == "refund"
    assert parse_answer('Here you go: {"scam": false, "type": "none", "red_flags": [], "advice": ""}').scam is False
    odd_type = parse_answer('{"scam": true, "type": "lottery", "red_flags": ["a", "b", "c", "d", "e"]}')
    assert odd_type.type == "other" and len(odd_type.red_flags) == 4 and odd_type.parsed
    for broken in ("I think it is fine", '{"scam": "no"}', "{not json}", ""):
        answer = parse_answer(broken)
        assert answer.scam and not answer.parsed
    with pytest.raises(ValueError):
        target({"text": "x", "scam": True, "type": "none"})


def test_red_flags_and_chinese_characters_are_checked_by_code():
    assert flags_in(REFUND, ["ＡＴＭで 手続き", "本日中", "今すぐ振り込んで"]) == ["ＡＴＭで 手続き", "本日中"]
    assert foreign_hanzi("【東京国税局】确定申告に関するお知らせ") == "确" and foreign_hanzi(REFUND + "檢察庁") == ""
