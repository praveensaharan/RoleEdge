"""A family's own accounts, or the demo ones: connect Gmail and Google Calendar (Google sign-in) or Notion (an
integration secret), per circle; until then, and after a disconnect, the prefilled demo accounts answer instead.

* ``ConnectedApps`` is what the Studio and the errands ask for an app: the family's own account if they connected
  one, otherwise the demo account (``errands.demo_accounts``). Every screen says which it is.
* Google: ``/api/connect/google/start`` sends the caregiver to Google's consent screen (read-only scopes, PKCE);
  ``/api/connect/google/callback`` stores the refresh token sealed in the vault. Without a Google OAuth client in
  .env, connecting explains what to set up instead of failing.
* Notion: the caregiver pastes an internal integration secret; it is checked against Notion before it is stored.
* Disconnect revokes at Google and deletes the sealed token. A demo reset doesn't sign anyone out.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ..config import Settings
from ..connectors import Connector, Notion
from ..connectors import google as g
from ..connectors.vault import Vault
from ..models import Circle
from ..store import Store, now_iso

OWN_APPS = ("gmail", "googlecalendar", "notion")  # the apps a family can connect their own account for
STATE_TTL_S = 600


class ConnectedApps:
    """The apps for one family: their own connected account where there is one, else the demo account."""

    def __init__(self, base: dict[str, Connector], store: Store | None = None, settings: Settings | None = None,
                 vault: Vault | None = None) -> None:
        self.base, self.store, self.settings = base, store, settings
        self.vault = vault
        self._sessions: dict[tuple[str, str], Any] = {}  # (circle, app) -> a live connector (keeps its access token)

    # ---------------------------------------------------------------- lookups

    def own(self, app: str, circle: Circle | str | None) -> Connector | None:
        """The family's own connected account for ``app``, or None."""
        circle_id = circle.id if isinstance(circle, Circle) else circle
        if not circle_id or self.store is None or app not in OWN_APPS:
            return None
        link = self.store.link(circle_id, app)
        if not link:
            self._sessions.pop((circle_id, app), None)
            return None
        key = (circle_id, app)
        if key not in self._sessions:
            token = self._vault().open(link["sealed"])
            if app == "notion":
                self._sessions[key] = Notion(token)
            else:
                session = g.GoogleSession(self.settings.google_client_id, self.settings.google_client_secret, token,  # type: ignore[union-attr]
                                          link.get("account", ""))
                self._sessions[key] = g.Gmail(session) if app == "gmail" else g.GoogleCalendar(session)
        return self._sessions[key]

    def get(self, app: str, circle: Circle | str | None = None) -> Connector | None:
        return self.own(app, circle) or self.base.get(app)

    def statuses(self, circle: Circle | str | None = None) -> list[dict[str, Any]]:
        out = []
        for app, connector in self.base.items():
            own = self.own(app, circle)
            status = (own or connector).status().to_dict()
            link = self.store.link(circle.id if isinstance(circle, Circle) else circle, app) if (own and self.store and circle) else None
            status.update(own=bool(own), account=(link or {}).get("account", ""), can_connect=app in OWN_APPS,
                          setup=self.setup_needed(app))
            if own:
                status["demo"] = False
            out.append(status)
        return out

    def setup_needed(self, app: str) -> str:
        """What the deployer must set up before a family can connect ``app``; "" when it is ready."""
        if app in ("gmail", "googlecalendar") and not (self.settings and self.settings.google_client_id and self.settings.google_client_secret):
            return ("Google sign-in isn't set up on this server yet: add ROLEEDGE_GOOGLE_CLIENT_ID and ROLEEDGE_GOOGLE_CLIENT_SECRET "
                    "(a Google Cloud OAuth client for a web application, redirect URI "
                    f"{self.settings.google_redirect_uri if self.settings else ''}) to .env.")
        return ""

    def forget(self, circle_id: str, app: str) -> None:
        self._sessions.pop((circle_id, app), None)

    def _vault(self) -> Vault:
        if self.vault is None:
            self.vault = Vault(self.settings.vault_key if self.settings else "")
        return self.vault


