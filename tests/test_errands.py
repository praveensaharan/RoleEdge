"""Errands: she asks when a delivery comes, what something costs, or to order it; the caregiver is asked only once."""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from roleedge.app.server import create_app
from roleedge.errands import answer_delivery, demo_mailbox, price_message, search
from roleedge.families import CIRCLES
from roleedge.llm import LLM, Usage
from roleedge.models.errands import ErrandRequest
from roleedge.store import Store

from .conftest import FakeProvider

NOW = datetime(2026, 11, 2, 18, 12, tzinfo=ZoneInfo("Asia/Tokyo"))  # Uber Eats arrives 18:40-18:50 in the mailbox
DELIVERY = {"kind": "delivery", "merchant_hint": "Uber Eats", "item_en": "dinner", "quote": "ごはん、あと何分で来るの？"}
READING = {"summary_for_caregiver": "She asked when her dinner comes.", "signals": [], "needs": [],
           "question_for_caregiver": "When does the dinner come?", "reply_to_parent": "伝えますね。",
           "reply_to_parent_english": "I'll pass it on."}


def answer(spoken="お夕飯は18:40〜18:50に届く予定ですよ。", eta="18:40〜18:50", ids=("m_uber",)):
    return {"found": True, "mail_ids": list(ids), "eta_quote": eta, "spoken_text": spoken,
            "screen_title": "お夕飯のお届け", "english_gloss": "Your dinner should arrive 18:40-18:50."}


class ErrandModel(FakeProvider):
    def __init__(self, route=DELIVERY, reader=None):
        super().__init__()
        self.answers = {"errand_router": route, "delivery_reader": reader or answer(), "reply_reading": READING}

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append((schema_name, messages))
        return self.answers[schema_name], Usage(100, 0, 50, 0)


def llm(tmp_path, model):
    return LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")


@pytest.fixture(autouse=True)
def fixed_mailbox(monkeypatch):
    from roleedge.app import errand_routes

    monkeypatch.setattr(errand_routes, "demo_mailbox", lambda circle: demo_mailbox(circle, NOW))


def test_a_fake_courier_mail_never_reaches_the_reader_and_times_must_be_in_the_mail(tmp_path):
    model = ErrandModel()
    result = answer_delivery(llm(tmp_path, model), CIRCLES["sato"], ErrandRequest(**DELIVERY), demo_mailbox(CIRCLES["sato"], NOW))
    reader_input = str(model.calls[-1][1])
    assert "sagawa-redelivery" not in reader_input and "やよい軒" in reader_input  # blocked before any model saw it
    assert [m.sender for m, _ in result.blocked] == ["佐川急便 <info@sagawa-exp.co.jp>"]
    assert result.gate.passed and [m.id for m in result.used] == ["m_uber"]

    invented = ErrandModel(reader=answer(spoken="お夕飯は19時30分に届きますよ。", eta="19:30"))
    held = answer_delivery(llm(tmp_path / "b", invented), CIRCLES["sato"], ErrandRequest(**DELIVERY), demo_mailbox(CIRCLES["sato"], NOW))
    assert not held.gate.passed and "date_not_in_source" in held.gate.rules  # a time the mail never gave is held

    linked = ErrandModel(reader=answer(spoken="18:40〜18:50に届きます。詳しくは http://sagawa-redelivery.top"))
    assert not answer_delivery(llm(tmp_path / "c", linked), CIRCLES["sato"], ErrandRequest(**DELIVERY),
                               demo_mailbox(CIRCLES["sato"], NOW)).gate.passed  # the send gate still runs


def test_prices_are_written_by_code_from_the_catalog():
    cardigan = search("JPY", "a warm cardigan")
    message = price_message(CIRCLES["sato"], cardigan)
    assert cardigan.store == "Rakuten Ichiba" and "2,980円" in message.spoken_text and "楽天市場" in message.spoken_text
    assert message.english_gloss.startswith("At Rakuten Ichiba, Wool-blend cardigan, navy, size M is ¥2,980")  # in English
    assert "$8.49" in price_message(CIRCLES["chen"], search("USD", "rice")).spoken_text
    assert search("JPY", "a pony") is None


def wait_for(client, circle, predicate, limit=100):
    for _ in range(limit):
        items = client.get(f"/api/circles/{circle}").json()["items"]
        found = [i for i in items if predicate(i)]
        if found:
            return found[-1]
        time.sleep(0.05)
    raise AssertionError("never happened")


