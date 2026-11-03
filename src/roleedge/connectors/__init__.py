"""Apps the caregiver can share from into the Studio: Gmail, Slack, Google Photos, Zoom, Notion, Spotify and LINE.

Each connector lists recent items and reads one as plain text (and, for a photo, as a picture). What it reads is
DATA, never instructions (T2): it goes through the same research, checks, gates and approval as anything typed into
the share box.

* **Gmail**, **Slack**, **Google Photos** and **Zoom** are demo accounts (``errands.demo_accounts``): synthetic data for
  each circle, labelled "demo account", until the person's own sign-in is connected (Google OAuth with the Gmail
  read-only or Photos picker scope, a Slack user token, Zoom OAuth; docs/PIVOT.md C2).
* **Notion** works when ``NOTION_TOKEN`` is set: an internal integration, with the pages it may read shared to it.
* **Spotify** and **LINE** are declared, so the API and the share box are ready for them.

Adding an app means one class with ``status``, ``recent``, ``read`` and ``images``, and one line in ``connectors()``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from ..models import Circle

MAX_CHARS = 12_000


@dataclass(frozen=True)
class SourceItem:
    id: str
    title: str
    edited: str  # ISO time of the last edit (or when a mail arrived, a photo was taken, a meeting starts)
    snippet: str = ""
    subtitle: str = ""  # who sent it, the channel, or when a meeting is
    thumb: str = ""  # a preview picture's URL (photos)
    badge: str = ""  # e.g. "Sender verified", "Failed sender check", "Work"
    tone: str = ""  # the badge's status colour: "ok", "urgent" or "" (neutral)


@dataclass(frozen=True)
class ConnectorStatus:
    id: str
    label: str
    icon: str  # a line-icon name from /api/icons
    connected: bool
    detail: str  # what it reads, or what connecting it needs
    demo: bool = False  # a demo account with synthetic data, not the person's own

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NotConnected(Exception):
    """The app isn't connected yet."""


class Connector(Protocol):
    id: str

    def status(self) -> ConnectorStatus: ...
    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]: ...
    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]: ...  # (title, text)
    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]: ...  # pictures for the reader


class Pending:
    """An app the share box offers but that isn't connected yet."""

    def __init__(self, id: str, label: str, icon: str, needs: str) -> None:
        self.id, self.label, self.icon, self.needs = id, label, icon, needs

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.id, self.label, self.icon, False, self.needs)

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        raise NotConnected(f"{self.label} isn't connected yet.")

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        raise NotConnected(f"{self.label} isn't connected yet.")

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return []


class Notion:
    """Read-only Notion: the pages shared with the integration, newest first, read as plain text."""

    id = "notion"
    API = "https://api.notion.com/v1"
    VERSION = "2022-06-28"
    PAGE_ID = re.compile(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}")
    TEXT_BLOCKS = {"paragraph": "", "heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "quote": "> ",
                   "bulleted_list_item": "- ", "numbered_list_item": "- ", "to_do": "- ", "callout": "", "toggle": ""}

    def __init__(self, token: str, timeout: float = 15.0) -> None:
        self.headers = {"Authorization": f"Bearer {token}", "Notion-Version": self.VERSION}
        self.timeout = timeout

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.id, "Notion", "document", True, "Pages shared with the RoleEdge integration")

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = httpx.request(method, f"{self.API}{path}", headers=self.headers, json=body, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return []

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        """Newest first, following Notion's pages of results up to ``limit`` (at most 200). Search can take a minute
        to list a page that was just created."""
        found: list[dict[str, Any]] = []
        cursor = None
        while len(found) < min(limit, 200):
            body = {"filter": {"property": "object", "value": "page"}, "page_size": max(1, min(limit - len(found), 100)),
                    "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
            data = self._call("POST", "/search", {**body, **({"start_cursor": cursor} if cursor else {})})
            found += data.get("results", [])
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                break
        return [SourceItem(page["id"], _page_title(page) or "Untitled", page.get("last_edited_time", ""))
                for page in found[:limit]]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        """The page as plain text: a database row's properties first, then every text block, including those inside
        toggles, lists and columns (two levels down)."""
        if not self.PAGE_ID.fullmatch(item_id):
            raise ValueError("Not a Notion page id.")
        page = self._call("GET", f"/pages/{item_id}")
        lines = _properties(page)
        self._blocks(item_id, lines, depth=0)
        return _page_title(page) or "Untitled", "\n".join(lines)[:MAX_CHARS]

    def _blocks(self, block_id: str, lines: list[str], depth: int) -> None:
        cursor = None
        while sum(len(line) for line in lines) < MAX_CHARS:
            data = self._call("GET", f"/blocks/{block_id}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else ""))
            for block in data.get("results", []):
                kind = block.get("type", "")
                if kind in self.TEXT_BLOCKS:
                    text = _plain(block.get(kind, {}).get("rich_text", []))
                    if text:
                        lines.append("  " * depth + self.TEXT_BLOCKS[kind] + text)
                elif kind == "bookmark" and block["bookmark"].get("url"):
                    lines.append("  " * depth + f"Link: {block['bookmark']['url']}")
                if block.get("has_children") and depth < 2 and kind not in ("child_page", "child_database"):
                    self._blocks(block["id"], lines, depth + 1)
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                return


def _plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(part.get("plain_text", "") for part in rich_text).strip()


def _properties(page: dict[str, Any]) -> list[str]:
    """A database row's filled-in properties as "Name: value" lines (the title is returned separately)."""
    lines = []
    for name, prop in (page.get("properties") or {}).items():
        kind = prop.get("type", "")
        value = prop.get(kind)
        if kind == "rich_text":
            text = _plain(value or [])
        elif kind == "select" or kind == "status":
            text = (value or {}).get("name", "")
        elif kind == "multi_select":
            text = ", ".join(v.get("name", "") for v in value or [])
        elif kind == "date":
            text = " to ".join(x for x in ((value or {}).get("start"), (value or {}).get("end")) if x)
        elif kind in ("number", "url", "email", "phone_number", "checkbox"):
            text = "" if value is None or value is False else str(value)
        else:
            text = ""
        if text:
            lines.append(f"{name}: {text}")
    return lines


def _page_title(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return _plain(prop.get("title", []))
    return ""


def connectors(notion_token: str = "") -> dict[str, Connector]:
    """The apps that are real or not connected yet (``errands.demo_accounts.app_connectors`` adds the demo accounts)."""
    notion: Connector = Notion(notion_token) if notion_token else Pending(
        "notion", "Notion", "document", "Not connected: add NOTION_TOKEN (an internal integration) to .env")
    return {
        "notion": notion,
        "spotify": Pending("spotify", "Spotify", "play", "Coming next: Spotify sign-in to share a song, playlist or podcast"),
        "line": Pending("line", "LINE", "chat", "Coming next: LINE Login to share a message or photo from the family group"),
    }
