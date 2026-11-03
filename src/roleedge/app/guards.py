"""Guards for a demo that may be reachable by anyone: a cap on Meta spend and a per-minute limit on requests that
call a model. Each kind of request has its own ``Budget``; all of them share the spend cap. The cap counts the app's
own calls in its usage ledger, not the evaluation lab's (docs/REEL_LAB.md), which the credit meter still shows."""

from __future__ import annotations

import contextlib
import time
from collections import deque
from pathlib import Path

from fastapi import HTTPException

from ..config import LEDGER_FILE
from ..costs import spend


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