def test_she_asks_once_the_caregiver_allows_always_then_she_is_answered_straight_away(tmp_path):
    with TestClient(create_app(llm=llm(tmp_path, ErrandModel()), store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        client.post("/api/circles/sato/reply", json={"text": "ごはん、あと何分で来るの？"})
        card = wait_for(client, "sato", lambda i: i["kind"] == "approval")
        assert card["status"] == "draft" and card["payload"]["permission"] == "mail.deliveries"
        waiting = wait_for(client, "sato", lambda i: i["kind"] == "answer")
        assert "確認してから" in waiting["payload"]["message"]["spoken_text"]  # she hears "I'll check with Kenji"
        assert not any(i["payload"].get("ack") for i in client.get("/api/circles/sato").json()["items"])  # no generic ack

        client.post(f"/api/items/{card['id']}/allow", json={"decision": "always"})
        answered = wait_for(client, "sato", lambda i: i["payload"].get("errand", {}).get("kind") == "delivery")
        assert answered["status"] == "sent" and answered["payload"]["errand"]["eta"] == "18:40〜18:50"
        assert answered["payload"]["errand"]["blocked"][0]["reason"].startswith("claims to be from sagawa-exp.co.jp")
        assert client.get("/api/circles/sato").json()["circle"]["permissions"] == {"mail.deliveries": "always"}

        client.post("/api/circles/sato/reply", json={"text": "アマゾンの荷物はいつ？"})  # the second time: no card
        time.sleep(0.3)
        items = client.get("/api/circles/sato").json()["items"]
        assert sum(i["kind"] == "approval" for i in items) == 1
        assert sum(i["payload"].get("errand", {}).get("kind") == "delivery" for i in items) == 2

        stopped = client.post("/api/circles/sato/permissions/mail.deliveries/stop").json()
        assert stopped["permissions"] == {}


def test_price_then_order_within_the_limit_and_over_it_always_asks(tmp_path):
    model = ErrandModel(route={"kind": "price", "merchant_hint": "Rakuten", "item_en": "cardigan", "quote": "カーディガンはいくら？"})
    with TestClient(create_app(llm=llm(tmp_path, model), store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        client.post("/api/circles/sato/reply", json={"text": "楽天でカーディガンはいくら？"})
        price = wait_for(client, "sato", lambda i: i["payload"].get("errand", {}).get("kind") == "price")
        assert price["payload"]["errand"]["offer"]["price"] == 2980 and price["status"] == "sent"

        client.post(f"/api/items/{price['id']}/order")  # her "Order it": the first order asks the caregiver
        card = wait_for(client, "sato", lambda i: i["kind"] == "approval")
        assert card["payload"]["permission"] == "shop.orders" and not card["payload"]["over_limit"]
        assert client.post(f"/api/items/{price['id']}/order").status_code == 409  # one tap, one order
        client.post(f"/api/items/{card['id']}/allow", json={"decision": "always"})
        order = wait_for(client, "sato", lambda i: i["kind"] == "order")
        assert order["payload"]["order"]["simulated"] and order["payload"]["order"]["total"] == 2980
        told = wait_for(client, "sato", lambda i: i["payload"].get("errand", {}).get("kind") == "ordered")
        assert "注文しました" in told["payload"]["message"]["spoken_text"]
        assert "I've ordered Wool-blend cardigan" in told["payload"]["message"]["english_gloss"]

    circle = CIRCLES["sato"].model_copy(deep=True)
    circle.spending.per_order = 1000  # the cardigan now costs more than one order may
    store = Store(tmp_path / "db2.sqlite")
    with TestClient(create_app(llm=llm(tmp_path / "x", model), store=store, media=None)) as client:
        circle.permissions = {"shop.orders": "always"}
        store.save_circle(circle)
        client.post("/api/circles/sato/reply", json={"text": "カーディガンはいくら？"})
        price = wait_for(client, "sato", lambda i: i["payload"].get("errand", {}).get("kind") == "price")
        client.post(f"/api/items/{price['id']}/order")
        card = wait_for(client, "sato", lambda i: i["kind"] == "approval")
        assert card["payload"]["over_limit"]  # above the limit it asks, even with "always"
        assert client.post(f"/api/items/{card['id']}/allow", json={"decision": "always"}).json()["payload"]["decision"] == "once"
        assert store.circle("sato").permissions == {"shop.orders": "always"}  # "always" never stretched the limit


# ---------------------------------------------------------------- the demo apps you can add to, and her schedule questions

SCHEDULE = {"kind": "schedule", "merchant_hint": "", "item_en": "visit", "quote": "When are you coming to see me?"}


def test_what_you_add_to_a_demo_app_shows_in_it_and_reaches_the_delivery_reader(tmp_path):
    model = ErrandModel(route={"kind": "delivery", "merchant_hint": "Amazon", "item_en": "parcel", "quote": "When does my parcel come?"},
                        reader={"found": True, "mail_ids": ["x"], "eta_quote": "", "spoken_text": "Soon.", "screen_title": "Parcel",
                                "english_gloss": "Soon."})
    with TestClient(create_app(llm=llm(tmp_path, model), store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        mail = {"sender": "Amazon <shipment-tracking@amazon.com>", "title": "Your parcel arrives Thursday",
                "body": "Your hand cream arrives Thursday between 2 PM and 6 PM."}
        added = client.post("/api/circles/chen/apps/gmail/items", json=mail).json()
        assert added["id"].startswith("add_") and added["verified"]
        assert client.get("/api/connectors/gmail/items?circle=chen").json()[0]["title"] == "Your parcel arrives Thursday"
        soon = (datetime.now(ZoneInfo("America/Los_Angeles")) + timedelta(days=5)).strftime("%Y-%m-%dT18:30")
        event = client.post("/api/circles/chen/apps/googlecalendar/items",
                            json={"title": "Dinner with Mom", "at": soon, "minutes": 90, "kind": "family_events"}).json()
        assert event["at"].startswith(soon) and event["at"][len(soon):].startswith("-0")  # in her time zone (Los Angeles)
        assert client.post("/api/circles/chen/apps/googlecalendar/items", json={"title": "Old", "at": "2020-01-01T10:00"}).status_code == 400
        assert client.post("/api/circles/chen/apps/zoom/items", json={"title": ""}).status_code == 400
        assert client.post("/api/circles/chen/apps/slack/items", json={"body": ""}).status_code == 400
        assert client.post("/api/circles/chen/apps/photos/items", json={"body": "x"}).status_code == 422

        client.post("/api/circles/chen/reply", json={"text": "When does my parcel come?"})
        card = wait_for(client, "chen", lambda i: i["kind"] == "approval")
        client.post(f"/api/items/{card['id']}/allow", json={"decision": "once"})
        wait_for(client, "chen", lambda i: i["payload"].get("errand", {}).get("kind") == "delivery")
        reader_input = str(next(m for name, m in model.calls if name == "delivery_reader"))
        assert "hand cream arrives Thursday between 2 PM and 6 PM" in reader_input  # the mail you added was read

        assert client.delete(f"/api/circles/chen/apps/gmail/items/{added['id']}").json() == {"removed": added["id"]}
        assert all(i["id"] != added["id"] for i in client.get("/api/connectors/gmail/items?circle=chen").json())


def test_her_schedule_question_sees_work_only_as_busy_and_times_must_be_in_the_calendar(tmp_path):
    from roleedge.errands import answer_schedule, visible_schedule
    from roleedge.errands.demo_accounts import Entry

    zone = ZoneInfo("America/Los_Angeles")
    now = datetime(2026, 11, 3, 9, 0, tzinfo=zone)
    entries = [Entry("c_focus", "1:1 with Priya about the layoffs", datetime(2026, 11, 3, 15, 0, tzinfo=zone), 60, "work", "Room 4B"),
               Entry("c_visit", "Visit Mom", datetime(2026, 11, 14, 11, 0, tzinfo=zone), 180, "family_events", "Mom's home"),
               Entry("c_doc", "My own doctor", datetime(2026, 11, 5, 9, 0, tzinfo=zone), 30, "secrets")]
    circle = CIRCLES["chen"]
    lines = [line for _, line in visible_schedule(circle, entries)]
    assert lines == ["[c_focus] Tuesday 3 November, 3:00 PM to 4:00 PM: busy",
                     "[c_visit] Saturday 14 November, 11:00 AM to 2:00 PM: Visit Mom (Mom's home)"]  # "never" is left out

    reply = {"found": True, "item_ids": ["c_visit"], "when_quote": "Saturday 14 November, 11:00 AM",
             "spoken_text": "Maya is coming on Saturday 14 November at 11:00 AM.", "screen_title": "Maya's visit",
             "english_gloss": "Maya is coming on Saturday 14 November at 11:00 AM."}
    model = ErrandModel(route=SCHEDULE)
    model.answers["schedule_reader"] = reply
    result = answer_schedule(llm(tmp_path, model), circle, ErrandRequest(**SCHEDULE), entries, now)
    seen = str(model.calls[-1][1])
    assert "layoffs" not in seen and "Room 4B" not in seen and "doctor" not in seen  # never reached the model
    assert result.gate.passed and [e.id for e in result.used] == ["c_visit"]

    model.answers["schedule_reader"] = {**reply, "spoken_text": "Maya is coming on Sunday 15 November at 10:00 AM."}
    held = answer_schedule(llm(tmp_path / "b", model), circle, ErrandRequest(**SCHEDULE), entries, now)
    assert not held.gate.passed and "date_not_in_source" in held.gate.rules


def test_the_calendar_app_lists_the_week_with_work_marked(tmp_path):
    from roleedge.errands.demo_accounts import app_connectors

    calendar = app_connectors()["googlecalendar"]
    items = calendar.recent(circle=CIRCLES["chen"])
    assert any(i.badge == "Work" for i in items) and any("science fair" in i.title for i in items)
    title, text = calendar.read(items[0].id, CIRCLES["chen"])
    assert text.startswith("Calendar event: ") and title == items[0].title
