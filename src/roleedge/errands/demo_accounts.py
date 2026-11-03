"""Demo accounts for the apps a family already uses: Gmail, Slack, Google Photos, Zoom and Google Calendar.

Real accounts need each person's own sign-in (docs/PIVOT.md C2), and judges must be able to try the demo without
one. Until a sign-in is connected, these stand in for them with synthetic data for each circle, timed around "now",
and every screen labels them "demo account". They follow the same rules as a real connector: what they hold is data,
never instructions, and it goes through the same research, checks and approval as anything typed into the share box.

* **Gmail** is the caregiver's work inbox: the demo mailbox the errands already read (deliveries, and one fake courier
  notice that fails the sender check), a trip, a work mail that stays the caregiver's, a city notice and a school letter.
* **Slack** is the caregiver's workspace: family threads, a schedule message, and a work message that is the
  caregiver's to keep.
* **Google Photos** is this week's album: photos and photographed documents (a city notice, a school letter, a trip
  confirmation); each goes to the reader as a picture, not as text, so the reader reads the dates off the page itself.
* **Zoom** lists the circle's meetings; a meeting's link and passcode never reach the agents (the send gate would hold
  a link anyway), only what it is and when.
* **Google Calendar** holds the week: a trip, family events, a visit, and work blocks.

You can **add** to Gmail, Slack, Zoom and Google Calendar (``AddedItem``, stored per circle): a new mail, message,
meeting or event then shows in the app and the agents pick it up like anything else in it: a delivery mail answers
"when does my parcel come?", an event answers "when are you visiting?" (``schedule``, by the disclosure rules).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import APP_WEB_DIR
from ..connectors import Connector, ConnectorStatus, NotConnected, SourceItem, connectors
from ..gates import check_sender
from ..models import Circle
from ..models.errands import AddedItem
from .mailbox import FAIL, Mail, demo_mailbox

PHOTOS_DIR = APP_WEB_DIR / "demo" / "photos"  # synthetic photos (Muse Image), served at /assets/demo/photos
PASS = "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
ADDED = "add_"  # the id prefix of what you added yourself (the app shows it so, and lets you remove it)
Added = Callable[[Circle, str], list[AddedItem]]  # (circle, app id) -> what was added to that app


def nothing_added(circle: Circle, app: str) -> list[AddedItem]:
    return []


def _now(circle: Circle) -> datetime:
    return datetime.now(ZoneInfo(circle.parent.timezone))


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="minutes")


def _next(weekday: int, hour: int, minute: int, now: datetime) -> datetime:
    """The next ``weekday`` (Monday = 0) at hour:minute, from ``now``."""
    days = (weekday - now.weekday()) % 7
    t = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=7)


def _dated(month: int, day: int, hour: int, minute: int, now: datetime) -> datetime:
    """The date a demo document prints (a flyer, a ticket) while it is still ahead; afterwards the same weekday and
    time next week, so the demo week never ends up in the past."""
    t = now.replace(year=2026, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
    return t if t > now - timedelta(hours=12) else _next(t.weekday(), hour, minute, now)


class _Demo:
    id = ""
    label = ""
    icon = ""
    detail = ""

    def __init__(self, added: Added = nothing_added) -> None:
        self.added = added

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.id, self.label, self.icon, True, self.detail, demo=True)

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return []

    def _circle(self, circle: Circle | None) -> Circle:
        if circle is None:
            raise NotConnected(f"The {self.label} demo account needs a family circle.")
        return circle


# ---------------------------------------------------------------- Gmail


def _family_mail(circle: Circle, now: datetime) -> list[Mail]:
    """The rest of a working caregiver's inbox: a trip, a work mail, a city notice and a school letter (synthetic)."""
    if circle.parent.language == "ja":
        return [
            Mail("m_city", "仙台市 健康増進課 <kenshin@kenko-sendai.jp>", PASS, "【仙台市】75歳以上の方の健康診査のご案内",
                 "75歳以上の方は健康診査を無料で受けられます。予約締切：11月20日（金曜日）午後5時まで。"
                 "お近くの医療機関に電話で予約してください。持ち物：保険証、受診券。", _iso(now - timedelta(days=1, hours=2))),
            Mail("m_trip", "えきねっと JR東日本 <info@eki-net.com>", PASS, "【えきねっと】ご予約内容のお知らせ",
                 "11月14日（土）はやぶさ15号 東京 9:36発 → 仙台 11:07着 4号車 8A。帰り 11月15日（日）仙台 17:20発。",
                 _iso(now - timedelta(hours=9))),
            Mail("m_work", "Ryo Tanaka <ryo.tanaka@northwind.example>", PASS, "Re: Board review moved to Friday 14:00",
                 "Kenji, the board review is now Friday 14:00 in the 12F room. Please send your slides by Thursday noon.",
                 _iso(now - timedelta(hours=4))),
            Mail("m_school", "青葉小学校 <office@aoba-shogakko.jp>", PASS, "学芸会のお知らせ（2年生）",
                 "2年生の学芸会は11月13日（金）10時から体育館で行います。ご家族の方もどうぞお越しください。"
                 "上ばきをお持ちください。", _iso(now - timedelta(days=2, hours=4))),
        ]
    return [
        Mail("m_city", "LA County Public Health <notices@lacountyhealthnews.org>", PASS, "Free flu shots for adults 65+",
             "Free flu shots for adults 65 and over at the Pasadena Central Library, Saturday November 14, 10 AM to 2 PM. "
             "No appointment needed. Bring your Medicare card.", _iso(now - timedelta(days=1, hours=3))),
        Mail("m_trip", "Alaska Airlines <itinerary@alaskaair.com>", PASS, "Your trip to Seattle: Tue, Nov 10",
             "Confirmation ZX4K2Q. Departs LAX 7:05 AM, arrives SEA 9:52 AM. Return Wed, Nov 11, 6:40 PM.",
             _iso(now - timedelta(hours=8))),
        Mail("m_work", "Priya Shah <priya.shah@northwind.example>", PASS, "Re: Q4 design review moved to 3 PM",
             "Thanks Maya, I've moved the review to 3 PM. Can you bring the onboarding mocks? We'll run until about 4.",
             _iso(now - timedelta(hours=3))),
        Mail("m_school", "Lincoln Elementary <office@lincoln-elementary-pasadena.org>", PASS, "Science fair this Friday",
             "Our 4th grade science fair is Friday, November 13 from 6 to 7:30 PM in the gym. Families and grandparents "
             "are welcome.", _iso(now - timedelta(days=2, hours=5))),
    ]


