"""Errand routes: she asks, the assistant finds out (or orders), asking the caregiver only the first time.

* Her reply is routed (``errands.route``). A delivery question needs the caregiver's mail; an order spends money.
  The first time, the caregiver gets an approval card (Always allow / Allow once / Not now) and she hears "I'll
  check with him". Once always allowed, she is answered straight away, even when the caregiver is busy.
* Price checks need no permission (the "watch staples" playbook): the price is written by code from the catalog.
* Orders stay within the circle's spending limit; anything above it asks every time, and "always" never covers it.
* The caregiver can stop any permission (``/permissions/{key}/stop``).

Mail is the demo mailbox and checkout is simulated until Gmail sign-in and a store API are connected; both are
labelled so on screen.

* Her schedule questions ("when are you visiting?") are answered from the demo Google Calendar and Zoom by the
  disclosure rules (``errands.answer_schedule``), with the same first-time approval.
* The caregiver can **add** a mail, a Slack message, a Zoom meeting or a calendar event to the demo apps
  (``/api/circles/{id}/apps/{app}/items``); the agents pick it up like anything else in those apps.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..errands import (
    STORES,
    Offer,
    added_mails,
    answer_delivery,
    answer_notes,
    answer_schedule,
    demo_mailbox,
    local_date,
    money,
    now_for,
    offer,
    pick_pages,
    place_order,
    price_message,
    route,
    say,
    schedule,
    search,
)
from ..errands.demo_accounts import Entry
from ..errands.mailbox import Mail
from ..llm import LLM
from ..models import Circle, GateResult, ParentMessage, ThreadItem, TraceStep
from ..models.errands import AddedApp, AddedItem, ErrandRequest, EventKind
from ..store import Store, new_id, now_iso
from .guards import Budget

PERMISSIONS = {
    "mail.deliveries": ("Read delivery emails in your Gmail",
                        "Read the delivery emails in your inbox (Uber Eats, Instacart, Amazon and couriers) to tell "
                        "{parent} when things arrive: only what is coming and when, never links, prices or order "
                        "numbers. Fake courier mails are blocked by the sender check."),
    "shop.orders": ("Order what she asks for",
                    "Order what {parent} asks for at {store}, up to {per_order} per order and {per_month} a month. "
                    "Anything above that still asks you."),
    "notion.notes": ("Answer her from your notes",
                     "Tell {parent} what your notes say when she asks (a recipe, a routine, what to bring), from your "
                     "Notion or the demo notes. Never passwords or codes, and no medical advice."),
    "calendar.schedule": ("Answer her from your calendar",
                          "Tell {parent} when you're free, away or visiting, and when family events are, from your "
                          "Google Calendar and Zoom: by your sharing rules, so work is only ever \"busy until 4\"."),
}
MAX_ADDED = 40  # per circle
MAX_NOTES_READ = 8  # pages read in full for one question


class NewAppItem(BaseModel):
    """A mail, Slack message, Zoom meeting or calendar event the caregiver adds to a demo app."""

    title: str = Field("", max_length=140)
    sender: str = Field("", max_length=120)
    where: str = Field("", max_length=120)
    body: str = Field("", max_length=2000)
    at: str = Field("", max_length=32)  # local "2026-11-14T11:00" for a meeting or event; "" = now
    minutes: int = Field(0, ge=0, le=60 * 24 * 7)
    kind: EventKind = "family_events"
    verified: bool = True


class Decision(BaseModel):
    decision: Literal["always", "once", "deny"]


class ErrandRuns:
    def __init__(self, *, llm: LLM, store: Store, publish: Callable[[ThreadItem], Awaitable[ThreadItem]],
                 budget: Budget) -> None:
        self.llm, self.store, self.publish, self.budget = llm, store, publish, budget
        self.apps: Any = None  # connect_routes.ConnectedApps, set by the server: a family's own accounts, else demo

    def added(self, circle: Circle, app: str) -> list[AddedItem]:
        return self.store.app_items(circle.id, app)

    def own(self, app: str, circle: Circle) -> Any:
        return self.apps.own(app, circle) if self.apps is not None else None

    def mailbox(self, circle: Circle) -> tuple[list[Mail], str]:
        """Her deliveries come from the caregiver's own Gmail when it is connected, else the demo inbox."""
        gmail = self.own("gmail", circle)
        if gmail is not None:
            rows = gmail.messages(query="newer_than:10d -in:spam -in:trash")
            return [Mail(m["id"], m["sender"], m["auth"], m["subject"], m["body"], m["received"]) for m in rows], "your Gmail"
        return demo_mailbox(circle) + added_mails(self.added(circle, "gmail")), "demo mailbox"

    def week_entries(self, circle: Circle) -> tuple[list[Entry], str]:
        """The caregiver's week from their own Google Calendar when it is connected, else the demo calendar and Zoom."""
        calendar = self.own("googlecalendar", circle)
        if calendar is not None:
            zone = ZoneInfo(circle.parent.timezone)
            return [Entry(e["id"], e["title"], e["start"].astimezone(zone), e["minutes"], e["kind"], e["where"], "Google Calendar")
                    for e in calendar.events()], "your Google Calendar"
        return schedule(circle, self.added), "demo calendar"

    def notes(self, circle: Circle, question: str = "") -> tuple[list[tuple[str, str]], str, list[TraceStep]]:
        """The family's notes: their own Notion when connected, else the demo notes (title, text per page). With more
        than a few pages, a picker chooses up to four by title and only those are read in full (the Reel Lab's Notion
        test: reading only the newest pages missed older ones; picking first answered 10 of 10)."""
        notion = self.apps.get("notion", circle) if self.apps is not None else None
        if notion is None or not notion.status().connected:
            return [], "no notes", []
        items = notion.recent(limit=100, circle=circle)
        trace: list[TraceStep] = []
        if len(items) > MAX_NOTES_READ and question:
            chosen, step = pick_pages(self.llm, circle, question, [i.title for i in items])
            items, trace = [items[k] for k in chosen], [step]
        pages = []
        for item in items[:MAX_NOTES_READ]:
            try:
                pages.append(notion.read(item.id, circle))
            except Exception:
                continue
        own = self.own("notion", circle) is not None or not notion.status().demo
        return pages, "your Notion" if own else "demo notes", trace

    # ---------------------------------------------------------------- helpers

    def limits(self, circle: Circle) -> tuple[int, int, int]:
        """(per order, per month, spent this month) in the store's smallest unit (yen, or cents)."""
        unit = 1 if circle.spending.currency == "JPY" else 100
        month = now_for(circle).strftime("%Y-%m")
        spent = sum(i.payload.get("order", {}).get("total", 0) for i in self.store.items(circle.id)
                    if i.kind == "order" and i.at[:7] == month)
        return circle.spending.per_order * unit, circle.spending.per_month * unit, spent

    def permission_text(self, circle: Circle, key: str) -> tuple[str, str]:
        title, detail = PERMISSIONS[key]
        unit = 1 if circle.spending.currency == "JPY" else 100
        return title, detail.format(parent=circle.parent.call_name, store=STORES[circle.spending.currency],
                                    per_order=money(circle.spending.per_order * unit, circle.spending.currency),
                                    per_month=money(circle.spending.per_month * unit, circle.spending.currency))

    async def tell_her(self, circle: Circle, message: ParentMessage, errand: dict[str, Any], *, trace: list[TraceStep],
                       gate: GateResult | None = None, status: str = "sent") -> ThreadItem:
        return await self.publish(ThreadItem(
            id=new_id("it"), circle_id=circle.id, at=now_iso(), kind="answer", to="parent", speaker="assistant",
            status=status, voice="assistant", gate=gate, trace=trace,  # type: ignore[arg-type]
            payload={"message": message.model_dump(), "language": circle.parent.language, "errand": errand}))

    # ---------------------------------------------------------------- her request

    async def route(self, circle: Circle, text: str, context: list[str]) -> tuple[ErrandRequest | None, TraceStep | None]:
        try:
            return await run_in_threadpool(route, self.llm, circle, text, context)
        except Exception:
            return None, None  # the reply still reaches the caregiver as a summary

    async def handle(self, circle: Circle, request: ErrandRequest, step: TraceStep | None) -> None:
        trace = [step] if step else []
        if request.kind == "delivery":
            if circle.permissions.get("mail.deliveries") == "always":
                await self.deliver(circle, request, "always", trace)
            else:
                await self.ask(circle, "mail.deliveries", request, trace)
        elif request.kind == "notes":
            if circle.permissions.get("notion.notes") == "always":
                await self.look_up(circle, request, "always", trace)
            else:
                await self.ask(circle, "notion.notes", request, trace)
        elif request.kind == "schedule":
            if circle.permissions.get("calendar.schedule") == "always":
                await self.week(circle, request, "always", trace)
            else:
                await self.ask(circle, "calendar.schedule", request, trace)
        elif request.kind in ("price", "order"):
            found = search(circle.spending.currency, request.item_en)
            if found is None:
                store = STORES[circle.spending.currency]
                searched = TraceStep(step=f"Searched {store} (simulated catalog): nothing matched", engine="code")
                await self.tell_her(circle, say(circle, "not_found", store=store),
                                    {"kind": request.kind, "question": request.quote, "simulated": True},
                                    trace=[*trace, searched])
            elif request.kind == "price":
                await self.tell_her(circle, price_message(circle, found),
                                    {"kind": "price", "question": request.quote, "offer": found.to_dict(), "simulated": True},
                                    trace=[*trace, TraceStep(step=f"Found the price at {found.store} (simulated catalog); "
                                                                  "the message is written by code", engine="code")])
            else:
                await self.order(circle, found, request.quote, trace)

    async def ask(self, circle: Circle, key: str, request: ErrandRequest, trace: list[TraceStep],
                  chosen: Offer | None = None, over_limit: bool = False) -> None:
        """The first time (or above the limit): a card for the caregiver, and a word to her meanwhile."""
        holding = say(circle, "order_wait" if key == "shop.orders" else "asking")
        await self.tell_her(circle, holding, {"kind": "waiting", "question": request.quote}, trace=trace)
        title, detail = self.permission_text(circle, key)
        await self.publish(ThreadItem(
            id=new_id("it"), circle_id=circle.id, at=now_iso(), kind="approval", to="caregiver", speaker="assistant",
            status="draft", trace=[TraceStep(step=f"Asked you first: {title.lower()}", engine="code")],
            payload={"permission": key, "title": title, "detail": detail, "request": request.model_dump(),
                     "offer": chosen.to_dict() if chosen else None, "over_limit": over_limit}))

    async def deliver(self, circle: Circle, request: ErrandRequest, permission: str, trace: list[TraceStep]) -> ThreadItem:
        mailbox, source = await run_in_threadpool(self.mailbox, circle)
        result = await run_in_threadpool(answer_delivery, self.llm, circle, request, mailbox)
        answer = result.answer
        message = ParentMessage(spoken_text=answer.spoken_text, screen_title=answer.screen_title, steps=[],
                                quick_replies=[], english_gloss=answer.english_gloss)
        errand = {"kind": "delivery", "question": request.quote, "found": answer.found, "eta": answer.eta_quote,
                  "source": source, "permission": permission,
                  "used": [{"sender": m.sender, "subject": m.subject} for m in result.used],
                  "blocked": [{"sender": m.sender, "reason": reason} for m, reason in result.blocked]}
        return await self.tell_her(circle, message, errand, trace=[*trace, *result.trace], gate=result.gate,
                                   status="sent" if result.gate.passed else "held")

    async def week(self, circle: Circle, request: ErrandRequest, permission: str, trace: list[TraceStep]) -> ThreadItem:
        entries, source = await run_in_threadpool(self.week_entries, circle)
        result = await run_in_threadpool(answer_schedule, self.llm, circle, request, entries)
        answer = result.answer
        message = ParentMessage(spoken_text=answer.spoken_text, screen_title=answer.screen_title, steps=[],
                                quick_replies=[], english_gloss=answer.english_gloss)
        errand = {"kind": "schedule", "question": request.quote, "found": answer.found, "when": answer.when_quote,
                  "source": source, "permission": permission,
                  "used": [{"title": e.title if circle.policy_for(e.kind) == "share" else "Busy", "source": e.source}
                           for e in result.used]}
        return await self.tell_her(circle, message, errand, trace=[*trace, *result.trace], gate=result.gate,
                                   status="sent" if result.gate.passed else "held")

    async def look_up(self, circle: Circle, request: ErrandRequest, permission: str, trace: list[TraceStep]) -> ThreadItem:
        pages, source, picked = await run_in_threadpool(self.notes, circle, request.quote)
        result = await run_in_threadpool(answer_notes, self.llm, circle, request, pages, source)
        result.trace = [*picked, *result.trace]
        answer = result.answer
        message = ParentMessage(spoken_text=answer.spoken_text, screen_title=answer.screen_title, steps=[],
                                quick_replies=[], english_gloss=answer.english_gloss)
        errand = {"kind": "notes", "question": request.quote, "found": answer.found, "page": result.page,
                  "source": source, "permission": permission}
        return await self.tell_her(circle, message, errand, trace=[*trace, *result.trace], gate=result.gate,
                                   status="sent" if result.gate.passed else "held")

    async def order(self, circle: Circle, chosen: Offer, quote: str, trace: list[TraceStep], approved: str = "") -> None:
        per_order, per_month, spent = self.limits(circle)
        over = chosen.price > per_order or spent + chosen.price > per_month
        allowed = approved == "once" or (not over and (approved == "always" or circle.permissions.get("shop.orders") == "always"))
        if not allowed:
            request = ErrandRequest(kind="order", merchant_hint=chosen.store, item_en=chosen.name_en, quote=quote)
            await self.ask(circle, "shop.orders", request, trace, chosen=chosen, over_limit=over)
            return
        placed = place_order(chosen, now_for(circle))
        await self.publish(ThreadItem(
            id=new_id("it"), circle_id=circle.id, at=now_iso(), kind="order", to="caregiver", speaker="assistant",
            status="done", trace=[*trace, TraceStep(step=f"Ordered at {chosen.store} (simulated checkout), within your limit", engine="code")],
            payload={"offer": chosen.to_dict(), "order": placed, "spent_month": spent + chosen.price,
                     "per_month": per_month, "question": quote}))
        ordered = say(circle, "ordered", {"name": chosen.name_en, "date": local_date(circle, placed["arrives"], "en")},
                      name=chosen.name if circle.parent.language == "ja" else chosen.name_en,
                      date=local_date(circle, placed["arrives"]))
        await self.tell_her(circle, ordered,
                            {"kind": "ordered", "offer": chosen.to_dict(), "order": placed, "simulated": True},
                            trace=[TraceStep(step="Told her the order is placed (written by code)", engine="code")])


