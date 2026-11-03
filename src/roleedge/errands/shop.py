"""The demo shop: a small catalog of what people buy online, Rakuten Ichiba for the Japan circle and Amazon for the US one.

Prices and checkout are simulated and labelled so on screen (HACKATHON.md: simulated parts are labelled). A real
store API (Rakuten Ichiba Item Search, say) would replace ``CATALOG`` and ``place_order``; the limits, the
permission and the code-written price messages stay the same. Prices are only ever written by code, never by a
model, so a price she hears is the price in the catalog.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from ..config import APP_WEB_DIR

SHOP_DIR = APP_WEB_DIR / "demo" / "shop"


@dataclass(frozen=True)
class Offer:
    id: str
    store: str
    name: str  # in the store's language
    name_en: str
    price: int  # whole yen, or cents for USD
    currency: str  # JPY or USD
    shipping_free: bool
    delivery_days: int
    keywords: tuple[str, ...]  # English words she might use (the router gives English)

    @property
    def image(self) -> str:
        """The product photo the cards show (a synthetic shot in web/app/demo/shop), or "" if there is none."""
        return f"/assets/demo/shop/{self.id}.jpg" if (SHOP_DIR / f"{self.id}.jpg").exists() else ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "image": self.image}


STORES = {"JPY": "Rakuten Ichiba", "USD": "Amazon"}
CATALOG: dict[str, list[Offer]] = {
    "JPY": [  # what people really buy on Rakuten: clothes, cosmetics, small electronics, things for the home
        Offer("rk_cardigan", "Rakuten Ichiba", "ウール混 カーディガン ネイビー M", "Wool-blend cardigan, navy, size M", 2980, "JPY", True, 3,
              ("cardigan", "sweater", "knit", "jumper", "cardy")),
        Offer("rk_handcream", "Rakuten Ichiba", "保湿 ハンドクリーム 2本セット", "Moisturising hand cream, 2 tubes", 1280, "JPY", False, 2,
              ("hand", "cream", "lotion", "moisturiser", "moisturizer")),
        Offer("rk_blanket", "Rakuten Ichiba", "電気ひざ掛け 洗える", "Electric lap blanket, washable", 3480, "JPY", True, 2,
              ("blanket", "electric", "heated", "lap", "warmer")),
        Offer("rk_lamp", "Rakuten Ichiba", "LED デスクライト 調光", "LED desk lamp, dimmable", 2480, "JPY", True, 2,
              ("lamp", "light", "desk", "reading", "led")),
        Offer("rk_slippers", "Rakuten Ichiba", "あったか ルームシューズ M", "Warm house slippers, size M", 1580, "JPY", False, 3,
              ("slippers", "slipper", "house", "shoes")),
    ],
    "USD": [
        Offer("az_rice5", "Amazon", "Jasmine rice, 5 lb", "Jasmine rice, 5 lb", 849, "USD", True, 2, ("rice", "jasmine")),
        Offer("az_towels", "Amazon", "Paper towels, 6 rolls", "Paper towels, 6 rolls", 1299, "USD", True, 1,
              ("paper", "towels", "towel", "kitchen", "roll")),
        Offer("az_tea", "Amazon", "Green tea, 100 bags", "Green tea, 100 bags", 999, "USD", True, 2, ("tea", "green", "teabags")),
        Offer("az_soap", "Amazon", "Laundry detergent, 92 oz", "Laundry detergent, 92 oz", 1197, "USD", True, 2,
              ("detergent", "laundry", "washing", "soap")),
        Offer("az_tissue", "Amazon", "Tissues, 6 boxes", "Tissues, 6 boxes", 949, "USD", True, 1, ("tissues", "tissue", "kleenex")),
    ],
}


def search(currency: str, query_en: str) -> Offer | None:
    """The catalog item that best matches the words she used (in English), or None."""
    words = set(re.findall(r"[a-z]+", query_en.lower()))
    words |= {w[:-1] for w in words if w.endswith("s")}  # "towels" -> "towel"
    scored = [(len(words & set(o.keywords)), o) for o in CATALOG.get(currency, [])]
    best = max(scored, key=lambda pair: pair[0], default=(0, None))
    return best[1] if best[0] else None


def offer(offer_id: str) -> Offer | None:
    return next((o for offers in CATALOG.values() for o in offers if o.id == offer_id), None)


def money(amount: int, currency: str) -> str:
    return f"¥{amount:,}" if currency == "JPY" else f"${amount / 100:,.2f}"


def place_order(chosen: Offer, now: datetime) -> dict[str, Any]:
    """A simulated checkout: an order number and the delivery date the store would give."""
    arrives = now + timedelta(days=chosen.delivery_days)
    return {"order_id": f"SIM-{now:%m%d%H%M}-{chosen.id}", "total": chosen.price, "currency": chosen.currency,
            "arrives": arrives.date().isoformat(), "simulated": True}