class NotionSecret(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def add_connect_routes(app: FastAPI, *, apps: ConnectedApps, store: Store, settings: Settings,
                       circle_or_404: Callable[[str], Circle]) -> None:
    pending: dict[str, dict[str, Any]] = {}  # OAuth state -> {circle, apps, verifier, at}

    @app.get("/api/circles/{circle_id}/connections")
    def connections(circle_id: str) -> list[dict[str, Any]]:
        return apps.statuses(circle_or_404(circle_id))

    @app.get("/api/connect/google/start")
    def google_start(circle: str, which: str = "gmail,googlecalendar") -> RedirectResponse:
        circle_or_404(circle)
        wanted = [a for a in which.split(",") if a in g.SCOPES]
        if not wanted:
            raise HTTPException(400, "Choose Gmail, Google Calendar or both.")
        need = apps.setup_needed("gmail")
        if need:
            raise HTTPException(409, need)
        for state in [s for s, p in pending.items() if time.time() - p["at"] > STATE_TTL_S]:
            pending.pop(state, None)
        state = secrets.token_urlsafe(24)
        verifier, challenge = g.pkce()
        pending[state] = {"circle": circle, "apps": wanted, "verifier": verifier, "at": time.time()}
        return RedirectResponse(g.auth_url(settings.google_client_id, settings.google_redirect_uri, wanted, state, challenge))

    @app.get("/api/connect/google/callback")
    async def google_callback(state: str = "", code: str = "", error: str = "") -> RedirectResponse:
        started = pending.pop(state, None)
        if started is None or time.time() - started["at"] > STATE_TTL_S:
            raise HTTPException(400, "This sign-in link has expired. Start again from the Studio.")
        circle_id = started["circle"]
        if error or not code:
            return RedirectResponse(f"/studio?circle={circle_id}&connect=cancelled")
        try:
            tokens = await run_in_threadpool(g.exchange, settings.google_client_id, settings.google_client_secret,
                                             settings.google_redirect_uri, code, started["verifier"])
            account = await run_in_threadpool(g.account_email, tokens["access_token"])
        except (httpx.HTTPError, KeyError):
            return RedirectResponse(f"/studio?circle={circle_id}&connect=failed")
        if not tokens.get("refresh_token"):
            return RedirectResponse(f"/studio?circle={circle_id}&connect=failed")
        granted = set(str(tokens.get("scope", "")).split())
        sealed = apps._vault().seal(tokens["refresh_token"])
        for which in started["apps"]:
            if g.SCOPES[which] in granted:
                store.save_link(circle_id, which, {"account": account, "sealed": sealed, "scopes": [g.SCOPES[which]],
                                                   "connected_at": now_iso()})
                apps.forget(circle_id, which)
        return RedirectResponse(f"/studio?circle={circle_id}&connect=google")

    @app.post("/api/circles/{circle_id}/connect/notion")
    async def notion_connect(circle_id: str, req: NotionSecret) -> dict[str, Any]:
        circle_or_404(circle_id)
        token = req.token.strip()
        try:
            me = await run_in_threadpool(_notion_me, token)
            pages = await run_in_threadpool(lambda: Notion(token).recent(limit=100))
        except httpx.HTTPError:
            raise HTTPException(400, "Notion didn't accept that secret. Copy it again from the integration's page.") from None
        account = me.get("bot", {}).get("workspace_name") or me.get("name") or "Notion"
        store.save_link(circle_id, "notion", {"account": account, "sealed": apps._vault().seal(token), "scopes": ["read content"],
                                             "connected_at": now_iso(), "pages": len(pages)})
        apps.forget(circle_id, "notion")
        return {"connected": True, "account": account, "pages": len(pages)}

    @app.post("/api/circles/{circle_id}/connect/{app_id}/disconnect")
    async def disconnect(circle_id: str, app_id: str) -> dict[str, Any]:
        circle_or_404(circle_id)
        link = store.link(circle_id, app_id)
        if link is None:
            raise HTTPException(404, "That app isn't connected for this family.")
        if app_id in g.SCOPES:
            still = [a for a in g.SCOPES if a != app_id and store.link(circle_id, a)]
            if not still:  # the last Google app: revoke the grant at Google too
                await run_in_threadpool(lambda: g.revoke(apps._vault().open(link["sealed"])))
        store.remove_link(circle_id, app_id)
        apps.forget(circle_id, app_id)
        return {"disconnected": app_id}


def _notion_me(token: str) -> dict[str, Any]:
    res = httpx.get(f"{Notion.API}/users/me", headers={"Authorization": f"Bearer {token}", "Notion-Version": Notion.VERSION},
                    timeout=15)
    res.raise_for_status()
    return res.json()
