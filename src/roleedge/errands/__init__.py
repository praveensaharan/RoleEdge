"""Errands the assistant runs for the parent: delivery times from verified mail, prices, orders within limits, and
the caregiver's week by the disclosure rules."""

from .agent import (
           answer_delivery,
           answer_notes,
           answer_schedule,
           local_date,
           now_for,
           pick_pages,
           price_message,
           route,
           say,
           visible_schedule,
           words,
)
from .demo_accounts import added_mails, schedule
from .mailbox import Mail, demo_mailbox
from .shop import STORES, Offer, money, offer, place_order, search

__all__ = ["STORES", "Mail", "Offer", "added_mails", "answer_delivery", "answer_notes", "answer_schedule", "demo_mailbox", "local_date",
           "money", "now_for", "pick_pages", "offer", "place_order", "price_message", "route", "say", "schedule", "search",
           "visible_schedule", "words"]
