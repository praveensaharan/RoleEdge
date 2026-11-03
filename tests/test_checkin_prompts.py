"""The check-in call must follow whichever care plan it is given, not the demo family."""

import json
import re

from roleedge.checkin import run_call
from roleedge.checkin.prompts import AGENT_SYSTEM, REPORT_SYSTEM, prompt_fields
from roleedge.checkin.tools import TOOLS
from roleedge.llm import LLM, ToolCall, ToolTurn, Usage
from roleedge.models import CarePlan
from roleedge.models.checkin import CallReport

from .conftest import FakeProvider

OTHER_FAMILY = CarePlan.model_validate({  # a parent in Japan: other language, other emergency number
    "parent": {"call_name": "Okaasan", "full_name": "Yoshiko Sato", "age": 81, "language": "Japanese",
               "script": "kanji and kana", "lives": "alone, Sendai; talks to few people most days"},
    "caregiver": {"name": "Kenji", "relation": "son", "status_now": "at work in Tokyo until 7 pm"},
    "conditions": ["arthritis"],
    "medicines": [{"name": "Calcium 500 mg", "when": "after breakfast"}],
    "diet": "low salt",
    "upcoming": ["Eye check-up on 3 Dec"],
    "food_ordering": "not allowed",
    "emergency": "119; Kenji 090-XXXX-XXX1",
    "emergency_number": "119",
    "call_time": "9:15 am",
})
DEMO_FAMILY_WORDS = ("Rohit", "Mummy", "Kamla", "Hindi", "Devanagari", "1:30", "112",
                     " her ", " she ", " him ", " he ")


class ShortCall(FakeProvider):
    """Saathi greets, the parent answers once, Saathi hangs up."""

    turns = [ToolTurn("おはようございます", []), ToolTurn(None, [ToolCall("c1", "end_call", '{"closing_summary": "ok"}')]),
             ToolTurn("bye", [])]

    def call_tools(self, messages, tools, *, effort="low", model=None):
        self.calls.append(("tools", messages))
        return self.turns[sum(kind == "tools" for kind, _ in self.calls) - 1], Usage(10, 0, 5, 0)

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append(("json", messages))
        return {"reply": "元気よ", "status": "green", "headline": "h", "medicines": [], "mood_and_sleep": "", "food": "",
                "concerns": [], "caregiver_actions": [], "message_to_parent_local": ""}, Usage(10, 0, 5, 0)


def test_prompts_come_from_the_care_plan(tmp_path):
    provider = ShortCall()
    record = run_call(LLM(provider, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl"), OTHER_FAMILY,
                      "other", "You feel fine.")
    agent, parent, report = (next(m for kind, m in provider.calls if kind == k and pick(m)) for k, pick in (
        ("tools", lambda m: True), ("json", lambda m: "role-playing" in m[0]["content"]),
        ("json", lambda m: "report" in m[0]["content"])))
    agent_text = agent[0]["content"] + agent[1]["content"]
    for needed in ("Kenji", "Yoshiko Sato", "Okaasan", "son", "at work in Tokyo", "Japanese", "kanji", "9:15 am",
                   "calling 119"):
        assert needed in agent_text, needed
    assert "Yoshiko Sato" in parent[0]["content"] and "Japanese" in parent[0]["content"]
    assert "Kenji" in report[0]["content"] and "Japanese" in report[0]["content"]
    without_plan = re.sub(r"Care plan \(JSON\): .*\n", "", agent[0]["content"])  # the plan itself may name anyone
    prompts = " ".join([without_plan, agent[1]["content"], parent[0]["content"], report[0]["content"], json.dumps(TOOLS)])
    for word in DEMO_FAMILY_WORDS:
        assert word not in prompts, word
    assert [who for who, _ in record.transcript] == ["Okaasan", "Saathi", "Okaasan", "Saathi"]


def test_the_call_asks_about_loneliness_and_flags_it_as_watch():
    text = AGENT_SYSTEM.format(care_plan_json="{}", **prompt_fields(OTHER_FAMILY))
    assert "talked with anyone or gone out" in text
    assert 'have not spoken with anyone for days, call flag_concern with severity "watch"' in text
    assert "social_contact" in REPORT_SYSTEM.format(**prompt_fields(OTHER_FAMILY))
    assert "social_contact" in CallReport.model_fields