def added_mails(items: list[AddedItem]) -> list[Mail]:
    """Mails you added: they pass the sender check unless you marked one as spoofed."""
    return [Mail(i.id, i.sender or "Unknown sender", PASS if i.verified else FAIL, i.title or "(no subject)", i.body, i.at)
            for i in items]


def _authenticated(mail: Mail) -> bool:
    """The receiving server's DMARC result (allow-listed or not: a city or school mail can be genuine too)."""
    return "dmarc=pass" in mail.auth.lower()


class DemoGmail(_Demo):
    id, label, icon = "gmail", "Gmail", "mail"
    detail = "Demo mailbox: synthetic mail until Google sign-in is connected"

    def _mails(self, circle: Circle) -> list[Mail]:
        now = _now(circle)
        mails = demo_mailbox(circle, now) + _family_mail(circle, now) + added_mails(self.added(circle, self.id))
        return sorted(mails, key=lambda m: m.received, reverse=True)

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        items = []
        for m in self._mails(self._circle(circle))[:limit]:
            name = m.sender.split("<")[0].strip()
            badge, tone = ("Sender verified", "ok") if _authenticated(m) else ("Failed sender check", "urgent")
            if m.id == "m_work":
                badge, tone = "Work", ""  # the caregiver's own; Mom only ever hears "in a meeting"
            items.append(SourceItem(m.id, m.subject, m.received, m.body.splitlines()[0][:120], subtitle=name,
                                    badge=badge, tone=tone))
        return items

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        mail = next((m for m in self._mails(self._circle(circle)) if m.id == item_id), None)
        if mail is None:
            raise ValueError("No such mail.")
        courier = check_sender(mail.sender, mail.auth)
        check = ("passed (SPF, DKIM and DMARC)" if _authenticated(mail) else
                 "FAILED: it claims to be from this sender but failed SPF, DKIM and DMARC, so it is likely fake")
        if courier.usable:
            check += "; a verified delivery company"
        got = datetime.fromisoformat(mail.received)
        return mail.subject, (f"From: {mail.sender}\nSender check: {check}\nReceived: {got:%A, %B} {got.day}, {got:%H:%M}\n\n"
                              f"{mail.body}")


