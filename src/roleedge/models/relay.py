"""The family relay: a question from a grandchild to their grandparent, or the answer back, passed on by the
assistant. Field order is the order the model fills it (rule A4)."""

from __future__ import annotations

from pydantic import BaseModel


class RelayMessage(BaseModel):
    """The relay writer's version of what one family member said, for the other one."""

    spoken_text: str  # for the listener, in their language (the title, "From Hana", is written by code)
    english_gloss: str  # what was said, in plain English, for the caregiver
    picture_en: str  # for a child: a calm picture-book scene of what was described; "" for a grandparent
    follow_up: str  # for a child: one short question they could ask next, in their language; "" for a grandparent
