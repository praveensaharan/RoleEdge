"""Guards for a demo that may be reachable by anyone: a cap on Meta spend and a per-minute limit on requests that
call a model. Each kind of request has its own ``Budget``; all of them share the spend cap. The cap counts the app's
own calls in its usage ledger, not the evaluation lab's (docs/REEL_LAB.md), which the credit meter still shows.

``SpendCap`` applies the same cap to every model call, so a run in progress also stops at it. ``LedgerBackup`` keeps a copy of that ledger on lasting storage, so a restart or a new deploy doesn't reset the spend."""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import HTTPException

from ..config import LEDGER_FILE
from ..costs import spend
from ..llm import ProviderError


class Budget:
    def __init__(self, *, per_minute: int, spend_cap_usd: float, what: str = "requests", ledger_file: Path = LEDGER_FILE) -> None:
        self.per_minute, self.spend_cap_usd, self.what, self.ledger_file = per_minute, spend_cap_usd, what, ledger_file
        self.stamps: deque[float] = deque()

    def check(self) -> None:
        """Raise 429 if the minute's allowance or the spend cap is used up (nothing is taken)."""
        now = time.monotonic()
        while self.stamps and now - self.stamps[0] > 60:
            self.stamps.popleft()
        if len(self.stamps) >= self.per_minute:
            raise HTTPException(429, f"Too many {self.what} in the last minute. Wait a moment and try again.")
        if spend(self.ledger_file)["meta_app_usd"] >= self.spend_cap_usd:
            raise HTTPException(429, "The demo's model budget is used up for now.")

    def take(self) -> float:
        """Check, then count one request; returns a stamp that ``give_back`` accepts if the request is refused later."""
        self.check()
        stamp = time.monotonic()
        self.stamps.append(stamp)
        return stamp

    def give_back(self, stamp: float) -> None:
        with contextlib.suppress(ValueError):
            self.stamps.remove(stamp)


class SpendCap:
    """``LLM(before_call=...)``: no new model call once the ledger shows the cap's worth of Meta spend. Cached replays
    still work (they cost nothing). Calls already under way finish, so the total can pass the cap by a few cents."""

    def __init__(self, spend_cap_usd: float, ledger_file: Path = LEDGER_FILE) -> None:
        self.spend_cap_usd, self.ledger_file = spend_cap_usd, ledger_file

    def __call__(self) -> None:
        if spend(self.ledger_file)["meta_app_usd"] >= self.spend_cap_usd:
            raise ProviderError("meta", "the demo's model budget is used up for now")


class LedgerBackup:
    """A copy of the usage ledger on storage that outlives the server (on Cloud Run: a Cloud Storage bucket mounted as
    a folder). A new server starts from the copy, so the spend cap still counts what was spent before. Model calls keep
    appending to the local ledger, which is fast; the copy is refreshed every few seconds and when the server stops."""

    def __init__(self, ledger_file: Path, backup_file: Path, every_s: float = 10.0) -> None:
        self.ledger_file, self.backup_file, self.every_s = ledger_file, backup_file, every_s
        self._saved = -1  # bytes of the ledger in the copy; -1 = not written yet
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def restore(self) -> None:
        """Start from the copy, unless this server already has a ledger of its own."""
        if self.backup_file.exists() and not self.ledger_file.exists():
            self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_file.write_bytes(self.backup_file.read_bytes())
            self._saved = self.ledger_file.stat().st_size

    def save(self) -> None:
        """Write the ledger's complete lines to the copy, if there is anything new."""
        data = self.ledger_file.read_bytes() if self.ledger_file.exists() else b""
        data = data[: data.rfind(b"\n") + 1]  # a line being appended right now waits for the next save
        if len(data) != self._saved:
            self.backup_file.write_bytes(data)
            self._saved = len(data)

    def start(self) -> None:
        self.restore()
        self._save_logged()  # the first save also shows at once whether the copy can be written
        self._thread = threading.Thread(target=self._run, name="ledger-backup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._save_logged()

    def _run(self) -> None:
        while not self._stop.wait(self.every_s):
            self._save_logged()

    def _save_logged(self) -> None:
        try:
            self.save()
        except OSError as exc:
            logging.getLogger("roleedge").error("Could not save the usage ledger to %s: %s", self.backup_file, exc)
