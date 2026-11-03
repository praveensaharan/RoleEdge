"""The daily check-in call: the care plan the agent follows, its tool arguments, and the report."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator


def _lower(value: Any) -> Any:
    """Models sometimes send "URGENT" or " Watch"; read them as the lower-case choice."""
    return value.strip().lower() if isinstance(value, str) else value


CallStatus = Literal["green", "amber", "red"]
Severity = Annotated[Literal["info", "watch", "urgent"], BeforeValidator(_lower)]
Taken = Annotated[Literal["yes", "no", "unsure", "not_due"], BeforeValidator(_lower)]


# ---------------------------------------------------------------- care plan (input)
# Field order is kept stable because the plan is embedded in the agent prompt as JSON.


class ParentInfo(BaseModel):
    call_name: str
    full_name: str
    age: int
    language: str
    script: str
    lives: str


class CaregiverInfo(BaseModel):
    name: str
    relation: str
    status_now: str


class Medicine(BaseModel):
    name: str
    when: str


class CarePlan(BaseModel):
    parent: ParentInfo
    caregiver: CaregiverInfo
    conditions: list[str]
    medicines: list[Medicine]
    diet: str
    upcoming: list[str]
    food_ordering: str
    emergency: str
    emergency_number: str  # local ambulance number: 112 in India, 119 in Japan
    call_time: str  # local time of the daily call, e.g. "1:30 pm"


# ---------------------------------------------------------------- tool arguments (agent -> app)


class MedicineCheck(BaseModel):
    name: str
    taken: Taken


class CheckinRecord(BaseModel):
    mood: Annotated[Literal["good", "okay", "low", "unwell"], BeforeValidator(_lower)]
    sleep: Annotated[Literal["good", "okay", "poor", "unknown"], BeforeValidator(_lower)]
    medicines: list[MedicineCheck]
    meals: list[str]
    symptoms: list[str]
    notes: str


class Concern(BaseModel):
    severity: Severity
    reason: str
    recommended_action: str


class FoodItem(BaseModel):
    name: str
    qty: int


class FoodOrderRequest(BaseModel):
    restaurant: str
    items: list[FoodItem]
    reason: str


class EndCall(BaseModel):
    closing_summary: str


# ---------------------------------------------------------------- simulator + report


class ParentReply(BaseModel):
    reply: str


class MedicineSummary(BaseModel):
    name: str
    taken: str


class CallReport(BaseModel):
    status: CallStatus
    headline: str
    medicines: list[MedicineSummary]
    mood_and_sleep: str
    food: str
    social_contact: str
    concerns: list[str]
    caregiver_actions: list[str]
    message_to_parent_local: str
