"""A family's own Gmail, Google Calendar and Notion, or the demo ones: connecting, what the agents then read, sealed
tokens, disconnecting; and the notes errand (no network: Google and Notion are faked)."""

import dataclasses
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from roleedge.app import connect_routes, server
from roleedge.config import get_settings
from roleedge.connectors import google as g
from roleedge.errands import answer_notes
from roleedge.errands.demo_accounts import DemoNotion
from roleedge.families import CIRCLES
from roleedge.llm import LLM
from roleedge.models.errands import ErrandRequest
from roleedge.store import Store

from .conftest import FakeProvider
from .test_errands import ErrandModel, wait_for

NOTES_Q = {"kind": "notes", "merchant_hint": "", "item_en": "soup recipe", "quote": "How do I make the chicken soup?"}


def settings(google: bool = True):
    return dataclasses.replace(get_settings(), google_client_id="cid.apps.googleusercontent.com" if google else "",
                               google_client_secret="sec" if google else "", vault_key=Fernet.generate_key().decode())


class FakeGoogle:
    """Google's token, userinfo, Gmail and Calendar endpoints, as the connector calls them."""

    def __init__(self):
        self.revoked = []
        start = datetime.now(ZoneInfo("America/Los_Angeles")).replace(microsecond=0) + timedelta(days=2)
        self.events = [{"id": "e1", "summary": "Dinner with Mom #family", "location": "Mom's home",
                        "start": {"dateTime": start.replace(hour=18, minute=30).isoformat()},
                        "end": {"dateTime": start.replace(hour=20, minute=0).isoformat()}},
                       {"id": "e2", "summary": "Layoff planning with HR", "start": {"dateTime": start.replace(hour=10).isoformat()},
                        "end": {"dateTime": start.replace(hour=11).isoformat()}}]

    def exchange(self, *a):
        return {"access_token": "at-1", "refresh_token": "rt-secret", "expires_in": 3600,
                "scope": f"openid email {g.SCOPES['gmail']} {g.SCOPES['googlecalendar']}"}

    def refresh(self, *a):
        return {"access_token": "at-2", "expires_in": 3600}

    def get(self, url, params=None, headers=None, timeout=None):
        class R:
            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                pass

            def json(self):
                return self.data

        if url.endswith("/messages"):
            return R({"messages": [{"id": "18c2a1f0e0aa"}]})
        if "/messages/" in url:
            body = "Your heated blanket arrives Friday between 10 AM and 2 PM."
            import base64
            return R({"id": "18c2a1f0e0aa", "snippet": body, "payload": {
                "headers": [{"name": "From", "value": "Amazon <shipment-tracking@amazon.com>"},
                            {"name": "Subject", "value": "Arriving Friday"},
                            {"name": "Date", "value": "Mon, 2 Nov 2026 09:00:00 -0800"},
                            {"name": "Authentication-Results", "value": "mx.google.com; spf=pass; dkim=pass; dmarc=pass"}],
                "mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}})
        if url.endswith("/events"):
            return R({"items": self.events})
        raise AssertionError(url)


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(g, "exchange", fake.exchange)
    monkeypatch.setattr(g, "refresh", fake.refresh)
    monkeypatch.setattr(g, "account_email", lambda token: "maya@example.com")
    monkeypatch.setattr(g, "revoke", lambda token: fake.revoked.append(token))
    monkeypatch.setattr(g.httpx, "get", fake.get)
    return fake


def app(tmp_path, monkeypatch, model=None, google_ready=True):
    conf = settings(google_ready)
    monkeypatch.setattr(server, "get_settings", lambda: conf)
    store = Store(tmp_path / "db.sqlite")
    llm = LLM(model or FakeProvider(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    return TestClient(server.create_app(llm=llm, store=store, media=None)), store


def test_google_sign_in_connects_gmail_and_calendar_sealed_and_the_agents_read_them(tmp_path, monkeypatch, google):
    question = {"kind": "schedule", "merchant_hint": "", "item_en": "dinner", "quote": "When are you coming for dinner?"}
    model = ErrandModel(route=question)
    model.answers["schedule_reader"] = {"found": True, "item_ids": ["e1"], "when_quote": "", "spoken_text": "Maya is coming for dinner.",
                                        "screen_title": "Dinner", "english_gloss": "Maya is coming for dinner."}
    client, store = app(tmp_path, monkeypatch, model)
    with client:
        start = client.get("/api/connect/google/start?circle=chen", follow_redirects=False)
        assert start.status_code == 307
        q = parse_qs(urlsplit(start.headers["location"]).query)
        assert q["code_challenge_method"] == ["S256"] and "gmail.readonly" in q["scope"][0] and "calendar.events.readonly" in q["scope"][0]
        back = client.get(f"/api/connect/google/callback?state={q['state'][0]}&code=abc", follow_redirects=False)
        assert back.headers["location"] == "/studio?circle=chen&connect=google"
        link = store.link("chen", "gmail")
        assert link["account"] == "maya@example.com" and "rt-secret" not in str(link)  # sealed, never plain
        apps = {a["id"]: a for a in client.get("/api/connectors?circle=chen").json()}
        assert apps["gmail"]["own"] and not apps["gmail"]["demo"] and apps["googlecalendar"]["own"]
        assert not apps["slack"]["own"] and apps["slack"]["demo"]  # the others stay demo accounts
        assert client.get("/api/connectors?circle=sato").json()[0]["demo"]  # another family isn't connected
        assert client.get("/api/connectors/gmail/items?circle=chen").json()[0]["title"] == "Arriving Friday"

        client.post("/api/circles/chen/reply", json={"text": question["quote"]})
        card = wait_for(client, "chen", lambda i: i["kind"] == "approval")
        client.post(f"/api/items/{card['id']}/allow", json={"decision": "once"})
        told = wait_for(client, "chen", lambda i: i["payload"].get("errand", {}).get("kind") == "schedule")
        assert told["payload"]["errand"]["source"] == "your Google Calendar"
        seen = str(next(m for name, m in model.calls if name == "schedule_reader"))
        assert "Dinner with Mom" in seen and "Layoff" not in seen and ": busy" in seen  # untagged events are busy only

        assert client.post("/api/circles/chen/connect/gmail/disconnect").json() == {"disconnected": "gmail"}
        assert google.revoked == []  # the calendar still uses the grant
        client.post("/api/circles/chen/connect/googlecalendar/disconnect")
        assert google.revoked == ["rt-secret"] and store.link("chen", "googlecalendar") is None
        assert client.get("/api/connectors?circle=chen").json()[0]["demo"]  # back to the demo inbox


def test_without_a_google_client_connecting_says_what_to_set_up(tmp_path, monkeypatch):
    client, _ = app(tmp_path, monkeypatch, google_ready=False)
    with client:
        res = client.get("/api/connect/google/start?circle=chen", follow_redirects=False)
        assert res.status_code == 409 and "ROLEEDGE_GOOGLE_CLIENT_ID" in res.json()["detail"]
        gmail = next(a for a in client.get("/api/connectors?circle=chen").json() if a["id"] == "gmail")
        assert gmail["can_connect"] and "ROLEEDGE_GOOGLE_CLIENT_ID" in gmail["setup"] and gmail["demo"]
        assert client.get("/api/connect/google/callback?state=forged&code=x").status_code == 400  # no such sign-in


def test_notion_connects_with_its_secret_and_the_demo_notes_answer_until_then(tmp_path, monkeypatch):
    from roleedge.connectors import SourceItem

    client, store = app(tmp_path, monkeypatch)
    monkeypatch.setattr(connect_routes, "_notion_me", lambda token: {"bot": {"workspace_name": "Chen family"}})
    monkeypatch.setattr(connect_routes.Notion, "recent", lambda self, limit=10, circle=None: [SourceItem("p", "Page", "")])
    with client:
        notion = next(a for a in client.get("/api/connectors?circle=chen").json() if a["id"] == "notion")
        assert notion["demo"] and notion["connected"] and not notion["own"]
        titles = [i["title"] for i in client.get("/api/connectors/notion/items?circle=chen").json()]
        assert "Mom's chicken soup" in titles and "Home notes" in titles
        done = client.post("/api/circles/chen/connect/notion", json={"token": "ntn_" + "x" * 40}).json()
        assert done == {"connected": True, "account": "Chen family", "pages": 1}
        assert "ntn_" not in str(store.link("chen", "notion"))
        notion = next(a for a in client.get("/api/connectors?circle=chen").json() if a["id"] == "notion")
        assert notion["own"] and notion["account"] == "Chen family"


def test_her_question_is_answered_from_the_notes_and_a_password_never_goes_out(tmp_path):
    pages = [DemoNotion().read(pid, CIRCLES["chen"]) for pid in ("n_recipe", "n_home", "n_week")]

    def reader(**answer):
        model = ErrandModel(route=NOTES_Q)
        model.answers["notes_reader"] = {"found": True, "page_title": "", "quote": "", "spoken_text": "", "screen_title": "Soup",
                                         "english_gloss": "", **answer}
        return answer_notes(LLM(model, cache_dir=tmp_path / str(time.time_ns()), ledger_file=tmp_path / "u.jsonl"),
                            CIRCLES["chen"], ErrandRequest(**NOTES_Q), pages, "demo notes")

    soup = reader(page_title="Mom's chicken soup", quote="Simmer for 90 minutes, then season with salt.",
                  spoken_text="Simmer the chicken with the vegetables for 90 minutes, then add salt.")
    assert soup.gate.passed and soup.page == "Mom's chicken soup"
    two = reader(page_title="Mom's chicken soup", quote="Serves 4.\nSimmer for 90 minutes, then season with salt.",
                 spoken_text="It serves 4. Simmer it for 90 minutes, then add salt.")
    assert two.gate.passed  # two lines from different places on the page
    invented = reader(page_title="Mom's chicken soup", quote="Simmer for 3 hours.", spoken_text="Simmer it for 3 hours.")
    assert not invented.gate.passed and "notes_check" in invented.gate.rules
    password = reader(page_title="Home notes", quote="Wi-Fi password: sunflower-2024", spoken_text="The Wi-Fi password is sunflower-2024.")
    assert not password.gate.passed and any("password" in r for r in password.gate.reasons)
    refused = reader(found=False, page_title="Home notes", quote="Wi-Fi password: sunflower-2024",
                     spoken_text="I can't share passwords, but Maya will help you with that.")
    assert refused.gate.passed  # it said no: that may go out
    late = reader(page_title="Mom's week", quote="Doctor: Dr. Patel, Thursday at 10:30 AM",
                  spoken_text="Your doctor is on Thursday at 11:30 AM.")
    assert not late.gate.passed  # a time that isn't in the page


def test_gmail_reads_html_mail_as_text():
    import base64

    html = "<html><style>p{}</style><p>Your order <b>arrives</b> Friday.</p><script>x()</script></html>"
    payload = {"mimeType": "multipart/alternative", "parts": [{"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(html.encode()).decode()}}]}
    assert g._body(payload).strip() == "Your order arrives Friday."