# ---------------------------------------------------------------- Slack


@dataclass(frozen=True)
class _Post:
    id: str
    channel: str
    author: str
    text: str
    at: str


def _posts(circle: Circle) -> list[_Post]:
    now = _now(circle)
    if circle.parent.language == "ja":
        return [
            _Post("s_eye", "#sato-family", "Keiko (sister)",
                  "Mom's eye doctor moved to Thursday 10:30 at Aoba Eye Clinic. Can someone tell her? She should bring "
                  "her glasses and the medicine notebook.", _iso(now - timedelta(minutes=40))),
            _Post("s_play", "Yuki (DM)", "Yuki",
                  "Hana's school play is Friday at 10:00 in the gym, she's the rabbit! Mom said she'd love to come. The "
                  "city bus from her place stops right at the school gate.", _iso(now - timedelta(hours=3))),
            _Post("s_trip", "#sato-family", "Kenji",
                  "I'm in Osaka Wednesday and Thursday for work, back Thursday night. Visiting Mom on Saturday.",
                  _iso(now - timedelta(hours=20))),
            _Post("s_work", "#q4-planning", "Ryo (work)",
                  "Board review moved to Friday 14:00. Please send your slides by Thursday.", _iso(now - timedelta(days=1))),
        ]
    return [
        _Post("s_rx", "#chen-family", "Daniel (brother)",
              "Heads up: Mom's pharmacy switched her blood-pressure refills to home delivery starting November 12. "
              "She'll get a text from the pharmacy when it ships.", _iso(now - timedelta(minutes=55))),
        _Post("s_fair", "Mark (DM)", "Mark",
              "Leo's science fair is Friday 6 PM in the gym. Mom wants to come, I can pick her up at 5:30.",
              _iso(now - timedelta(hours=4))),
        _Post("s_trip", "#chen-family", "Maya",
              "I'm in Seattle Tuesday to Wednesday for work. Back Wednesday night, and I'll visit Mom Saturday.",
              _iso(now - timedelta(hours=22))),
        _Post("s_work", "#design-team", "Priya (work)", "Design review moved to Thursday 3 PM. Bring the Q4 mocks.",
              _iso(now - timedelta(days=1))),
    ]


class DemoSlack(_Demo):
    id, label, icon = "slack", "Slack", "chat"
    detail = "Demo workspace: synthetic messages until Slack sign-in is connected"

    def _posts(self, circle: Circle) -> list[_Post]:
        added = [_Post(i.id, i.where or f"#{circle.id}-family", i.sender or circle.caregiver.call_name, i.body, i.at)
                 for i in self.added(circle, self.id)]
        return sorted(_posts(circle) + added, key=lambda p: p.at, reverse=True)

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        return [SourceItem(p.id, p.text[:90] + ("…" if len(p.text) > 90 else ""), p.at, p.text, subtitle=f"{p.channel} · {p.author}",
                           badge="Work" if p.id == "s_work" else "", tone="")
                for p in self._posts(self._circle(circle))[:limit]]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        post = next((p for p in self._posts(self._circle(circle)) if p.id == item_id), None)
        if post is None:
            raise ValueError("No such message.")
        at = datetime.fromisoformat(post.at)
        return f"Slack message in {post.channel}", f"{post.author} wrote in {post.channel} on {at:%A} at {at:%H:%M}:\n{post.text}"


