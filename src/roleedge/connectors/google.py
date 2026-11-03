"""A family's own Gmail and Google Calendar, read-only, once the caregiver signs in with Google (OAuth 2.0 with PKCE).

* Scopes, the least that works: ``gmail.readonly`` for delivery mails and shares, ``calendar.events.readonly`` for
  the week; ``openid email`` to show which account is connected. Nothing is ever written or sent.
* Tokens: the refresh token is sealed in the vault (``vault.py``) and stored per family; access tokens live in memory
  and are refreshed when they expire. Disconnecting revokes the token at Google and deletes it here.
* What a mail or an event says is DATA, never instructions (T2), and goes through the same checks as anything shared.
* The Google Cloud OAuth client (web application) is the deployer's: ``ROLEEDGE_GOOGLE_CLIENT_ID`` and ``_SECRET``,
  with the redirect URI registered. Gmail's read scope is a restricted scope (docs/reel-lab/INTEGRATIONS.md):
  until Google verifies the app, only the test users added on its consent screen can connect.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import Circle
from . import MAX_CHARS, ConnectorStatus, SourceItem

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (an endpoint, not a secret)
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR = "https://www.googleapis.com/calendar/v3"
SCOPES = {"gmail": "https://www.googleapis.com/auth/gmail.readonly",
          "googlecalendar": "https://www.googleapis.com/auth/calendar.events.readonly"}
TIMEOUT = 15.0


# ---------------------------------------------------------------- signing in


def pkce() -> tuple[str, str]:
    """(verifier, challenge) for the S256 code challenge."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def auth_url(client_id: str, redirect_uri: str, apps: list[str], state: str, challenge: str) -> str:
    scopes = ["openid", "email", *(SCOPES[a] for a in apps if a in SCOPES)]
    return AUTH_URL + "?" + urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
                                       "scope": " ".join(scopes), "access_type": "offline", "prompt": "consent",
                                       "include_granted_scopes": "true", "state": state,
                                       "code_challenge": challenge, "code_challenge_method": "S256"})


def exchange(client_id: str, client_secret: str, redirect_uri: str, code: str, verifier: str) -> dict[str, Any]:
    """The authorization code for tokens: access_token, refresh_token, expires_in, scope."""
    res = httpx.post(TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret, "code": code,
                                      "code_verifier": verifier, "grant_type": "authorization_code",
                                      "redirect_uri": redirect_uri}, timeout=TIMEOUT)
    res.raise_for_status()
    return res.json()


