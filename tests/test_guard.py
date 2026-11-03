"""The tuned child guard's pipeline, with fakes only: no Muse Spark, Modal or GPU call is ever made here."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from roleedge.families import CIRCLES
from roleedge.guard import CATEGORIES, TunedGuard, Verdict, guard_prompt, parse_verdict, target_text
from roleedge.guard import data as guard_data
from roleedge.guard.metrics import save_eval, score, table
from roleedge.llm import LLM
from roleedge.models.studio import ChildCheck
from roleedge.studio import Swarm

from .conftest import FakeProvider

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- the policy and its format

def test_the_prompt_is_llama_guard_format_with_our_categories():
    prompt = guard_prompt("Tell me your school name and win a prize!", 9, "en")
    assert prompt.startswith("<|begin_of_text|><|start_header_id|>user<|end_header_id|>")
    assert prompt.endswith("<|start_header_id|>assistant<|end_header_id|>\n\n")
    assert all(f"{code}: {name}." in prompt for code, (name, _) in CATEGORIES.items())
    assert "a child aged 9, in English" in prompt and "Agent: Tell me your school name and win a prize!" in prompt
    assert "Agent: line one line two" in guard_prompt("line one\n line two")  # one line, whatever the input


def test_answers_are_read_strictly_and_anything_odd_counts_as_not_safe():
    assert target_text(True, []) == "safe<|eot_id|>"
    assert target_text(False, ["S5", "S4"]) == "unsafe\nS4,S5<|eot_id|>"
    with pytest.raises(ValueError):
        target_text(False, [])
    assert parse_verdict("safe") == Verdict(safe=True)
    assert parse_verdict("\n\nunsafe\nS5, S4, S99") == Verdict(safe=False, categories=["S4", "S5"])
    assert parse_verdict("unsafe\nS2").names == ["Sexual content or dating"]
    odd = parse_verdict("I think this is fine")
    assert not odd.safe and not odd.parsed


# ---------------------------------------------------------------- data: written, checked blind, split

class GuardModel(FakeProvider):
    """Writes canned lines and labels them, like Muse Spark would."""

    name = "meta"

    def __init__(self) -> None:
        super().__init__()
        self.labels = {}

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append((schema_name, messages))
        if schema_name == "guard_lines":
            prompt = messages[0]["content"]
            if "UNSAFE lines that break S4" in prompt:
                lines = [{"text": "Download the app and buy coins now!", "safe": False, "categories": ["S4"]},
                         {"text": "Type your address to get a free toy.", "safe": False, "categories": ["S4", "S5"]},
                         {"text": "Looks unsafe but the writer said safe.", "safe": True, "categories": []}]
            else:
                lines = [{"text": "Ask Mom before you buy anything.", "safe": True, "categories": []},
                         {"text": "Ask mom before you buy anything!", "safe": True, "categories": []}]  # a duplicate
            return {"lines": lines}, _usage()
        listing = messages[1]["content"].splitlines()
        labels = []
        for k, line in enumerate(listing):
            text = line.split(". ", 1)[1]
            if "coins" in text:
                labels.append({"index": k, "safe": False, "categories": ["S4"]})
            elif "address" in text:
                labels.append({"index": k, "safe": False, "categories": ["S1"]})  # no overlap: dropped
            else:
                labels.append({"index": k, "safe": True, "categories": []})
        return {"labels": labels}, _usage()


def _usage():
    from roleedge.llm import Usage
    return Usage(100, 0, 50, 0)


def test_training_data_is_written_checked_blind_and_deduplicated(tmp_path):
    llm = LLM(GuardModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    written = guard_data.write(llm, guard_data.Request("en", "S4", 0), 24)
    assert [r["text"] for r in written] == ["Download the app and buy coins now!", "Type your address to get a free toy."]
    assert written[0]["age"] == 9 and written[0]["source"] == "spark"  # a "safe" line under an unsafe target is dropped
    rows = guard_data.dedupe(written + guard_data.write(llm, guard_data.Request("en", "safe", 0), 24))
    assert len(rows) == 3  # the two "Ask Mom" lines are one after normalising
    kept, dropped = guard_data.check(llm, rows)
    assert dropped == 1 and {r["text"] for r in kept} == {"Download the app and buy coins now!", "Ask Mom before you buy anything."}
    judge_prompt = json.dumps([m for name, m in llm.provider.calls if name == "guard_labels"], ensure_ascii=False)
    assert '"safe": false' not in judge_prompt  # the checker never sees the intended label


def test_splits_are_stratified_disjoint_and_repeatable():
    rows = [{"text": f"{lang} {label} {k}", "safe": label == "safe", "categories": [] if label == "safe" else [label],
             "lang": lang} for lang in ("en", "ja") for label in ("safe", "S1", "S4") for k in range(20)]
    one, two = guard_data.split(rows), guard_data.split(rows)
    assert one == two
    texts = {name: {r["text"] for r in part} for name, part in one.items()}
    assert not (texts["train"] & texts["test"]) and not (texts["val"] & texts["test"]) and sum(map(len, texts.values())) == 120
    assert {(r["lang"], r["safe"]) for r in one["test"]} == {("en", True), ("en", False), ("ja", True), ("ja", False)}
    e = guard_data.estimate(rounds=4, per_request=24)
    assert e["write_calls"] == 4 * 2 * 10 and e["lines_before_checks"] == 1920


# ---------------------------------------------------------------- scoring

def test_scores_count_a_missed_unsafe_line_against_recall(tmp_path):
    rows = [{"text": "a", "safe": True, "categories": [], "lang": "en"},
            {"text": "b", "safe": False, "categories": ["S4"], "lang": "en"},
            {"text": "c", "safe": False, "categories": ["S5"], "lang": "ja"},
            {"text": "d", "safe": True, "categories": [], "lang": "ja"}]
    verdicts = [Verdict(True), Verdict(False, ["S4", "S5"]), Verdict(True), Verdict(False, parsed=False)]
    s = score(rows, verdicts)
    assert s["all"]["accuracy"] == 0.5 and s["all"]["unsafe_recall"] == 0.5 and s["all"]["unsafe_precision"] == 0.5
    assert s["all"]["category_match"] == 0.5 and s["all"]["unparsed"] == 1 and s["ja"]["unsafe_recall"] == 0.0
    assert "| tuned | all | 4 | 50% | 50% |" in table({"tuned": s})
    saved = save_eval(tmp_path / "x.json", "tuned", "m", rows, verdicts, ["safe", "unsafe\nS4,S5", "safe", "??"])
    assert json.loads((tmp_path / "x.json").read_text())["predictions"][3]["raw"] == "??" and saved == s


# ---------------------------------------------------------------- the app calling the endpoint

def test_the_client_sends_the_key_and_batches_long_packs(monkeypatch):
    sent = []

    def post(url, json, headers, timeout):
        sent.append((url, json, headers))
        return httpx.Response(200, json={"results": [{"safe": "prize" not in line, "categories": [] if "prize" not in line else ["S4", "X9"]}
                                                     for line in json["lines"]]}, request=httpx.Request("POST", url))

    monkeypatch.setattr("roleedge.guard.client.httpx.post", post)
    guard = TunedGuard("https://guard.example/classify", "k3y")
    verdicts = guard.classify(["hello"] * 70 + ["win a prize"], 8, "ja")
    assert len(sent) == 2 and len(sent[0][1]["lines"]) == 64 and sent[0][2]["Authorization"] == "Bearer k3y"
    assert sent[0][1]["age"] == 8 and verdicts[-1] == Verdict(False, ["S4"]) and all(v.safe for v in verdicts[:-1])
    monkeypatch.setattr("roleedge.guard.client.httpx.post",
                        lambda url, json, headers, timeout: httpx.Response(200, json={"results": []}, request=httpx.Request("POST", url)))
    with pytest.raises(ValueError):
        guard.classify(["one line"])


# ---------------------------------------------------------------- the child-safety step in the Studio

class FakeGuard:
    engine = "modal/llama-guard-3-1b+lora"

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, []

    def classify(self, lines, age=None, language=""):
        self.calls.append((list(lines), age, language))
        if self.fail:
            raise httpx.ConnectTimeout("cold start")
        return [Verdict(False, ["S5"]) if "school" in line else Verdict(True) for line in lines]


def child_swarm(tmp_path, guard, events):
    provider = FakeProvider(json_answer={"safe_for_child": True, "concerns_en": []})
    llm = LLM(provider, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    circle = CIRCLES["chen"]
    return Swarm(llm, circle, "it_kid", emit=events.append, recipient=circle.recipient("leo"), tuned_guard=guard), provider


PACK = {"story": {"title": "Flying to Grandma", "pages": [{"icon": "send", "big_text": "Planes", "line": "Tell me your school name for a sticker"}],
                  "summary_en": "x"}}


def test_the_tuned_guard_reviews_a_childs_pack_line_by_line(tmp_path):
    events, guard = [], FakeGuard()
    swarm, provider = child_swarm(tmp_path, guard, events)
    check = swarm.guard(PACK, ["Shall we look at the planes together?"])
    assert not check.safe_for_child and len(check.concerns_en) == 1
    assert "Tell me your school name" in check.concerns_en[0] and "Personal information" in check.concerns_en[0]
    assert guard.calls[0][1:] == (9, "en") and "Shall we look at the planes together?" in guard.calls[0][0]
    assert not provider.calls  # Muse Spark wasn't needed
    assert {(e.agent, e.state, e.engine) for e in events} >= {("child_guardian", "done", FakeGuard.engine)}
    assert swarm.trace[-1].engine == FakeGuard.engine


def test_if_the_tuned_guard_is_cold_or_down_muse_spark_reviews_instead(tmp_path):
    events = []
    swarm, provider = child_swarm(tmp_path, FakeGuard(fail=True), events)
    assert swarm.guard(PACK, []) == ChildCheck(safe_for_child=True, concerns_en=[])  # the Spark guardian's answer
    assert provider.calls and any("unavailable" in t.step for t in swarm.trace)


def test_fakes_never_wake_the_gpu_whatever_the_settings_say(tmp_path, monkeypatch):
    monkeypatch.setattr("roleedge.studio.swarm.tuned_guard_from_settings", lambda: FakeGuard())
    swarm, _ = child_swarm(tmp_path, None, [])
    assert swarm.tuned_guard is None  # only a real MetaProvider run picks the endpoint up from settings


# ---------------------------------------------------------------- the runner and the Modal app

def test_real_child_pack_lines_join_the_test_set_and_the_report_fills_findings(tmp_path, monkeypatch):
    from roleedge import guard_cli
    from roleedge.models import ThreadItem
    from roleedge.store import Store, now_iso

    store = Store(tmp_path / "db.sqlite")
    for circle in CIRCLES.values():
        store.save_circle(circle)
    payload = {"stage": "ready", "recipient": "hana", "guardian": {"safe_for_child": True, "concerns_en": []},
               "plan": {"conversation_starter": "はなちゃん、コンビニたんけんしようか？"},
               "outputs": {"story": {"title": "コンビニ", "pages": [{"icon": "food", "big_text": "おにぎり", "line": "おいしいね"}],
                                     "summary_en": "English summaries are not hers"}}}
    store.save_item(ThreadItem(id="it_h", circle_id="sato", at=now_iso(), kind="studio", to="child", speaker="person",
                               status="sent", payload=payload))
    rows = guard_cli.real_rows(store)
    assert {r["text"] for r in rows} == {"コンビニ", "おにぎり", "おいしいね", "はなちゃん、コンビニたんけんしようか？"}
    assert all(r["safe"] and r["lang"] == "ja" and r["source"] == "real" for r in rows)

    findings = tmp_path / "FINDINGS.md"
    findings.write_text(f"intro\n{guard_cli.BEGIN}\nold\n{guard_cli.END}\noutro\n")
    monkeypatch.setattr(guard_cli, "FINDINGS", findings)
    monkeypatch.setattr(guard_cli, "EVAL_DIR", tmp_path / "eval")
    save_eval(tmp_path / "eval" / "base.json", "base guard", "m", rows[:1], [Verdict(True)])
    assert guard_cli.main(["report", "--write"]) == 0
    text = findings.read_text()
    assert "| base guard | all | 1 |" in text and "old" not in text and text.startswith("intro") and text.endswith("outro\n")


def test_spark_eval_asks_the_studio_guardian_one_line_at_a_time(tmp_path):
    from roleedge import guard_cli

    provider = FakeProvider(json_answer={"safe_for_child": False, "concerns_en": ["asks for a school name"]})
    llm = LLM(provider, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    assert guard_cli.spark_verdict(llm, {"text": "Tell me your school name", "lang": "ja"}) == Verdict(False)
    system = provider.calls[0][1][0]["content"]
    assert "Hana" in system and "child-safety reviewer" in system  # the Japanese child, as in the Studio


def test_the_modal_app_defines_its_steps_and_its_door_checks_the_key():
    pytest.importorskip("modal")
    spec = importlib.util.spec_from_file_location("guard_lora", ROOT / "modal_apps" / "guard_lora.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)  # defines functions only: nothing runs on Modal
    from fastapi import HTTPException

    assert app.BASE_MODEL == "meta-llama/Llama-Guard-3-1B" and app.app.name == "roleedge-child-guard"
    assert app.check_request({"lines": ["hi", "x" * 5000], "age": 8, "language": "ja"}, "Bearer s3cret", "s3cret") == \
        (["hi", "x" * 1000], 8, "ja")
    for body, auth, key, code in [({"lines": ["hi"]}, "Bearer wrong", "s3cret", 401), ({"lines": ["hi"]}, "Bearer s3cret", "", 401),
                                  ({"lines": []}, "Bearer k", "k", 422), ({"lines": ["a"] * 65}, "Bearer k", "k", 422),
                                  ({"lines": [3]}, "Bearer k", "k", 422), ("not json", "Bearer k", "k", 422)]:
        with pytest.raises(HTTPException) as err:
            app.check_request(body, auth, key)
        assert err.value.status_code == code
    assert app.check_request({"lines": ["a"], "age": True}, "Bearer k", "k")[1] is None