# ---------------------------------------------------------------- Google Photos


@dataclass(frozen=True)
class _Photo:
    id: str
    file: str
    title: str
    taken: str


PHOTOS: dict[str, list[tuple[str, str, str, int]]] = {  # circle -> (id, file, caption, days ago)
    "sato": [("p_notice", "notice.jpg", "Sendai city health check notice", 0), ("p_shrine", "shrine.jpg", "Shrine visit in autumn", 0),
             ("p_school", "school.jpg", "Hana's school play letter", 1), ("p_shinkansen", "shinkansen.jpg", "The shinkansen to Sendai", 2),
             ("p_office", "office.jpg", "Kenji's desk in Tokyo", 3), ("p_dinner", "dinner.jpg", "Dinner at Okaasan's", 5)],
    "chen": [("p_flyer", "flyer.jpg", "Leo's science fair flyer", 0), ("p_itinerary", "itinerary.jpg", "Seattle trip confirmation", 0),
             ("p_office", "office.jpg", "Maya's team room", 1), ("p_train", "train.jpg", "The train along the coast", 2),
             ("p_skyline", "skyline.jpg", "LA at golden hour", 3), ("p_garden", "garden.jpg", "Tomatoes from Mom's garden", 5)],
}


def _photos(circle: Circle) -> list[_Photo]:
    now = _now(circle)
    return [_Photo(pid, f"{circle.id}/{file}", title, _iso(now - timedelta(days=days, hours=2)))
            for pid, file, title, days in PHOTOS.get(circle.id, [])]


class DemoPhotos(_Demo):
    id, label, icon = "googlephotos", "Google Photos", "eye"
    detail = "Demo album: synthetic photos until Google sign-in is connected"

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        return [SourceItem(p.id, p.title, p.taken, "", subtitle="This week", thumb=f"/assets/demo/photos/{p.file}")
                for p in _photos(self._circle(circle))[:limit] if (PHOTOS_DIR / p.file).exists()]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        photo = self._photo(item_id, circle)
        taken = datetime.fromisoformat(photo.taken)
        who = self._circle(circle).caregiver.call_name
        return photo.title, (f"{who}'s own photo from his or her Google Photos album: \"{photo.title}\", taken on {taken:%A, %B} "
                             f"{taken.day}. {who} took it and chose to share it; it is not a link anyone sent. The picture itself "
                             "is attached: read what it shows (a photographed paper or document can be read as it is).")

    def images(self, item_id: str, circle: Circle | None = None) -> list[Path]:
        return [PHOTOS_DIR / self._photo(item_id, circle).file]

    def _photo(self, item_id: str, circle: Circle | None) -> _Photo:
        photo = next((p for p in _photos(self._circle(circle)) if p.id == item_id), None)
        if photo is None or not (PHOTOS_DIR / photo.file).exists():
            raise ValueError("No such photo.")
        return photo


# ---------------------------------------------------------------- Zoom


@dataclass(frozen=True)
class _Meeting:
    id: str
    topic: str
    start: datetime
    minutes: int
    host: str
    people: str
    private: bool = False


