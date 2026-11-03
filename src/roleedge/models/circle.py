"""A family circle: the people in it, how they are linked, and the rules the agents follow for them.

The circle is closed (PIVOT.md T1): members are linked once, with both sides approving, and nobody outside it can
send to anyone in it. Playbooks (T2) are the routines the agent may run without asking; anything else needs the
caregiver's confirmation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["caregiver", "parent", "child"]
Language = Literal["en", "ja"]
VoiceChoice = Literal["mine", "assistant"]  # whose voice a message to the parent is spoken in
Disclosure = Literal["share", "ask", "never"]  # what the agent may tell the parent from the caregiver's sources

LANGUAGE_NAMES: dict[str, str] = {"en": "English", "ja": "Japanese"}


class Member(BaseModel):
    id: str
    name: str  # full name (synthetic in the demo, rule S7)
    call_name: str  # what the family calls them, in the caregiver's language, e.g. "Mom", "Okaasan", "Kenji"
    call_name_local: str = ""  # the same in the member's own language, e.g. "お母さん"; empty = same as call_name
    role: Role
    language: Language
    timezone: str  # IANA name
    age: int | None = None
    relation: str = ""  # relation to the caregiver, e.g. "his mother"
    emergency_number: str = ""  # shown on the parent's screen on an urgent signal (119 in Japan)
    calls_caregiver: str = ""  # what this member calls the caregiver, e.g. "パパ"; empty = the caregiver's local name
    calls_grandparent: str = ""  # a child's word for the parent, e.g. "おばあちゃん"; empty = the parent's call name

    @property
    def local_name(self) -> str:
        return self.call_name_local or self.call_name

    @property
    def language_name(self) -> str:
        return LANGUAGE_NAMES[self.language]


class Playbook(BaseModel):
    """A routine the caregiver set up once; the agent may run it without asking each time."""

    id: Literal["daily_checkin", "weekly_summary", "answer_schedule", "watch_staples", "tonight_food"]
    label: str
    enabled: bool = True
    detail: str = ""  # e.g. "10:00 every day"


class DisclosureRule(BaseModel):
    category: Literal["schedule", "whereabouts", "travel", "family_events", "deliveries",
                      "work", "health", "money", "other_people", "secrets"]
    label: str
    policy: Disclosure


class SpendingLimit(BaseModel):
    currency: Literal["JPY", "USD"] = "JPY"
    per_order: int = 3000
    per_month: int = 20000


class Circle(BaseModel):
    id: str
    label: str  # e.g. "Kenji and Okaasan"
    caregiver: Member
    parent: Member
    children: list[Member] = Field(default_factory=list)  # the caregiver's children: Studio packs only, through them
    paired: bool = False  # both sides approved the link (T1)
    voice: VoiceChoice = "mine"  # default voice for messages to the parent
    send_immediately: bool = False  # off = every message waits for the caregiver's approval (S6)
    avatar_mode: Literal["3d", "2d"] = "3d"  # how the caregiver appears on the parent's phone
    playbooks: list[Playbook] = Field(default_factory=list)
    disclosure: list[DisclosureRule] = Field(default_factory=list)
    spending: SpendingLimit = Field(default_factory=SpendingLimit)
    # What the assistant may do for the parent without asking first, e.g. {"mail.deliveries": "always"}. Anything
    # missing is asked the first time; the caregiver can stop any of them.
    permissions: dict[str, Literal["always"]] = Field(default_factory=dict)

    def member(self, member_id: str) -> Member | None:
        return next((m for m in (self.caregiver, self.parent, *self.children) if m.id == member_id), None)

    def recipient(self, member_id: str = "") -> Member | None:
        """Who a Studio pack is for: the parent (the default) or one of the children; None if not in this circle."""
        if not member_id or member_id == self.parent.id:
            return self.parent
        return next((c for c in self.children if c.id == member_id), None)

    def policy_for(self, category: str) -> Disclosure:
        """Unknown categories are never shared without asking."""
        return next((r.policy for r in self.disclosure if r.category == category), "ask")
