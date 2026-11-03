"""Tools the check-in agent can call, and what the app answers.

In the product these hit real services (caregiver push/SMS, an approval card, the care record).
Here they are simulated, but the replies tell the agent the truth about state - e.g. a food
order is *pending approval*, never "placed" (rule S4).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from ..llm import tool_spec
from ..models import CheckinRecord, Concern, EndCall, FoodOrderRequest

ARGUMENTS: dict[str, type[BaseModel]] = {
    "record_checkin": CheckinRecord, "flag_concern": Concern, "request_food_order": FoodOrderRequest, "end_call": EndCall,
}

TOOLS = [
    tool_spec("record_checkin", "Save the structured results of today's check-in.", CheckinRecord),
    tool_spec("flag_concern", "Alert the caregiver. urgent = call them now; watch = today; info = in report.", Concern),
    tool_spec("request_food_order", "Prepare a food order from a saved restaurant; the caregiver must approve.", FoodOrderRequest),
    tool_spec("end_call", "Hang up after the closing line.", EndCall),
]

SIMULATED_RESULTS: dict[str, dict[str, Any]] = {
    "request_food_order": {"status": "pending_caregiver_approval", "note": "the caregiver gets an approve/decline card"},
    "flag_concern": {"status": "sent", "delivered_to": "caregiver (push + SMS)"},
}


def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Simulated tool execution: what the app would answer the agent."""
    return SIMULATED_RESULTS.get(name, {"status": "ok"})


def read_arguments(name: str, raw: str | None) -> tuple[dict[str, Any], str | None]:
    """Parse a tool call's arguments and check them against the tool's model. Returns (arguments, error).

    The arguments are returned as sent even when they are invalid, so a concern the agent tried to flag
    still reaches ``escalation_status``; the agent is told the error and can call again.
    """
    model = ARGUMENTS.get(name)
    if model is None:
        return {}, f"unknown tool {name!r}"
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        return {}, f"arguments are not valid JSON ({e.msg})"
    if not isinstance(args, dict):
        return {}, "arguments must be a JSON object"
    try:
        model.model_validate(args)
    except ValidationError as e:
        return args, "; ".join(f"{'.'.join(map(str, err['loc'])) or 'arguments'}: {err['msg']}" for err in e.errors())
    return args, None