def _meetings(circle: Circle) -> list[_Meeting]:
    now = _now(circle)
    c, p = circle.caregiver.call_name, circle.parent.call_name
    kid = circle.children[0].call_name if circle.children else ""
    if circle.parent.language == "ja":
        return [
            _Meeting("z_family", "Sato family call", _next(6, 19, 0, now), 30, c, f"{c}, {p}, {kid}"),
            _Meeting("z_recital", f"{kid}'s piano recital (live stream)", _next(5, 14, 0, now), 45, "Yuki", f"{c}, {p}, Keiko"),
            _Meeting("z_clinic", "Aoba Eye Clinic: online check-in", _next(3, 10, 0, now), 15, "Aoba Eye Clinic", f"{p}, {c}"),
            _Meeting("z_work", "Q4 planning", _next(4, 14, 0, now), 60, "Ryo", "work team", private=True),
        ]
    return [
        _Meeting("z_family", "Chen family call", _next(6, 17, 0, now), 30, c, f"{c}, {p}, {kid}"),
        _Meeting("z_fair", f"{kid}'s science fair (live stream)", _dated(11, 13, 18, 0, now), 60, "Mark", f"{c}, {p}, Daniel"),
        _Meeting("z_plan", "Medicare plan review with Linda's advisor", _next(1, 11, 0, now), 30, "Westside Senior Center", f"{p}, {c}"),
        _Meeting("z_work", "Design review", _next(3, 15, 0, now), 60, "Priya", "design team", private=True),
    ]


class DemoZoom(_Demo):
    id, label, icon = "zoom", "Zoom", "video"
    detail = "Demo calendar: synthetic meetings until Zoom sign-in is connected"

    def meetings(self, circle: Circle) -> list[_Meeting]:
        added = [_Meeting(i.id, i.title or "Meeting", datetime.fromisoformat(i.at), i.minutes or 30, circle.caregiver.call_name,
                          i.where or circle.caregiver.call_name, private=i.kind == "work") for i in self.added(circle, self.id)]
        return sorted(_meetings(circle) + added, key=lambda m: m.start)

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        meetings = self.meetings(self._circle(circle))[:limit]
        return [SourceItem(m.id, m.topic, _iso(m.start), f"{m.minutes} min · with {m.people}",
                           subtitle=f"{m.start:%a %d %b · %H:%M}", badge="Work" if m.private else "", tone="")
                for m in meetings]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        circle = self._circle(circle)
        meeting = next((m for m in self.meetings(circle) if m.id == item_id), None)
        if meeting is None:
            raise ValueError("No such meeting.")
        when = f"{meeting.start:%A %d %B %Y, %H:%M} ({meeting.minutes} minutes)"
        return meeting.topic, (f"Zoom meeting: {meeting.topic}\nWhen: {when}\nHost: {meeting.host}\nWith: {meeting.people}\n"
                               f"(The meeting link and passcode stay with RoleEdge; they are not part of this item.)")


# ---------------------------------------------------------------- Google Calendar


@dataclass(frozen=True)
class Entry:
    """One thing in the caregiver's week, from the calendar or a Zoom meeting."""

    id: str
    title: str
    start: datetime
    minutes: int
    kind: str  # its disclosure category: family_events, travel, work, schedule, health
    where: str = ""
    source: str = "Google Calendar"

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


