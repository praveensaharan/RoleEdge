import json

from roleedge.checkin import escalation_status, run_call
from roleedge.checkin.tools import read_arguments
from roleedge.demo import CARE_PLAN
from roleedge.llm import LLM, ToolCall, ToolTurn, Usage

from .conftest import FakeProvider


def flag(severity):
    return {"turn": 0, "tool": "flag_concern", "args": {"severity": severity, "reason": "r", "recommended_action": "a"}}


def record(taken):
    return {"turn": 0, "tool": "record_checkin", "args": {"medicines": [{"name": "Amlodipine", "taken": taken}]}}


def test_urgent_flag_is_red_even_if_everything_else_is_fine():
    assert escalation_status([record("yes"), flag("info"), flag("urgent")]) == "red"


def test_watch_or_missed_medicine_is_amber():
    assert escalation_status([flag("watch")]) == "amber"
    assert escalation_status([record("no")]) == "amber"


def test_otherwise_green():
    assert escalation_status([record("yes"), record("not_due"), flag("info")]) == "green"
    assert escalation_status([]) == "green"


def test_tool_values_are_read_whatever_their_case():
    assert escalation_status([flag("URGENT")]) == "red"
    assert escalation_status([flag(" Watch ")]) == "amber"
    assert escalation_status([record("No")]) == "amber"


def test_values_that_cannot_be_read_never_lower_the_status():
    assert escalation_status([flag("critical")]) == "red"
    assert escalation_status([{"turn": 0, "tool": "flag_concern", "args": {"reason": "fell"}}]) == "red"
    assert escalation_status([record("not taken")]) == "amber"  # an unreadable medicine status counts as missed
    assert escalation_status([{"turn": 0, "tool": "record_checkin", "args": {"medicines": None}}]) == "green"


def test_tool_arguments_are_checked_before_the_tool_runs():
    args, error = read_arguments("flag_concern", '{"severity": "URGENT", "reason": "r", "recommended_action": "a"}')
    assert error is None and args["severity"] == "URGENT"  # kept as sent; read case-insensitively
    args, error = read_arguments("flag_concern", '{"severity": "critical", "reason": "r", "recommended_action": "a"}')
    assert "severity" in error and args["severity"] == "critical"  # kept, so escalation still sees it
    assert read_arguments("flag_concern", "{not json")[1].startswith("arguments are not valid JSON")
    assert read_arguments("flag_concern", "[1]")[1] == "arguments must be a JSON object"
    assert read_arguments("order_pizza", "{}")[1] == "unknown tool 'order_pizza'"


class ScriptedCall(FakeProvider):
    """The agent flags a concern, then hangs up; the report model claims the call was amber."""

    def __init__(self, severity: str) -> None:
        super().__init__()
        concern = json.dumps({"severity": severity, "reason": "chest pain", "recommended_action": "call now"})
        self.turns = [ToolTurn(None, [ToolCall("c1", "flag_concern", concern)]),
                      ToolTurn("मैं Rohit को अभी बता रही हूँ।", []),
                      ToolTurn(None, [ToolCall("c2", "end_call", '{"closing_summary": "Rohit informed"}')]),
                      ToolTurn("ध्यान रखिए।", [])]

    def call_tools(self, messages, tools, *, effort="low", model=None):
        self.calls.append(("tools", messages))
        return self.turns[len([c for c in self.calls if c[0] == "tools"]) - 1], Usage(10, 0, 5, 0)

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append(("json", messages))
        if schema_name == "reply":
            return {"reply": "हाँ बेटा"}, Usage(10, 0, 5, 0)
        return {"status": "amber", "headline": "h", "medicines": [], "mood_and_sleep": "", "food": "", "concerns": [],
                "caregiver_actions": [], "message_to_parent_local": ""}, Usage(10, 0, 5, 0)


def tool_replies(provider):
    last_agent_messages = [m for kind, m in provider.calls if kind == "tools"][-1]
    return [json.loads(m["content"]) for m in last_agent_messages if m["role"] == "tool"]


def test_call_with_upper_case_urgent_flag_is_red(tmp_path):
    provider = ScriptedCall("URGENT")
    llm = LLM(provider, cache_dir=tmp_path / "cache", ledger_file=tmp_path / "usage.jsonl")
    record = run_call(llm, CARE_PLAN, "test", "scenario")
    assert record.report["status"] == "red" and record.report["status_from_model"] == "amber"
    assert tool_replies(provider)[0]["status"] == "sent"


def test_call_tells_the_agent_when_its_tool_arguments_are_invalid(tmp_path):
    provider = ScriptedCall("critical")
    llm = LLM(provider, cache_dir=tmp_path / "cache", ledger_file=tmp_path / "usage.jsonl")
    record = run_call(llm, CARE_PLAN, "test", "scenario")
    assert record.report["status"] == "red"  # an unreadable flag must not let the call come out green
    assert record.events[0]["error"].startswith("severity:")
    reply = tool_replies(provider)[0]
    assert reply["status"] == "error" and "severity" in reply["error"]
