# Japan, loneliness and the demo story API: implementation plan (plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a Japanese family (a parent who lives alone and feels lonely) to the real pipeline, make the
content pipeline and renderer locale-aware, add loneliness to the check-in call, run it for real, and serve all
saved outputs to the web app as one JSON "story".

**Architecture:** Demo data gains a `FAMILIES` table, so CLI loops read families instead of one hard-coded
plan. Locale details (timezone, Japanese labels, fonts, Japanese date detection for rule S2) move from constants
into the recipient and i18n tables. The story builder lives in `chat/` (layer 4) because it reads `demo`
(layer 3); the chat server exposes it at `/api/demo/story` and serves `output/content` at `/media/content`.

**Tech stack:** Python 3.11+, pydantic 2, FastAPI, icalendar, pytest, ruff. Run everything with `.venv/bin/...`.

**Spec:** `docs/superpowers/specs/2026-10-28-product-demo-design.md` (plan 2 covers its Part 2, the web app).

## Global constraints

- Only synthetic data in the repo (rule S7). Names below are fictional.
- Layers (`tests/test_layers.py`): imports point strictly down; same-layer imports fail.
- The Indian digest prompt text must stay byte-identical (its cache must keep replaying for free).
- The folder is not a git repository: instead of committing, each task ends with the full test suite + ruff.
- After every task: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check src tests` both pass.

## Files

| File | Change |
|---|---|
| `src/carecircle/content/verify.py` | Japanese date and time mentions (S2) |
| `src/carecircle/models/people.py` | `Recipient.timezone` |
| `src/carecircle/content/prompts.py` | digest prompt uses `{timezone}` |
| `src/carecircle/render/calendar.py`, `render/package.py` | calendar uses the recipient's timezone |
| `src/carecircle/render/i18n.py`, `render/theme.py` | Japanese labels and dates; Noto Sans JP |
| `src/carecircle/checkin/prompts.py`, `models/checkin.py` | loneliness step, watch rule, `social_contact` |
| `src/carecircle/demo.py`, `data/samples/*_ja.txt` | Japanese family, `FAMILIES` |
| `src/carecircle/cli.py` | check-in loops over families |
| `src/carecircle/chat/story.py` (new), `chat/app.py`, `chat/__init__.py` | story builder and routes |
| `tests/conftest.py`, `tests/test_verify_policy.py`, `tests/test_render.py`, `tests/test_checkin_prompts.py`, `tests/test_demo.py` (new), `tests/test_story.py` (new) | tests |
| `ARCHITECTURE.md` | one line on loneliness and families |

---

### Task 1: Japanese dates are held too (rule S2)

**Files:** Modify `src/carecircle/content/verify.py` (the `date_mentions` section). Test: `tests/test_verify_policy.py`.

**Interfaces:** Produces `date_mentions(text: str) -> list[str]` (same signature, now also Japanese).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_verify_policy.py`)

```python
def test_japanese_dates_and_times_are_recognised():
    assert date_mentions("予約締切：11月20日（金曜日）午後5時まで") == date_mentions("予約は１１月２０日(金曜)午後５時までです")
    assert date_mentions("11月20日まで") != date_mentions("11月27日まで")
    assert date_mentions("明日の10時半") != date_mentions("明後日の10時半")
    assert set(date_mentions("期間：2026年11月4日〜12月11日")) == {"2026年11月4日", "12月11日"}


def test_a_japanese_fix_that_moves_a_date_is_held_and_rewording_is_applied():
    d = doc()
    d["regional"]["article"] = "予約締切は11月20日です。"
    d["voice_note_script"] = "予約締切は11月20日です。"
    reviewed = apply_fixes(d, [issue("regional.article", "予約締切は11月27日です。"),
                               issue("voice_note_script", "予約のしめきりは11月20日です。")])
    assert [(r.needs_review, r.applied) for r in reviewed] == [(True, False), (False, True)]
    assert d["regional"]["article"] == "予約締切は11月20日です。"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_verify_policy.py -k japanese`
Expected: FAIL (Japanese dates return `[]`, so the date move is applied).

- [ ] **Step 3: Implement** in `src/carecircle/content/verify.py`

Add after `_CODE = ...`:

```python
_JA_WORDS = re.compile("明後日|一昨日|今日|明日|昨日|今夜|今晩|[月火水木金土日]曜日?")
_JA_CODE = {"今日": "R0", "明日": "R1", "昨日": "R1", "明後日": "R2", "一昨日": "R2", "今夜": "P4", "今晩": "P4"}


def _ja_code(word: str) -> str:
    return _JA_CODE.get(word) or f"D{'月火水木金土日'.index(word[0]) + 1}"  # 月曜 -> D1 ... 日曜 -> D7
```

Add these alternatives at the top of `_MENTION` (before the `M\d+` line):

```text
    (?<!\d)\d{1,4}年(?:\d{1,2}月)?(?:\d{1,2}日)?                       # 2026年11月20日
  | (?<!\d)\d{1,2}月(?:\d{1,2}日)?                                    # 11月20日, 11月
  | (?<!\d)\d{1,2}日                                                   # 20日
  | (?:午前|午後)?(?<!\d)\d{1,2}時(?:\d{1,2}分|半)?                    # 午後5時, 10時30分, 10時半
  |
```

In `date_mentions`, change NFD to NFKD and map the Japanese words before the Latin/Devanagari words:

```python
    text = unicodedata.normalize("NFKD", text).translate(_NORMALISE).lower()  # nukta split; full-width -> ASCII
    text = re.sub(r"\b([ap])\.\s?m\b\.?", r"\1m", text)
    text = _JA_WORDS.sub(lambda m: f" {_ja_code(m.group())} ", text)
    text = re.sub(_LETTERS, lambda m: f" {_CODE[m.group()]} " if m.group() in _CODE else m.group(), text)
```

Update the section comment to: `# Words are mapped to one code per meaning, so "Nov" and "नवम्बर" (or "Friday", "शुक्रवार" and "金曜日") compare equal.`

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest -q tests/test_verify_policy.py`
Expected: all pass (the Hindi/English tests too).

- [ ] **Step 5: Full suite + ruff** (see global constraints).

---

### Task 2: Recipients carry a timezone; renderer speaks Japanese

**Files:** Modify `src/carecircle/models/people.py`, `src/carecircle/content/prompts.py:10`,
`src/carecircle/render/calendar.py`, `src/carecircle/render/package.py:37`, `src/carecircle/render/i18n.py`,
`src/carecircle/render/theme.py:23-25`, `src/carecircle/demo.py` (RECIPIENTS), `tests/conftest.py` (recipient
fixtures). Test: `tests/test_render.py`.

**Interfaces:** Produces `Recipient.timezone: str`; `build_calendar(digest, uid_prefix, held=frozenset(), *,
timezone: str) -> bytes | None`; Japanese entries in `trust_badge`, `sent_by`, `format_day`, `deadline_phrase`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_render.py`; reuse its imports, adding
  `from carecircle.content.prompts import DIGEST_SYSTEM`, `from carecircle.demo import RECIPIENTS, TODAY`,
  `from carecircle.render.i18n import deadline_phrase, sent_by, trust_badge` if not imported)

```python
def test_japanese_labels_and_dates():
    assert deadline_phrase("2026-11-20", "Japanese") == "11月20日まで"
    assert trust_badge("likely_scam_or_misleading", "Japanese") == "⚠ 詐欺かもしれません"
    assert sent_by("Kenji", "Japanese") == "Kenjiから · Saathiがやさしく説明"


def test_calendar_uses_the_recipients_timezone(digest):
    assert "TZID=Asia/Tokyo" in build_calendar(digest, "x", timezone="Asia/Tokyo").decode()


def test_digest_prompt_for_the_demo_family_is_unchanged():
    assert "today is 2026-10-28 (Asia/Kolkata)." in DIGEST_SYSTEM.format(today=TODAY, **RECIPIENTS["mummy"].model_dump())
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest -q tests/test_render.py`
Expected: FAIL (`timezone` is an unexpected keyword; Japanese falls back to English).

- [ ] **Step 3: Implement**

`models/people.py`, after `script`:

```python
    timezone: str  # IANA name, e.g. "Asia/Kolkata"; dates in prompts and calendars use it
```

`content/prompts.py`: `Dates: today is {today} (Asia/Kolkata).` → `Dates: today is {today} ({timezone}).`

`render/calendar.py`: delete `TIMEZONE = ZoneInfo("Asia/Kolkata")`; change

```python
def build_calendar(digest: Digest, uid_prefix: str, held: set[int] = frozenset(), *, timezone: str) -> bytes | None:
    """The .ics bytes, or None when there is nothing to put in a calendar. Times are in ``timezone``."""
    ...
        cal.add_component(_event(action, f"{uid_prefix}-{index}@carecircle.example", ZoneInfo(timezone)))


def _event(action: Action, uid: str, tz: ZoneInfo) -> Event:
    ...
        start = datetime.combine(day, datetime.strptime(action.due_time, "%H:%M").time(), tzinfo=tz)
```

`render/package.py`: `ics = build_calendar(digest, uid_prefix=record.case, held=held, timezone=recipient.timezone)`.
Existing `build_calendar(...)` calls in `tests/test_render.py` get `timezone="Asia/Kolkata"`.

`render/i18n.py`:

```python
TRUST_BADGES: dict[str, dict[TrustVerdict, str]] = {
    ...existing Hindi and English...,
    "Japanese": {"looks_genuine": "✓ 信頼できそうです", "unverified": "? 未確認です — 一度確かめましょう",
                 "likely_scam_or_misleading": "⚠ 詐欺かもしれません"},
}

SENT_BY = {"Hindi": "{sender} ने भेजा · Saathi ने आसान बनाया", "English": "Sent by {sender} · made simple by Saathi",
           "Japanese": "{sender}から · Saathiがやさしく説明"}
DEADLINE = {"Hindi": "{day} तक", "English": "by {day}", "Japanese": "{day}まで"}


def format_day(iso_date: str, language: str) -> str:
    d = date.fromisoformat(iso_date)
    lang = _lang(language)
    if lang == "Hindi":
        return f"{d.day} {HINDI_MONTHS[d.month - 1]}"
    if lang == "Japanese":
        return f"{d.month}月{d.day}日"
    return d.strftime("%-d %B")


def deadline_phrase(iso_date: str, language: str) -> str:
    """'30 नवंबर तक' in Hindi (postposition), '11月30日まで' in Japanese, 'by 30 November' in English."""
    return DEADLINE[_lang(language)].format(day=format_day(iso_date, language))
```

`render/theme.py`: add `"&family=Noto+Sans+JP:wght@400;700;800"` to `FONT_LINK` (before `&display=block`) and
`'Noto Sans JP'` to `FONT_STACK` after `'Noto Sans Devanagari'`; comment: `# Indic and Japanese scripts need Noto fonts; without them they render as empty boxes.`

`demo.py` RECIPIENTS: `timezone="Asia/Kolkata"` for `mummy` and `aarav`. `tests/conftest.py`: the same for
`hindi_recipient` and `english_recipient`.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest -q tests/test_render.py` → PASS.

- [ ] **Step 5: Full suite + ruff.**

---

### Task 3: Loneliness in the check-in call

**Files:** Modify `src/carecircle/checkin/prompts.py`, `src/carecircle/models/checkin.py` (`CallReport`),
`ARCHITECTURE.md` §4. Test: `tests/test_checkin_prompts.py`.

**Interfaces:** Produces `CallReport.social_contact: str`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_checkin_prompts.py`; import
  `from carecircle.checkin.prompts import AGENT_SYSTEM, REPORT_SYSTEM, prompt_fields` and
  `from carecircle.models.checkin import CallReport`)

```python
def test_the_call_asks_about_loneliness_and_flags_it_as_watch():
    text = AGENT_SYSTEM.format(care_plan_json="{}", **prompt_fields(OTHER_FAMILY))
    assert "talked with anyone or gone out" in text
    assert 'have not spoken with anyone for days, call flag_concern with severity "watch"' in text
    assert "social_contact" in REPORT_SYSTEM.format(**prompt_fields(OTHER_FAMILY))
    assert "social_contact" in CallReport.model_fields
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/bin/python -m pytest -q tests/test_checkin_prompts.py -k loneliness` → FAIL.

- [ ] **Step 3: Implement**

In `AGENT_SYSTEM`, replace steps 6–7 with:

```text
6. Ask whether they have talked with anyone or gone out in the last few days. If they sound lonely, chat warmly \
for a moment about something they enjoy, and offer to set up a call with {caregiver}.
7. Mention at most one upcoming item.
8. Close warmly. Call record_checkin once with everything learned, then end_call.
```

Add as the third safety rule (after the missed-medicine rule):

```text
- Loneliness matters: if they say they feel lonely, or have not spoken with anyone for days, call flag_concern \
with severity "watch".
```

In `REPORT_SYSTEM`, before `caregiver_actions are ...`, add `"social_contact says who they have talked to "
"recently and any signs of loneliness. "`.

In `CallReport`, after `food: str`: `social_contact: str`.

In `ARCHITECTURE.md` §4 check-in step 1, append: ` Saathi asks about medicines, meals, pain and whether they have
talked with anyone; loneliness is a "watch" concern, so the call turns amber.`

- [ ] **Step 4: Run the tests** → PASS. **Step 5: Full suite + ruff.**

---

### Task 4: The Japanese family and `FAMILIES`

**Files:** Modify `src/carecircle/demo.py`, `src/carecircle/cli.py` (`cmd_checkin`). Create
`data/samples/line_scam_ja.txt`, `data/samples/city_notice_ja.txt`, `tests/test_demo.py`.

**Interfaces:** Produces `demo.Family(id, label, care_plan, recipients: tuple[str, ...], calls: dict[str, str])`,
`demo.FAMILIES: dict[str, Family]`, `demo.JAPAN_CARE_PLAN`, recipient key `"okaasan"`, content cases
`"line_scam"` and `"city_notice"`, call scenario `"lonely_day"`.

- [ ] **Step 1: Write the failing tests** (`tests/test_demo.py`)

```python
from carecircle.demo import CONTENT_CASES, FAMILIES, RECIPIENTS


def test_every_recipient_belongs_to_exactly_one_family():
    owners = {key: [f.id for f in FAMILIES.values() if key in f.recipients] for key in RECIPIENTS}
    assert all(len(found) == 1 for found in owners.values()), owners
    assert {case.recipient for case in CONTENT_CASES} <= set(RECIPIENTS)


def test_call_scenario_names_are_unique():
    names = [name for family in FAMILIES.values() for name in family.calls]
    assert len(names) == len(set(names))


def test_the_japanese_family_is_set_up_for_japan():
    japan = FAMILIES["japan"]
    assert japan.care_plan.emergency_number == "119" and japan.care_plan.parent.language == "Japanese"
    assert all(RECIPIENTS[key].timezone == "Asia/Tokyo" for key in japan.recipients)
    assert "lonely_day" in japan.calls


def test_japanese_text_samples_load():
    texts = {case.id: case.build().text for case in CONTENT_CASES if case.id in ("line_scam", "city_notice")}
    assert set(texts) == {"line_scam", "city_notice"}
    assert "ATM" in texts["line_scam"] and "11月20日" in texts["city_notice"]
```

- [ ] **Step 2: Run them to see them fail** → ImportError (`FAMILIES`).

- [ ] **Step 3: Implement**

`data/samples/line_scam_ja.txt` (synthetic):

```text
【LINE】知らないアカウント「ゆうた」からのメッセージ（転送）
おばあちゃん、ぼくだよ、ゆうただよ。スマホをなくしたから新しいアカウントになった。
会社のお金が入ったカバンを電車に忘れて、今日中に50万円必要なんだ。お父さんには絶対に言わないで。
今すぐ近くのATMに行って、今から送る口座に振り込んでくれる？急いで！
```

`data/samples/city_notice_ja.txt` (synthetic):

```text
仙台市からのお知らせ（転送）
75歳以上の方へ：無料の健康診査のご案内
対象：仙台市にお住まいの75歳以上の方
期間：2026年11月4日（水曜日）〜12月11日（金曜日）
予約締切：11月20日（金曜日）午後5時まで
予約方法：お近くの指定医療機関に電話で予約してください。
持ち物：保険証、受診券（同封）
費用：無料
問い合わせ：仙台市健康福祉局 022-XXX-XXXX
```

`demo.py`: add to `RECIPIENTS`:

```python
    "okaasan": Recipient(
        call_name="お母さん", full_name="Yoshiko Sato", role="parent", age=81, language="Japanese",
        script="kanji and kana", timezone="Asia/Tokyo",
        reading="an 81-year-old who lives alone; reads slowly, prefers large text, short polite sentences and voice",
        sender="Kenji (her son)"),
```

Add to `CONTENT_CASES`:

```python
    ContentCase("line_scam", "okaasan", "Forwarded LINE message from someone posing as a grandson", lambda: ContentItem(
        text="Shared item: a forwarded LINE message.\n\n" + _text("line_scam_ja.txt"))),
    ContentCase("city_notice", "okaasan", "City notice about a free health check-up", lambda: ContentItem(
        text="Shared item: a forwarded city notice.\n\n" + _text("city_notice_ja.txt"))),
```

After `CALL_SCENARIOS`, add:

```python
JAPAN_CARE_PLAN = CarePlan.model_validate({
    "parent": {"call_name": "お母さん", "full_name": "Yoshiko Sato", "age": 81, "language": "Japanese",
               "script": "kanji and kana", "lives": "alone in Sendai; son in Tokyo; few visitors"},
    "caregiver": {"name": "Kenji", "relation": "son", "status_now": "at work in Tokyo until 7 pm"},
    "conditions": ["high blood pressure", "mild knee arthritis"],
    "medicines": [{"name": "Amlodipine 5 mg", "when": "morning after breakfast"}],
    "diet": "low salt",
    "upcoming": ["Free health check-up: book by 20 Nov", "Kenji visits on 23 Nov"],
    "food_ordering": "allowed, needs Kenji's approval, from saved shops only (Sendai Bento Kitchen, local supermarket)",
    "emergency": "119; Kenji 090-XXXX-XXX1; neighbour Mrs Suzuki next door",
    "emergency_number": "119",
    "call_time": "10:00 am",
})

JAPAN_CALL_SCENARIOS: dict[str, str] = {
    "lonely_day": "You live alone. Apart from the TV you have not spoken to anyone for three days, and you feel "
                  "lonely and a bit low, but you don't want to be a burden on Kenji, so at first you say you are "
                  "fine. You only had tea for breakfast because cooking for one feels pointless. You took the "
                  "morning Amlodipine. No pain; you slept badly. You brighten up if asked about your garden or old songs.",
}


@dataclass(frozen=True)
class Family:
    id: str
    label: str
    care_plan: CarePlan
    recipients: tuple[str, ...]  # keys into RECIPIENTS
    calls: dict[str, str]  # call scenario name -> hidden situation for the simulated parent


FAMILIES: dict[str, Family] = {
    "india": Family("india", "India", CARE_PLAN, ("mummy", "aarav"), CALL_SCENARIOS),
    "japan": Family("japan", "Japan", JAPAN_CARE_PLAN, ("okaasan",), JAPAN_CALL_SCENARIOS),
}
```

`cli.py` `cmd_checkin`:

```python
def cmd_checkin(args: argparse.Namespace) -> int:
    from . import checkin
    from .demo import FAMILIES

    llm = _pipeline_llm()
    for family in FAMILIES.values():
        for name, scenario in family.calls.items():
            if args.scenarios and name not in args.scenarios:
                continue
            record = checkin.run_call(llm, family.care_plan, name, scenario)
            checkin.save(record)
            print(checkin.summary_line(record))
    return 0
```

- [ ] **Step 4: Run the tests** → PASS. **Step 5: Full suite + ruff.**

---

### Task 5: Run the real pipeline (paid, a few cents)

**Files:** none (writes `output/`). Back up `output/` to the scratchpad first.

- [ ] **Step 1:** `.venv/bin/carecircle content pension_reel scam_reel electricity_bill school_notice`
  Expected: every line ends `replay=True`, and the ledger's last 8 lines all have `replayed_from_cache: true`
  (no paid calls: the Indian prompts did not change).
- [ ] **Step 2:** `.venv/bin/carecircle content line_scam city_notice` (2 digest + 2 checker calls).
  Check: `line_scam` verdict `likely_scam_or_misleading`; `city_notice` has an action dated `2026-11-20`;
  recipient-facing text is Japanese.
- [ ] **Step 3:** `.venv/bin/carecircle render` → Japanese `card.png` shows Japanese text (open it), and
  `city_notice/event.ics` has `Asia/Tokyo` or an all-day date.
- [ ] **Step 4:** `.venv/bin/carecircle checkin` (3 calls). Check: `lonely_day` has a `flag_concern` with
  severity `watch` and status `amber`; every report has `social_contact`; Indian statuses are recorded.
- [ ] **Step 5:** `.venv/bin/carecircle costs` and `.venv/bin/carecircle mock` (no model calls) so derived
  outputs match. Report the measured cost of the new calls.

---

### Task 6: The story builder and its routes

**Files:** Create `src/carecircle/chat/story.py`, `tests/test_story.py`. Modify `src/carecircle/chat/app.py`.

**Interfaces:**
- Consumes: `demo.FAMILIES`, `demo.RECIPIENTS`, `demo.CONTENT_CASES`, `content.load`, `content.CONTENT_DIR`,
  `checkin.CHECKIN_DIR`.
- Produces: `story.build(content_dir: Path = CONTENT_DIR, checkin_dir: Path = CHECKIN_DIR) -> dict[str, Any]`
  with the shape in the spec §1.5; `create_app(providers=None, content_dir=CONTENT_DIR, checkin_dir=CHECKIN_DIR)`;
  routes `GET /api/demo/story`, static `/media/content/<case>/<file>`.

- [ ] **Step 1: Write the failing tests** (`tests/test_story.py`)

```python
from fastapi.testclient import TestClient

from carecircle import checkin, content
from carecircle.chat import create_app
from carecircle.chat.story import build
from carecircle.checkin import CallRecord
from carecircle.models import DigestRecord

from .conftest import FakeProvider, make_digest


def save_fixture(tmp_path):
    content_dir, checkin_dir = tmp_path / "content", tmp_path / "checkin"
    digest = make_digest()
    content.save(DigestRecord(case="electricity_bill", recipient="mummy", input="Photo of a bill", media_count=1,
                              digest=digest, draft_before_verify=digest, verify_issues=[], usage={}, latency_s=1.0,
                              cached=True, verify_usage={}, verify_latency_s=1.0), content_dir)
    (content_dir / "electricity_bill" / "card.png").write_bytes(b"png")
    checkin.save(CallRecord(scenario="normal_day", ended_cleanly=True, transcript=[("Mummy", "हेलो?")], events=[],
                            report={"status": "green", "headline": "fine"}, metrics={}), checkin_dir)
    return content_dir, checkin_dir


def test_story_has_both_families_and_lists_what_is_missing(tmp_path):
    story = build(*save_fixture(tmp_path))
    india, japan = story["families"]
    assert (india["id"], japan["id"]) == ("india", "japan")
    assert india["caregiver"]["name"] == "Rohit" and japan["parent"]["language"] == "Japanese"
    item = india["items"][0]
    assert item["case"] == "electricity_bill" and item["media"]["card"] == "/media/content/electricity_bill/card.png"
    assert "video" not in item["media"]  # only files that exist
    assert india["calls"][0]["status"] == "green"
    assert "content/pension_reel" in india["missing"] and "checkin/lonely_day" in japan["missing"]


def test_story_route_and_media(tmp_path):
    content_dir, checkin_dir = save_fixture(tmp_path)
    client = TestClient(create_app({"azure": FakeProvider()}, content_dir=content_dir, checkin_dir=checkin_dir))
    assert client.get("/api/demo/story").json()["families"][0]["id"] == "india"
    assert client.get("/media/content/electricity_bill/card.png").content == b"png"
```

- [ ] **Step 2: Run them to see them fail** → ImportError (`carecircle.chat.story`).

- [ ] **Step 3: Implement** `src/carecircle/chat/story.py`

```python
"""Everything the demo web app plays, gathered from saved outputs into one JSON document.

The web app never calls a model: it replays what `carecircle content`, `render` and `checkin` saved.
Missing outputs are listed under "missing" instead of failing, so the page works after a partial run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..checkin import CHECKIN_DIR
from ..content import CONTENT_DIR, load
from ..demo import CONTENT_CASES, FAMILIES, RECIPIENTS

MEDIA = {"card": "card.png", "video": "explainer.mp4", "calendar": "event.ics"}


def build(content_dir: Path = CONTENT_DIR, checkin_dir: Path = CHECKIN_DIR) -> dict[str, Any]:
    families = []
    for family in FAMILIES.values():
        plan, items, calls, missing = family.care_plan, [], [], []
        for case in (c for c in CONTENT_CASES if c.recipient in family.recipients):
            if (content_dir / case.id / "digest.json").exists():
                items.append(_item(load(case.id, content_dir), content_dir))
            else:
                missing.append(f"content/{case.id}")
        for name in family.calls:
            path = checkin_dir / f"{name}.json"
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
                calls.append({"scenario": name, "status": record["report"]["status"], "transcript": record["transcript"],
                              "events": record["events"], "report": record["report"]})
            else:
                missing.append(f"checkin/{name}")
        families.append({
            "id": family.id, "label": family.label,
            "caregiver": {"name": plan.caregiver.name, "relation": plan.caregiver.relation},
            "parent": {"call_name": plan.parent.call_name, "full_name": plan.parent.full_name,
                       "language": plan.parent.language},
            "recipients": [{"key": key, "call_name": RECIPIENTS[key].call_name, "role": RECIPIENTS[key].role,
                            "language": RECIPIENTS[key].language} for key in family.recipients],
            "items": items, "calls": calls, "missing": missing,
        })
    return {"families": families}


def _item(record: Any, content_dir: Path) -> dict[str, Any]:
    folder = content_dir / record.case
    media = {key: f"/media/content/{record.case}/{name}" for key, name in MEDIA.items() if (folder / name).exists()}
    return {
        "case": record.case, "input": record.input, "recipient": record.recipient, "scam": record.digest.is_scam,
        "digest": record.digest.model_dump(mode="json"), "held_actions": sorted(record.held_action_indexes),
        "held_fields": [issue.path for issue in record.verify_issues if issue.needs_review],
        "voice_note": record.digest.voice_note_script, "media": media,
    }
```

`chat/app.py`: import `from pathlib import Path`, `from ..checkin import CHECKIN_DIR`,
`from ..content import CONTENT_DIR`, `from . import story`; change the signature to
`def create_app(providers: dict[str, Provider] | None = None, content_dir: Path = CONTENT_DIR, checkin_dir: Path = CHECKIN_DIR) -> FastAPI:`
and add before the `/static` mount:

```python
    @app.get("/api/demo/story")
    def demo_story() -> dict:
        return story.build(content_dir, checkin_dir)

    app.mount("/media/content", StaticFiles(directory=content_dir, check_dir=False), name="media")
```

- [ ] **Step 4: Run the tests** → PASS (including `tests/test_layers.py`: `chat` is layer 4, everything it imports
  is lower).
- [ ] **Step 5: Full suite + ruff**, then `curl -s localhost:8000/api/demo/story | head -c 400` against
  `.venv/bin/carecircle chat` to see real data.