def _events(circle: Circle) -> list[Entry]:
    """The week in the caregiver's calendar (synthetic), on the same days as the mails, tickets and flyers."""
    now = _now(circle)
    soon = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    p = circle.parent.call_name
    kid = circle.children[0].call_name if circle.children else ""
    if circle.parent.language == "ja":
        return [
            Entry("c_osaka", "Osaka (work trip)", _next(2, 8, 0, now), 36 * 60 + 30, "travel", "Osaka"),
            Entry("c_focus", "Budget meeting", soon, 90, "work", "Tokyo office, 12F"),
            Entry("c_play", f"{kid}'s school play", _dated(11, 13, 10, 0, now), 90, "family_events", "Aoba Elementary gym"),
            Entry("c_visit", f"Shinkansen to Sendai to visit {p} (Hayabusa 15)", _dated(11, 14, 9, 36, now), 91, "travel",
                  "Tokyo Station to Sendai"),
            Entry("c_home", "Shinkansen home from Sendai", _dated(11, 15, 17, 20, now), 90, "travel", "Sendai Station"),
        ]
    return [
        Entry("c_focus", "1:1 with Priya", soon, 60, "work", "Northwind office, room 4B"),
        Entry("c_seattle", "Flight to Seattle (AS 1145)", _dated(11, 10, 7, 5, now), 167, "travel", "LAX to SEA"),
        Entry("c_return", "Flight home from Seattle", _dated(11, 11, 18, 40, now), 165, "travel", "SEA to LAX"),
        Entry("c_fair", f"{kid}'s science fair", _dated(11, 13, 18, 0, now), 90, "family_events", "Lincoln Elementary gym"),
        Entry("c_visit", f"Visit {p}", _dated(11, 14, 11, 0, now), 180, "family_events", f"{p}'s home"),
    ]


class DemoCalendar(_Demo):
    id, label, icon = "googlecalendar", "Google Calendar", "calendar"
    detail = "Demo calendar: synthetic events until Google sign-in is connected"

    def entries(self, circle: Circle) -> list[Entry]:
        added = [Entry(i.id, i.title or "Event", datetime.fromisoformat(i.at), i.minutes or 60, i.kind, i.where)
                 for i in self.added(circle, self.id)]
        return sorted(_events(circle) + added, key=lambda e: e.start)

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        return [SourceItem(e.id, e.title, _iso(e.start), f"{_span(e)}" + (f" · {e.where}" if e.where else ""),
                           subtitle=f"{e.start:%a %d %b · %H:%M}", badge="Work" if e.kind == "work" else "", tone="")
                for e in self.entries(self._circle(circle))[:limit]]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        entry = next((e for e in self.entries(self._circle(circle)) if e.id == item_id), None)
        if entry is None:
            raise ValueError("No such event.")
        return entry.title, (f"Calendar event: {entry.title}\nWhen: {entry.start:%A %d %B %Y, %H:%M} to {_end(entry)}\n"
                             + (f"Where: {entry.where}\n" if entry.where else ""))


def _span(e: Entry) -> str:
    return f"{e.minutes // 60} h {e.minutes % 60} min" if e.minutes >= 60 and e.minutes % 60 else \
        f"{e.minutes // 60} h" if e.minutes >= 60 else f"{e.minutes} min"


def _end(e: Entry) -> str:
    return f"{e.end:%H:%M}" if e.end.date() == e.start.date() else f"{e.end:%A %d %B, %H:%M}"


def schedule(circle: Circle, added: Added = nothing_added, days: int = 14) -> list[Entry]:
    """The caregiver's next ``days`` days from the calendar and Zoom, soonest first (what is under way included)."""
    now = _now(circle)
    zoom = [Entry(m.id, m.topic, m.start, m.minutes, "work" if m.private else "family_events", "Zoom", "Zoom")
            for m in DemoZoom(added).meetings(circle)]
    every = DemoCalendar(added).entries(circle) + zoom
    return sorted((e for e in every if e.end > now and e.start < now + timedelta(days=days)), key=lambda e: e.start)


# ---------------------------------------------------------------- Notion


@dataclass(frozen=True)
class _Page:
    id: str
    title: str
    text: str
    days_ago: int


