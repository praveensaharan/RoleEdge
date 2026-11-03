"""The demo mailbox: synthetic delivery mails in the caregiver's inbox, timed around "now" so answers feel live.

Real Gmail needs the caregiver's Google sign-in (docs/PIVOT.md C2); until then this inbox stands in for it and is
labelled "demo mailbox" on screen. It holds the mails a real inbox would: a food delivery on its way, a parcel, a
grocery or rice delivery, and one fake courier notice that must be blocked by the sender check (T8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import Circle

PASS = "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
FAIL = "mx.google.com; spf=fail; dkim=none; dmarc=fail"
JA_WEEKDAYS = "月火水木金土日"


@dataclass(frozen=True)
class Mail:
    id: str
    sender: str  # the From header
    auth: str  # the Authentication-Results header the receiving server added
    subject: str
    body: str
    received: str  # ISO time

    def text(self) -> str:
        return f"Subject: {self.subject}\n{self.body}"


def _round_up(t: datetime, minutes: int) -> datetime:
    extra = (-t.minute) % minutes
    return (t + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def _ja_day(d: datetime) -> str:
    return f"{d.month}月{d.day}日({JA_WEEKDAYS[d.weekday()]})"


def _en_time(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def demo_mailbox(circle: Circle, now: datetime | None = None) -> list[Mail]:
    """The caregiver's delivery mails for this circle, newest first."""
    now = (now or datetime.now(ZoneInfo(circle.parent.timezone))).astimezone(ZoneInfo(circle.parent.timezone))
    eta = _round_up(now + timedelta(minutes=25), 5)
    received = (now - timedelta(minutes=12)).isoformat(timespec="minutes")
    tomorrow, later = now + timedelta(days=1), now + timedelta(days=2)
    parent = circle.parent
    if parent.language == "ja":
        return [
            Mail("m_uber", "Uber Eats <noreply@uber.com>", PASS, "ご注文の商品をお届け中です",
                 f"お届け先：{parent.name} 様\nお店：やよい軒 仙台駅前店\nご注文：さば塩焼定食 1点\n"
                 f"お届け予定時刻：{eta:%H:%M}〜{eta + timedelta(minutes=10):%H:%M}\n配達パートナーが向かっています。", received),
            Mail("m_fake", "佐川急便 <info@sagawa-exp.co.jp>", FAIL, "【佐川急便】お荷物のお届けについて",
                 "お荷物をお届けに伺いましたが不在のため持ち帰りました。下記より再配達の手続きをお願いします。"
                 "http://sagawa-redelivery.top/jp", (now - timedelta(hours=2)).isoformat(timespec="minutes")),
            Mail("m_amazon", "Amazon.co.jp <shipment-tracking@amazon.co.jp>", PASS, "お客様の商品を発送しました",
                 f"お届け先：{parent.name} 様\n商品：トイレットペーパー 12ロール\nお届け予定：{_ja_day(tomorrow)} 19時〜21時",
                 (now - timedelta(hours=5)).isoformat(timespec="minutes")),
            Mail("m_yamato", "ヤマト運輸 <mail@kuronekoyamato.co.jp>", PASS, "お届け予定のお知らせ",
                 f"お届け先：{parent.name} 様\n品名：お米 5kg\nお届け予定日時：{_ja_day(later)} 14時〜16時",
                 (now - timedelta(hours=7)).isoformat(timespec="minutes")),
        ]
    slot = _round_up(now + timedelta(minutes=90), 30)
    return [
        Mail("m_uber", "Uber Eats <noreply@uber.com>", PASS, "Your order is on the way",
             f"Delivering to: {parent.name}\nGolden Bowl Noodles: chicken noodle soup (1)\n"
             f"Estimated arrival: {_en_time(eta)} - {_en_time(eta + timedelta(minutes=10))}\nYour courier is on the way.",
             received),
        Mail("m_fake", "USPS <alerts@usps-redelivery.top>", FAIL, "Your package is on hold",
             "We tried to deliver your package. Pay the $1.99 redelivery fee within 24 hours: http://usps-redelivery.top",
             (now - timedelta(hours=2)).isoformat(timespec="minutes")),
        Mail("m_instacart", "Instacart <orders@instacart.com>", PASS, "Your Safeway order is confirmed",
             f"Delivering to: {parent.name}\nGroceries: milk, bananas, oatmeal, eggs (12 items)\n"
             f"Delivery window: today, {_en_time(slot)} - {_en_time(slot + timedelta(hours=1))}",
             (now - timedelta(hours=3)).isoformat(timespec="minutes")),
        Mail("m_amazon", "Amazon.com <shipment-tracking@amazon.com>", PASS, "Your package has shipped",
             f"Delivering to: {parent.name}\nItem: paper towels, 6 rolls\nArriving {tomorrow:%A, %b} {tomorrow.day}, by 9 PM",
             (now - timedelta(hours=6)).isoformat(timespec="minutes")),
    ]
