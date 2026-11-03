"""People in a family circle, as the AI sees them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Recipient(BaseModel):
    """Who a chat is for, and how to write for them."""

    call_name: str  # what the family calls them, e.g. "Mummy"
    full_name: str
    role: Literal["parent", "child"]
    age: int
    language: str  # e.g. "Hindi", "English"
    script: str  # e.g. "Devanagari", "Latin"
    timezone: str  # IANA name, e.g. "Asia/Kolkata"; dates in prompts and calendars use it
    reading: str  # plain description of reading level and preferences, used in prompts
    sender: str  # who usually shares into this chat, e.g. "Rohit (her son)"

    @property
    def sender_short(self) -> str:
        """'Rohit (her son)' -> 'Rohit'."""
        return self.sender.split(" (")[0]

    def known_people(self) -> str:
        """The only names the AI may use when writing for this recipient."""
        return f"{self.call_name} (the recipient, {self.full_name}), {self.sender} (the sender), Saathi (the helper)"