def add_errand_routes(app: FastAPI, *, llm: LLM, store: Store, publish: Callable[[ThreadItem], Awaitable[ThreadItem]],
                      budget: Budget, circle_or_404: Callable[[str], Circle],
                      item_or_404: Callable[[str], ThreadItem]) -> ErrandRuns:
    runs = ErrandRuns(llm=llm, store=store, publish=publish, budget=budget)

    @app.post("/api/items/{item_id}/allow")
    async def allow(item_id: str, req: Decision) -> dict:
        """The caregiver's answer to an approval card."""
        item = item_or_404(item_id)
        if item.kind != "approval" or item.status != "draft":
            raise HTTPException(409, "This was already answered.")
        circle = circle_or_404(item.circle_id)
        key, request = item.payload["permission"], ErrandRequest.model_validate(item.payload["request"])
        over = item.payload.get("over_limit", False)
        decision = "once" if req.decision == "always" and over else req.decision  # "always" never covers the limit
        item.status, item.payload["decision"] = ("done" if decision == "deny" else "answered"), decision
        await publish(item)
        if decision == "always":
            circle.permissions[key] = "always"
            store.save_circle(circle)
        if decision == "deny":
            await runs.tell_her(circle, say(circle, "declined" if key == "shop.orders" else "denied"),
                                {"kind": "declined", "question": request.quote}, trace=[TraceStep(step="You said not now", engine="you")])
        elif key == "mail.deliveries":
            budget.take()
            await runs.deliver(circle, request, decision, [TraceStep(step=f"You allowed it ({decision})", engine="you")])
        elif key == "notion.notes":
            budget.take()
            await runs.look_up(circle, request, decision, [TraceStep(step=f"You allowed it ({decision})", engine="you")])
        elif key == "calendar.schedule":
            budget.take()
            await runs.week(circle, request, decision, [TraceStep(step=f"You allowed it ({decision})", engine="you")])
        else:
            chosen = offer((item.payload.get("offer") or {}).get("id", ""))
            if chosen is None:
                raise HTTPException(409, "That item is no longer in the catalog.")
            await runs.order(circle, chosen, request.quote, [TraceStep(step=f"You allowed it ({decision})", engine="you")],
                             approved=decision)
        return item.model_dump()

    @app.post("/api/items/{item_id}/order")
    async def order_from_price(item_id: str) -> dict:
        """Her "Order it" on a price answer."""
        item = item_or_404(item_id)
        errand = item.payload.get("errand") or {}
        chosen = offer((errand.get("offer") or {}).get("id", "")) if errand.get("kind") == "price" else None
        if chosen is None or item.payload.get("order_requested"):
            raise HTTPException(409, "Nothing to order here.")
        item.payload["order_requested"] = True
        await publish(item)
        circle = circle_or_404(item.circle_id)
        await runs.order(circle, chosen, errand.get("question", ""), [TraceStep(step="She tapped Order it", engine="her phone")])
        return item.model_dump()

    @app.post("/api/circles/{circle_id}/permissions/{key}/stop")
    async def stop_permission(circle_id: str, key: str) -> dict:
        circle = circle_or_404(circle_id)
        circle.permissions.pop(key, None)
        store.save_circle(circle)
        return circle.model_dump()

    @app.get("/api/permissions")
    def permission_labels() -> dict[str, str]:
        return {key: title for key, (title, _) in PERMISSIONS.items()}

    # ---------------------------------------------------------------- adding to the demo apps

    @app.get("/api/circles/{circle_id}/apps")
    def added_items(circle_id: str) -> list[dict]:
        circle_or_404(circle_id)
        return [i.model_dump() for i in store.app_items(circle_id)]

    @app.post("/api/circles/{circle_id}/apps/{app_id}/items")
    def add_item(circle_id: str, app_id: AddedApp, req: NewAppItem) -> dict:
        circle = circle_or_404(circle_id)
        if len(store.app_items(circle_id)) >= MAX_ADDED:
            raise HTTPException(409, f"Up to {MAX_ADDED} added items; remove one first.")
        zone = ZoneInfo(circle.parent.timezone)
        now = datetime.now(zone)
        try:
            at = datetime.fromisoformat(req.at).replace(tzinfo=zone) if req.at else now
        except ValueError:
            raise HTTPException(400, "The date and time should look like 2026-11-14T11:00.") from None
        timed = app_id in ("zoom", "googlecalendar")
        if timed and not req.title.strip():
            raise HTTPException(400, "Give it a title.")
        if not timed and not req.body.strip():
            raise HTTPException(400, "Write the message.")
        if timed and not now - timedelta(days=1) < at < now + timedelta(days=60):
            raise HTTPException(400, "Pick a time in the next two months.")
        item = AddedItem(id=new_id("add"), app=app_id, at=at.isoformat(timespec="minutes"), title=req.title.strip(),
                         sender=req.sender.strip(), where=req.where.strip(), body=req.body.strip(),
                         minutes=req.minutes or (60 if timed else 0), kind=req.kind if timed else "family_events",
                         verified=req.verified)
        store.add_app_item(circle_id, item)
        return item.model_dump()

    @app.delete("/api/circles/{circle_id}/apps/{app_id}/items/{item_id}")
    def remove_item(circle_id: str, app_id: str, item_id: str) -> dict:
        circle_or_404(circle_id)
        if not store.remove_app_item(circle_id, item_id):
            raise HTTPException(404, "No such item.")
        return {"removed": item_id}

    return runs