def refresh(client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    res = httpx.post(TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret,
                                      "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=TIMEOUT)
    res.raise_for_status()
    return res.json()


def revoke(token: str) -> None:
    httpx.post(REVOKE_URL, data={"token": token}, timeout=TIMEOUT)  # best effort: the local copy is deleted anyway


def account_email(access_token: str) -> str:
    res = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=TIMEOUT)
    res.raise_for_status()
    return str(res.json().get("email") or "")


@dataclass
class GoogleSession:
    """A connected account: refreshes its access token when needed. ``refresh_token`` stays in memory only while used."""

    client_id: str
    client_secret: str
    refresh_token: str
    account: str
    access_token: str = ""
    expires_at: float = 0.0
    _get: Callable[..., httpx.Response] | None = field(default=None, repr=False)  # tests swap the HTTP call

    def token(self) -> str:
        if not self.access_token or time.time() > self.expires_at - 60:
            data = refresh(self.client_id, self.client_secret, self.refresh_token)
            self.access_token = data["access_token"]
            self.expires_at = time.time() + float(data.get("expires_in") or 3600)
        return self.access_token

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        res = (self._get or httpx.get)(url, params=params, headers={"Authorization": f"Bearer {self.token()}"}, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()


# ---------------------------------------------------------------- Gmail


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _body(payload: dict[str, Any]) -> str:
    """The message's text: its text/plain part, else its HTML as text."""
    parts = [payload, *payload.get("parts", [])]
    for p in list(parts):
        parts.extend(p.get("parts", []))
    plain = next((p for p in parts if p.get("mimeType") == "text/plain" and (p.get("body") or {}).get("data")), None)
    if plain:
        return _decode(plain["body"]["data"])
    html = next((p for p in parts if p.get("mimeType") == "text/html" and (p.get("body") or {}).get("data")), None)
    if html:
        parser = _Text()
        parser.feed(_decode(html["body"]["data"]))
        return re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
    return ""


def _headers(msg: dict[str, Any]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in (msg.get("payload") or {}).get("headers", [])}


def _when(header: str) -> str:
    try:
        return parsedate_to_datetime(header).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        return ""


class Gmail:
    """The caregiver's own Gmail, read-only."""

    id, label, icon = "gmail", "Gmail", "mail"

    def __init__(self, session: GoogleSession) -> None:
        self.session = session

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.id, self.label, self.icon, True, f"Your Gmail: {self.session.account}")

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return []

    def messages(self, query: str = "newer_than:14d -in:spam -in:trash", limit: int = 15) -> list[dict[str, str]]:
        """Recent mails as {id, sender, auth, subject, body, received}: ``auth`` is the Authentication-Results header the
        receiving server added, so the same sender check as the demo inbox runs on real mail."""
        listed = self.session.get(f"{GMAIL}/messages", {"q": query, "maxResults": max(1, min(limit, 25))}).get("messages", [])
        out = []
        for ref in listed:
            msg = self.session.get(f"{GMAIL}/messages/{ref['id']}", {"format": "full"})
            h = _headers(msg)
            out.append({"id": msg["id"], "sender": h.get("from", ""), "auth": h.get("authentication-results", ""),
                        "subject": h.get("subject", "(no subject)"), "body": _body(msg.get("payload") or {})[:MAX_CHARS],
                        "received": _when(h.get("date", "")), "snippet": msg.get("snippet", "")})
        return out

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        return [SourceItem(m["id"], m["subject"], m["received"], m["snippet"][:120], subtitle=m["sender"].split("<")[0].strip(),
                           badge="Sender verified" if "dmarc=pass" in m["auth"].lower() else "", tone="ok" if "dmarc=pass" in m["auth"].lower() else "")
                for m in self.messages(limit=limit)]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        if not re.fullmatch(r"[0-9a-fA-F]{8,32}", item_id):
            raise ValueError("Not a Gmail message id.")
        msg = self.session.get(f"{GMAIL}/messages/{item_id}", {"format": "full"})
        h = _headers(msg)
        check = "passed (SPF, DKIM and DMARC)" if "dmarc=pass" in h.get("authentication-results", "").lower() else "not passed"
        return h.get("subject", "(no subject)"), (f"From: {h.get('from', '')}\nSender check: {check}\nReceived: {h.get('date', '')}\n\n"
                                                  f"{_body(msg.get('payload') or {})}")[:MAX_CHARS]


# ---------------------------------------------------------------- Google Calendar

FAMILY_TAG = re.compile(r"#family|\bfamily\b|\bmom\b|\bmum\b|\bgrandma\b|\bvisit\b|家族|母|実家", re.I)
TRAVEL_TAG = re.compile(r"\bflight\b|\btrain\b|\btrip\b|\bairport\b|新幹線|出張|旅行", re.I)


class GoogleCalendar:
    """The caregiver's own Google Calendar, read-only. An event counts as family or travel only when it says so (a
    #family tag, "Mom", "visit", a flight or a train); everything else is shown to her as busy, never its title."""

    id, label, icon = "googlecalendar", "Google Calendar", "calendar"

    def __init__(self, session: GoogleSession) -> None:
        self.session = session

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.id, self.label, self.icon, True, f"Your calendar: {self.session.account}")

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return []

    def events(self, days: int = 14) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        data = self.session.get(f"{CALENDAR}/calendars/primary/events",
                                {"timeMin": now.isoformat(), "timeMax": (now + timedelta(days=days)).isoformat(),
                                 "singleEvents": "true", "orderBy": "startTime", "maxResults": 50})
        out = []
        for e in data.get("items", []):
            start = (e.get("start") or {}).get("dateTime") or ((e.get("start") or {}).get("date", "") + "T00:00:00+00:00")
            end = (e.get("end") or {}).get("dateTime") or ((e.get("end") or {}).get("date", "") + "T00:00:00+00:00")
            try:
                s, t = datetime.fromisoformat(start), datetime.fromisoformat(end)
            except ValueError:
                continue
            text = f"{e.get('summary', '')} {e.get('description', '')}"
            kind = "travel" if TRAVEL_TAG.search(text) else "family_events" if FAMILY_TAG.search(text) else "work"
            out.append({"id": e.get("id", ""), "title": e.get("summary", "Busy"), "start": s,
                        "minutes": max(1, int((t - s).total_seconds() // 60)), "kind": kind, "where": e.get("location", "")})
        return out

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        return [SourceItem(e["id"], e["title"], e["start"].isoformat(timespec="minutes"), e["where"],
                           subtitle=f"{e['start']:%a %d %b · %H:%M}", badge="Work" if e["kind"] == "work" else "")
                for e in self.events()[:limit]]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        event = next((e for e in self.events() if e["id"] == item_id), None)
        if event is None:
            raise ValueError("No such event.")
        return event["title"], f"Calendar event: {event['title']}\nWhen: {event['start']:%A %d %B %Y, %H:%M} ({event['minutes']} minutes)\n" \
                               + (f"Where: {event['where']}\n" if event["where"] else "")
