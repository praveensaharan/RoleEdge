"""The lab's spending limit: $70 for the whole Reel Lab (raised by the user from $50, then $55), new runs stop at $69.50.

Spent = the Meta spend in the app's usage ledger (every lab ledger is appended to it when its run ends, so it is
counted once) + Muse Voice Transcribe at $0.18 an audio hour (it is billed per audio time, not per token) + Muse Image
at $0.01 a picture. The usage ledger also holds the app's own calls from before the lab started, so the figure errs
high.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..costs import spend
from . import LAB

LIMIT_USD = 70.0  # $50, then $55 (2026-11-03), then raised to $70 by the user (2026-11-04)
STOP_AT_USD = 69.5  # stop half a dollar short of the limit
TRANSCRIBE_USD_PER_HOUR = 0.18


def lab_rows(ledger: Path) -> str:
    """A lab ledger's rows for the app's usage ledger, each marked "source": "lab": the credit meter counts them, the
    demo's spend guard doesn't."""
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    return "".join(json.dumps({**row, "source": "lab"}) + "\n" for row in rows)


def transcription_usd() -> float:
    seconds = 0.0
    for path in LAB.glob("*/transcript.json"):
        heard = json.loads(path.read_text(encoding="utf-8"))
        seconds += min(float(heard.get("duration_s") or 0), 600)
    return seconds / 3600 * TRANSCRIBE_USD_PER_HOUR


def images_usd() -> float:
    """Muse Image pictures the lab drew ($0.01 each; images are not in the token ledger)."""
    return 0.01 * sum(1 for _ in LAB.glob("*/picture-*.png"))


def spent() -> dict[str, float]:
    meta = spend()["meta_usd"]
    heard = transcription_usd()
    drawn = images_usd()
    return {"meta_usd": round(meta, 4), "transcribe_usd": round(heard, 4), "images_usd": round(drawn, 2),
            "total_usd": round(meta + heard + drawn, 4), "limit_usd": LIMIT_USD, "stop_at_usd": STOP_AT_USD}


def can_spend(estimate_usd: float) -> bool:
    """True if a batch estimated at ``estimate_usd`` stays under the stop line."""
    return spent()["total_usd"] + estimate_usd <= STOP_AT_USD
