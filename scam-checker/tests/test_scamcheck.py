"""The kit with fakes only: no Meta, Modal or GPU call is made. Run with `python -m pytest tests -q`."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scamcheck import SCAM_TYPES, messages, parse_answer, target  # noqa: E402
from scamcheck import build as build_  # noqa: E402
from scamcheck import generate as gen  # noqa: E402
from scamcheck.metrics import score, table  # noqa: E402
from scamcheck.model_card import card  # noqa: E402
from scamcheck.policy import SHORT_SYSTEM, flags_in, foreign_hanzi  # noqa: E402

REFUND = "【市役所】医療費の還付金があります。本日中にお近くのATMで手続きしてください。"


# ---------------------------------------------------------------- the prompt and the answer format

def test_prompts_full_for_untrained_models_short_for_the_tuned_one():
    row = {"text": REFUND, "channel": "phone", "sender": "+81 3-0000-0000"}
    system, user = messages(row)
    assert all(f"- {code}:" in system["content"] for code in SCAM_TYPES)
    assert user["content"] == f"Channel: Phone call (written out)\nSender: +81 3-0000-0000\nMessage:\n{REFUND}"
    assert messages(row, short=True)[0]["content"] == SHORT_SYSTEM and len(SHORT_SYSTEM) * 10 < len(system["content"])


def test_the_target_is_compact_json_and_reads_back():
    scam = {"text": REFUND, "scam": True, "type": "refund", "red_flags": ["ATMで手続き"], "advice": "家族に確認しましょう。"}
    assert target(scam) == '{"scam":true,"type":"refund","red_flags":["ATMで手続き"],"advice":"家族に確認しましょう。"}'
    assert parse_answer(target(scam)).type == "refund"
    assert target({"text": "x", "scam": False, "type": "none"}) == '{"scam":false,"type":"none","red_flags":[],"advice":""}'
    with pytest.raises(ValueError):
        target({"text": "x", "scam": True, "type": "none"})


def test_odd_answers_count_as_a_scam():
    assert parse_answer('Sure: {"scam": false, "type": "none"}').scam is False
    assert parse_answer('{"scam": true, "type": "lottery", "red_flags": ["a", "b", "c", "d", "e"]}').type == "other"
    for broken in ("I think it is fine", '{"scam": "no"}', "{not json}", ""):
        assert parse_answer(broken).scam and not parse_answer(broken).parsed


def test_red_flags_and_chinese_characters_are_checked_by_code():
    assert flags_in(REFUND, ["ＡＴＭで 手続き", "本日中", "今すぐ振り込んで"]) == ["ＡＴＭで 手続き", "本日中"]
    assert foreign_hanzi("【東京国税局】确定申告に関するお知らせ") == "确" and foreign_hanzi(REFUND) == ""


# ---------------------------------------------------------------- generate: written, checked blind

class FakeSpark:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list]] = []

    def json(self, task, msgs, schema, name, effort="low"):
        self.calls.append((name, msgs))
        if name == "scam_messages":
            if "SCAM messages of type refund" in msgs[0]["content"]:
                return {"messages": [
                    {"channel": "phone", "sender": "", "text": REFUND, "scam": True, "type": "refund",
                     "red_flags": ["ATMで手続き", "made up"], "advice": "電話を切りましょう。"},
                    {"channel": "sms", "sender": "", "text": "還付金のお知らせ。リンクから受け取り。", "scam": True,
                     "type": "refund", "red_flags": ["not in the text"], "advice": "x"},
                    {"channel": "sms", "sender": "", "text": "【国税局】确定申告の還付はATMで。", "scam": True,
                     "type": "refund", "red_flags": ["ATMで"], "advice": "x"}]}
            return {"messages": [
                {"channel": "line", "sender": "母", "text": "今日の夕飯はカレーだよ。7時に帰るね。", "scam": False,
                 "type": "none", "red_flags": [], "advice": ""},
                {"channel": "sms", "sender": "", "text": "市役所からのお知らせ：詐欺に注意してください。", "scam": False,
                 "type": "none", "red_flags": [], "advice": ""}]}
        labels = []
        for k, block in enumerate(msgs[1]["content"].split("\n\n")):
            if "ATM" in block:
                labels.append({"index": k, "scam": True, "type": "refund"})
            elif "詐欺に注意" in block:
                labels.append({"index": k, "scam": True, "type": "fake_official"})  # disagrees: dropped
            else:
                labels.append({"index": k, "scam": False, "type": "none"})
        return {"labels": labels}


def test_generated_rows_are_checked_by_code_then_blind(tmp_path):
    api = FakeSpark()
    scams = gen.write(api, gen.Request("refund", 0), 20)
    assert [r["text"] for r in scams] == [REFUND] and scams[0]["red_flags"] == ["ATMで手続き"]
    kept = gen.check(api, scams + gen.write(api, gen.Request("lookalike:refund", 0), 20))
    assert {r["text"] for r in kept} == {REFUND, "今日の夕飯はカレーだよ。7時に帰るね。"}
    judge = json.dumps([m for name, m in api.calls if name == "scam_labels"], ensure_ascii=False)
    assert "電話を切りましょう" not in judge  # the judge never sees the labels
    assert len(gen.requests(2, start=3)) == 42 and gen.requests(1, start=3)[0].round == 3
    assert gen.estimate(20, 20)["write_calls"] == 420


# ---------------------------------------------------------------- build: your cases, real messages, splits

def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}))
        writer.writeheader()
        writer.writerows(rows)


def test_build_checks_cases_keeps_real_out_of_training_and_splits(tmp_path):
    data = tmp_path / "data"
    synthetic = [{"text": f"本物のお知らせ {k} です。", "scam": False, "type": "none", "target": "everyday", "channel": "line"}
                 for k in range(40)]
    synthetic.append({"text": REFUND, "scam": True, "type": "refund", "red_flags": ["本日中"], "advice": "x", "target": "refund"})
    (data / "synthetic").mkdir(parents=True)
    (data / "synthetic" / "spark.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in synthetic))
    _csv(data / "cases" / "mine.csv", [
        {"text": "お母さん、俺だけど新しい番号。今日中に50万必要。", "scam": "yes", "type": "family_impersonation",
         "red_flags": "新しい番号|今日中に50万必要", "advice": "電話を切りましょう。", "split": "test"},
        {"text": "これは詐欺です。ATMへ。", "scam": "yes", "type": "lottery", "red_flags": "ATM", "advice": "x"},
        {"text": "これも詐欺です。ATMへ。", "scam": "yes", "type": "refund", "red_flags": "コンビニ", "advice": "x"},
    ])
    _csv(data / "cases" / "_template.csv", [{"text": "ignored", "scam": "maybe"}])
    _csv(data / "real" / "published.csv", [
        {"text": REFUND, "scam": "yes", "type": "refund", "source_url": "https://example.org/warning"},
        {"text": "出典のない本物のメッセージです。", "scam": "no"},
    ])
    stats, problems = build_.build(data)
    assert len(problems) == 3  # unknown type, a red flag not in the text, a real row without a source
    assert any("mine.csv:3" in p and "lottery" in p for p in problems)
    assert any("mine.csv:4" in p and "コンビニ" in p for p in problems)
    assert stats["removed_because_in_real_test"] == 1  # the refund message is in the real test set
    final = {p.stem: [json.loads(x) for x in p.read_text().splitlines()] for p in (data / "final").glob("*.jsonl")}
    assert [r["text"] for r in final["real_test"]] == [REFUND]
    assert any(r["origin"] == "cases" for r in final["test"])  # split=test is honoured
    assert all(r["text"] != REFUND for name in ("train", "val", "test") for r in final[name])
    assert sum(len(final[n]) for n in ("train", "val", "test")) == 41


# ---------------------------------------------------------------- scoring, the model card, the Modal helpers

def test_scores_count_missed_scams_and_false_alarms():
    rows = [{"text": REFUND, "scam": True, "type": "refund", "red_flags": ["本日中"]},
            {"text": "お知らせ", "scam": False, "type": "none"},
            {"text": "お母さん、俺", "scam": True, "type": "family_impersonation", "red_flags": ["俺"]},
            {"text": "本物", "scam": False, "type": "none"}]
    answers = [parse_answer(a) for a in ('{"scam": true, "type": "refund", "red_flags": ["本日中に"]}', '{"scam": true}',
                                         '{"scam": false}', "??")]
    s = score(rows, answers)
    assert s["catch_rate"] == 0.5 and s["false_alarms"] == 1.0 and s["type_match"] == 1.0 and s["flag_match"] == 1.0
    assert s["unparsed"] == 1
    text = card("me/glimmer-scam-checker-ja", "meta-models/Muse-Glimmer-30B", {"Glimmer v1": {"test": s}})
    assert "license: apache-2.0" in text and "| Glimmer v1 | test | 4 | 50% | 100% |" in text and table({}) in text


def test_the_answer_is_read_from_the_answer_channel():
    modal_train = pytest.importorskip("modal_train")
    raw = ' to=self<|message|>{"draft": 1}<|eom|><|start|>assistant to=user<|message|>{"scam": false}<|eot|>'
    assert modal_train._final(raw) == '{"scam": false}'
    assert modal_train._final('{"scam": true, "type": "refund"}<|eot|><|finetune_right_pad|>') == '{"scam": true, "type": "refund"}'
