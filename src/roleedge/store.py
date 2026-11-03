"""A small SQLite store for circles, thread items, signal events, voice measurements and what was added to the demo apps.

One table per kind, each row a JSON document, because the pydantic models are the schema (rule A4). The file lives
in ``output/`` (generated, never committed). ``reset`` loads circles and their history (the demo passes the
synthetic ones from ``families``).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from .config import OUTPUT_DIR
from .models import Circle, SignalEvent, ThreadItem, VoiceDay
from .models.errands import AddedItem

DB_FILE = OUTPUT_DIR / "roleedge.sqlite"
TABLES = ("circles", "items", "events", "voice", "apps", "links")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Store:
    def __init__(self, path: Path = DB_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            for table in TABLES:
                self._db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, circle_id TEXT, "
                                 "sort TEXT, doc TEXT)")

    # ---------------------------------------------------------------- generic

    def _put(self, table: str, row_id: str, circle_id: str, sort: str, doc: dict) -> None:
        with self._lock, self._db:
            self._db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?, ?)",
                             (row_id, circle_id, sort, json.dumps(doc, ensure_ascii=False)))

    def _all(self, table: str, circle_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(f"SELECT doc FROM {table} WHERE circle_id = ? ORDER BY sort, id",
                                    (circle_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ---------------------------------------------------------------- circles

    def circles(self) -> list[Circle]:
        with self._lock:
            rows = self._db.execute("SELECT doc FROM circles ORDER BY id").fetchall()
        return [Circle.model_validate_json(r[0]) for r in rows]

    def circle(self, circle_id: str) -> Circle | None:
        return next((c for c in self.circles() if c.id == circle_id), None)

    def save_circle(self, circle: Circle) -> None:
        self._put("circles", circle.id, circle.id, circle.id, circle.model_dump())

    # ---------------------------------------------------------------- thread

    def items(self, circle_id: str) -> list[ThreadItem]:
        return [ThreadItem.model_validate(d) for d in self._all("items", circle_id)]

    def item(self, item_id: str) -> ThreadItem | None:
        with self._lock:
            row = self._db.execute("SELECT doc FROM items WHERE id = ?", (item_id,)).fetchone()
        return ThreadItem.model_validate_json(row[0]) if row else None

    def save_item(self, item: ThreadItem) -> None:
        self._put("items", item.id, item.circle_id, item.at, item.model_dump())

    # ---------------------------------------------------------------- signals

    def add_events(self, circle_id: str, events: list[SignalEvent]) -> None:
        for event in events:
            self._put("events", new_id("ev"), circle_id, event.day, event.model_dump())

    def events(self, circle_id: str) -> list[SignalEvent]:
        return [SignalEvent.model_validate(d) for d in self._all("events", circle_id)]

    def add_voice_day(self, circle_id: str, day: VoiceDay) -> None:
        self._put("voice", f"{circle_id}-{day.day}", circle_id, day.day, day.model_dump())

    def merge_voice_day(self, circle_id: str, day: VoiceDay) -> None:
        """Average a new reply's measurements into that day's values."""
        old = next((v for v in self.voice_days(circle_id) if v.day == day.day), None)
        if old:
            day = VoiceDay(day=day.day, speech_rate_wpm=round((old.speech_rate_wpm + day.speech_rate_wpm) / 2, 1),
                           pause_ratio=round((old.pause_ratio + day.pause_ratio) / 2, 3),
                           reply_seconds=round((old.reply_seconds + day.reply_seconds) / 2, 1))
        self.add_voice_day(circle_id, day)

    def voice_days(self, circle_id: str) -> list[VoiceDay]:
        return [VoiceDay.model_validate(d) for d in self._all("voice", circle_id)]

    # ---------------------------------------------------------------- the demo apps

    def add_app_item(self, circle_id: str, item: AddedItem) -> None:
        self._put("apps", item.id, circle_id, item.at, item.model_dump())

    def app_items(self, circle_id: str, app: str = "") -> list[AddedItem]:
        items = [AddedItem.model_validate(d) for d in self._all("apps", circle_id)]
        return [i for i in items if not app or i.app == app]

    def remove_app_item(self, circle_id: str, item_id: str) -> bool:
        with self._lock, self._db:
            return self._db.execute("DELETE FROM apps WHERE id = ? AND circle_id = ?", (item_id, circle_id)).rowcount > 0

    # ---------------------------------------------------------------- accounts a family connected (tokens sealed)

    def save_link(self, circle_id: str, app: str, doc: dict) -> None:
        """A connected account: {app, account, sealed (the encrypted token), scopes, connected_at}. Never plain tokens."""
        self._put("links", f"{circle_id}:{app}", circle_id, app, {**doc, "app": app, "circle_id": circle_id})

    def link(self, circle_id: str, app: str) -> dict | None:
        return next((d for d in self._all("links", circle_id) if d.get("app") == app), None)

    def remove_link(self, circle_id: str, app: str) -> bool:
        with self._lock, self._db:
            return self._db.execute("DELETE FROM links WHERE id = ?", (f"{circle_id}:{app}",)).rowcount > 0

    # ---------------------------------------------------------------- demo

    def reset(self, circles: Iterable[Circle],
              history: Callable[[str], tuple[list[SignalEvent], list[VoiceDay]]]) -> None:
        """Wipe everything and load ``circles`` with the history ``history(circle_id)`` returns. Accounts a family
        connected stay connected: a demo reset is not a sign-out."""
        with self._lock, self._db:
            for table in TABLES:
                if table != "links":
                    self._db.execute(f"DELETE FROM {table}")
        for circle in circles:
            self.save_circle(circle)
            events, voice = history(circle.id)
            self.add_events(circle.id, events)
            for day in voice:
                self.add_voice_day(circle.id, day)