def _pages(circle: Circle) -> list[_Page]:
    """The family's notes (synthetic): what a caregiver keeps for a parent. Questions she asks are answered from them."""
    p = circle.parent.call_name
    kid = circle.children[0].call_name if circle.children else ""
    if circle.parent.language == "ja":
        return [
            _Page("n_week", f"{p}の一週間", "眼科：木曜日 10:30、あおば眼科（2階）。めがねとお薬手帳を持っていく。\n"
                  "散歩：月曜と金曜の朝9時、近所の佐藤さんと公園まで20分。\nゴミの日：火曜と金曜の朝。", 1),
            _Page("n_recipe", f"{p}の肉じゃが", "4人分。じゃがいも3個、玉ねぎ1個、にんじん1本、牛肉200g。\n"
                  "1. 野菜を切る。\n2. 肉を炒めてから野菜を入れる。\n3. だし400mlと、しょうゆ・みりん大さじ3で20分煮る。", 3),
            _Page("n_school", f"{kid}の学校", f"学芸会：金曜日 10時から体育館。{kid}はうさぎの役。上ばきを持っていく。\n担任：山田先生。", 2),
            _Page("n_home", "家のメモ", "Wi-Fiのパスワード：sakura-2024\n水道の元栓：台所の流しの下。\n"
                  "電球の予備：玄関の棚の上の箱。", 6),
            _Page("n_visit", "仙台に行く日", "11月14日（土）はやぶさ15号で仙台へ、11:07着。駅からタクシーで実家まで。\n"
                  "15日（日）17:20発で東京に戻る。", 4),
        ]
    return [
        _Page("n_week", f"{p}'s week", "Doctor: Dr. Patel, Thursday at 10:30 AM, Huntington Family Medicine, 2nd floor. "
              "Bring the blue folder and her glasses.\nWalks: Mondays and Fridays at 9 AM with Carol, around the park, 20 minutes.\n"
              "Book club: first Tuesday of the month at the library, 2 PM.\nTrash night: Tuesday.", 1),
        _Page("n_recipe", f"{p}'s chicken soup", "Serves 4. 1 whole chicken, 2 carrots, 2 celery sticks, 1 onion, a bay leaf, "
              "salt.\n1. Cover the chicken with cold water and bring it to a simmer.\n2. Add the vegetables and the bay leaf.\n"
              "3. Simmer for 90 minutes, then season with salt.", 3),
        _Page("n_school", f"{kid}'s school", f"Science fair: Friday at 6 PM in the gym. {kid}'s project is a baking-soda volcano. "
              "His teacher is Ms. Rivera.", 2),
        _Page("n_home", "Home notes", "Wi-Fi password: sunflower-2024\nWater shut-off: under the kitchen sink.\n"
              "Spare light bulbs: the box on the hall shelf.", 6),
        _Page("n_trip", "Seattle trip", "Flight AS 1145 from LAX at 7:05 AM on Tuesday, back Wednesday at 6:40 PM. "
              "Hotel: Pike Street Inn. Maya visits Mom on Saturday after the trip.", 4),
    ]


class DemoNotion(_Demo):
    """The family's notes until a real Notion is connected: a few pages a caregiver keeps for a parent."""

    id, label, icon = "notion", "Notion", "document"
    detail = "Demo notes: synthetic pages until your Notion is connected"

    def recent(self, limit: int = 10, circle: Circle | None = None) -> list[SourceItem]:
        now = _now(self._circle(circle))
        return [SourceItem(pg.id, pg.title, _iso(now - timedelta(days=pg.days_ago, hours=3)), pg.text.splitlines()[0][:110])
                for pg in _pages(self._circle(circle))[:limit]]

    def read(self, item_id: str, circle: Circle | None = None) -> tuple[str, str]:
        page = next((pg for pg in _pages(self._circle(circle)) if pg.id == item_id), None)
        if page is None:
            raise ValueError("No such page.")
        return page.title, page.text


def app_connectors(notion_token: str = "", added: Added = nothing_added) -> dict[str, Connector]:
    """Every app the share box offers, in the order shown: the demo accounts first, then the others. Notion is the
    real one when a token is set, otherwise the demo notes."""
    demo: dict[str, Connector] = {c.id: c(added) for c in (DemoGmail, DemoSlack, DemoPhotos, DemoZoom, DemoCalendar)}
    others = connectors(notion_token)
    if not notion_token:
        others["notion"] = DemoNotion(added)
    return {**demo, **others}
