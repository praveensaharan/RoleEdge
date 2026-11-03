"""The daily check-in call, simulated in text.

Saathi (the agent) talks to a simulated parent (a second model playing a hidden scenario), uses
tools to record what it learns, and the call ends with a caregiver report. The real call is
voice; the conversation logic, tools and safety rules are the same, which is what this tests.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel

from ..llm import LLM, Message
from ..models import CallReport, CarePlan, ParentReply
from .escalation import escalation_status
from .prompts import AGENT_SYSTEM, CALL_CONNECTED, FIRST_WORDS, PARENT_SYSTEM, REPORT_SYSTEM, prompt_fields
from .tools import TOOLS, read_arguments, run_tool

MAX_TURNS = 16
MAX_TOOL_ROUNDS = 4  # tool calls the agent may make before it must speak


class CallRecord(BaseModel):
    scenario: str
    ended_cleanly: bool
    transcript: list[tuple[str, str]]  # (speaker, line)
    events: list[dict[str, Any]]  # tool calls: {"turn", "tool", "args", "error" if the arguments were invalid}
    report: dict[str, Any]  # CallReport fields; "status" set by code, "status_from_model" if it disagreed
    metrics: dict[str, Any]
    wall_s: float = 0.0


class SimulatedParent:
    def __init__(self, llm: LLM, care_plan: CarePlan, scenario_name: str, scenario: str) -> None:
        self.llm = llm
        self.task = f"checkin/{scenario_name}/parent"
        system = PARENT_SYSTEM.format(scenario=scenario, **prompt_fields(care_plan))
        self.messages: list[Message] = [{"role": "system", "content": system}]
        self.usage: list[dict[str, Any]] = []

    def reply(self, agent_said: str) -> str:
        self.messages.append({"role": "user", "content": agent_said or "..."})
        result = self.llm.complete_json(self.task, self.messages, ParentReply, "reply", effort="minimal")
        self.usage.append({"latency_s": result.latency_s, **result.usage.to_dict()})
        reply = result.data["reply"]
        self.messages.append({"role": "assistant", "content": reply})
        return reply


def run_call(llm: LLM, care_plan: CarePlan, scenario_name: str, scenario: str) -> CallRecord:
    started = time.time()
    task = f"checkin/{scenario_name}/agent"
    fields = prompt_fields(care_plan)
    system = AGENT_SYSTEM.format(care_plan_json=json.dumps(care_plan.model_dump(), ensure_ascii=False), **fields)
    agent: list[Message] = [{"role": "system", "content": system},
                            {"role": "user", "content": CALL_CONNECTED.format(**fields)}]
    parent = SimulatedParent(llm, care_plan, scenario_name, scenario)
    parent_name = care_plan.parent.call_name
    transcript = [(parent_name, FIRST_WORDS)]
    events: list[dict[str, Any]] = []
    agent_usage: list[dict[str, Any]] = []
    ended = False

    for turn in range(MAX_TURNS):
        for _ in range(MAX_TOOL_ROUNDS):
            result = llm.tool_turn(task, agent, TOOLS, effort="low")
            agent_usage.append({"latency_s": result.latency_s, **result.usage.to_dict()})
            agent.append(result.data.as_assistant_message())
            if not result.data.tool_calls:
                break
            for call in result.data.tool_calls:
                args, error = read_arguments(call.name, call.arguments)
                events.append({"turn": turn, "tool": call.name, "args": args} | ({"error": error} if error else {}))
                answer = {"status": "error", "error": error} if error else run_tool(call.name, args)
                agent.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(answer)})
                ended = ended or call.name == "end_call"

        said = (result.data.content or "").strip()
        if said:
            transcript.append(("Saathi", said))
        if ended:
            break
        reply = parent.reply(said)
        agent.append({"role": "user", "content": reply})
        transcript.append((parent_name, reply))

    report, report_usage = _write_report(llm, care_plan, scenario_name, transcript, events)
    return CallRecord(scenario=scenario_name, ended_cleanly=ended, transcript=transcript, events=events, report=report,
                      metrics={"agent_turns": agent_usage, "parent_turns": parent.usage, "report": report_usage},
                      wall_s=round(time.time() - started, 1))


def _write_report(llm: LLM, care_plan: CarePlan, scenario_name: str, transcript: list[tuple[str, str]],
                  events: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    conversation = "\n".join(f"{who}: {text}" for who, text in transcript)
    result = llm.complete_json(f"checkin/{scenario_name}/report", [
        {"role": "system", "content": REPORT_SYSTEM.format(**prompt_fields(care_plan))},
        {"role": "user", "content": f"TRANSCRIPT:\n{conversation}\n\nTOOL EVENTS:\n{json.dumps(events, ensure_ascii=False)}"},
    ], CallReport, "report", effort="low")
    report = dict(result.data)
    status = escalation_status(events)
    if status != report["status"]:
        report["status_from_model"] = report["status"]
    report["status"] = status
    return report, {"latency_s": result.latency_s, **result.usage.to_dict()}
