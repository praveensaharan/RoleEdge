"""Errands: what she asks the assistant to find out or do (a delivery time, a price, an order), and the answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ErrandKind = Literal["none", "delivery", "price", "order", "schedule", "notes"]


class ErrandRequest(BaseModel):
    """What she asked the assistant to do, read from her own words (the errand router's contract)."""

    kind: ErrandKind  # none: not an errand (a feeling, news, a question only her family can answer)
    merchant_hint: str  # e.g. "Uber Eats", "Amazon", "Rakuten", "Yamato"; "" if she named none
    item_en: str  # what it is about, in plain English: "dinner", "rice", "toilet paper"; "" if general
    quote: str  # her own words that asked it


class DeliveryAnswer(BaseModel):
    """The mail reader's answer from verified delivery mails only (the delivery reader's contract)."""

    found: bool  # false if no verified mail answers her question
    mail_ids: list[str]  # the mails the answer relies on
    eta_quote: str  # the arrival time or date exactly as the mail writes it; "" if none
    spoken_text: str  # the answer in her language, warm and short, spoken by the assistant
    screen_title: str  # 2-6 words in her language
    english_gloss: str  # the same answer in plain English, for the caregiver and subtitles


# ---------------------------------------------------------------- the demo apps you can add to

AddedApp = Literal["gmail", "slack", "zoom", "googlecalendar"]
EventKind = Literal["family_events", "travel", "work", "schedule", "health"]  # its disclosure category


class AddedItem(BaseModel):
    """Something the caregiver added to a demo app (a mail, a Slack message, a meeting, a calendar event), stored per
    circle so the agents pick it up as if it had arrived in the real app."""

    id: str
    app: AddedApp
    at: str  # ISO local time: when a mail or message arrived, when a meeting or event starts
    title: str = ""  # a mail's subject, a meeting's topic, an event's title
    sender: str = ""  # a mail's From ("Amazon <shipment-tracking@amazon.com>"), a Slack author
    where: str = ""  # a Slack channel, an event's place
    body: str = ""  # a mail's body, a Slack message, an event's notes
    minutes: int = 0  # how long a meeting or event lasts
    kind: EventKind = "family_events"  # what an event is, which decides what she may hear about it
    verified: bool = True  # a mail passes the sender check; False stands for a spoofed one


class ScheduleAnswer(BaseModel):
    """The schedule reader's answer from the calendar items she may know about (the schedule reader's contract)."""

    found: bool  # false if nothing she may know answers her question
    item_ids: list[str]  # the calendar items the answer relies on
    when_quote: str  # the day and time exactly as the item gives it; "" if none
    spoken_text: str  # the answer in her language, warm and short, spoken by the assistant
    screen_title: str  # 2-6 words in her language
    english_gloss: str  # the same answer in plain English, for the caregiver and subtitles


class NotesAnswer(BaseModel):
    """The notes reader's answer from the family's own notes (Notion, or the demo notes) (the notes reader's contract)."""

    found: bool  # false if the notes don't answer her question
    page_title: str  # the page the answer comes from; "" if none
    quote: str  # the line or lines the answer comes from, copied word for word from that page; "" if none
    spoken_text: str  # the answer in her language, warm and short, spoken by the assistant
    screen_title: str  # 2-6 words in her language
    english_gloss: str  # the same answer in plain English, for the caregiver and subtitles


class PagePick(BaseModel):
    """The notes picker: which of the family's pages could answer her question (by title)."""

    pages: list[int]  # the numbers of the pages most likely to hold the answer, best first (at most 4); [] if none
