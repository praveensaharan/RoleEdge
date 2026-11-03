"""Phase 7: the Notion integration, tested for real.

1. ``inspect``: what the integration may see (counts only: no titles, no content of pages that aren't ours);
2. test pages: three pages of synthetic family notes, created in the reels database the integration already writes
   to (it has no plain page to create them under), clearly titled "[RoleEdge test]" and moved to the trash after;
3. scenarios: a fact, a summary, a question, two pages combined, an answer that isn't there, and three questions on
   the real reel pages whose answers we know from the source folder. Each has its expected answer written down
   before it runs, and is checked by code: the found flag, the expected terms, the pages cited, and every quote
   found word for word in the page it cites (a quote that isn't there is an invention).

The product's own Notion connector (``connectors.Notion``) does the listing and reading, so the test measures what
the Studio would really get. The token is read from the source folder's .env at run time and never printed.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from dotenv import dotenv_values

from ..config import LEDGER_FILE
from ..connectors import Notion
from ..families import CIRCLES
from ..llm import LLM
from ..llm.providers import pipeline_provider
from ..studio import Swarm
from . import LAB, SOURCE
from .agents import NOTION_ANSWER, NOTION_PICK, NotionAnswer, PagePick
from .budget import lab_rows
from .rounds import ledger_cost

DIR = LAB / "notion"
API = "https://api.notion.com/v1"
TEST_PREFIX = "[RoleEdge test]"


def _env() -> tuple[str, str]:
    env = dotenv_values(SOURCE / ".env")
    return (env.get("NOTION_TOKEN") or "").strip(), (env.get("NOTION_DB_ID") or "").strip()


def _raw(method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
    token, _ = _env()
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": Notion.VERSION}
    for attempt in range(4):
        res = httpx.request(method, f"{API}{path}", headers=headers, json=body, timeout=30)
        if res.status_code != 429:
            return res
        time.sleep(float(res.headers.get("Retry-After", 2)) * (attempt + 1))
    return res


def _id(value: str) -> str:
    return value.replace("-", "")


# ---------------------------------------------------------------- 1. inspect


def inspect() -> dict[str, Any]:
    token, db = _env()
    out: dict[str, Any] = {"token_present": bool(token), "database_id_present": bool(db)}
    if not token:
        return out
    me = _raw("GET", "/users/me")
    out["auth"] = me.status_code
    if me.status_code == 200:
        bot = me.json().get("bot") or {}
        out["bot_owner"] = (bot.get("owner") or {}).get("type", "")
    found, cursor = [], None
    while True:
        res = _raw("POST", "/search", {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}).json()
        found += res.get("results", [])
        cursor = res.get("next_cursor")
        if not res.get("has_more"):
            break
    pages = [x for x in found if x["object"] == "page"]
    out.update(pages=len(pages), databases=sum(x["object"] == "database" for x in found),
               pages_in_reels_db=sum(_id(x["parent"].get("database_id", "")) == _id(db) for x in pages),
               pages_elsewhere=sum(_id(x["parent"].get("database_id", "")) != _id(db) for x in pages),
               plain_pages=sum(x["parent"]["type"] in ("page_id", "workspace") for x in pages))
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "inspect.json").write_text(json.dumps(out, indent=1), encoding="utf-8")  # counts only
    return out


# ---------------------------------------------------------------- 2. test pages (synthetic)


def _text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def _block(kind: str, content: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"rich_text": _text(content)}
    if children:
        body["children"] = children
    return {"object": "block", "type": kind, kind: body}


TEST_PAGES: list[dict[str, Any]] = [
    {"title": f"{TEST_PREFIX} Linda's week", "blocks": [
        _block("paragraph", "Notes Sarah keeps for her mother Linda. Synthetic test data for RoleEdge."),
        _block("heading_2", "Doctor"),
        _block("bulleted_list_item", "Appointment with Dr. Sato on Thursday 6 November 2026 at 10:30, Aoba Clinic, 2nd floor."),
        _block("bulleted_list_item", "Bring the blue health notebook."),
        _block("heading_2", "Walks"),
        _block("bulleted_list_item", "20 minutes after breakfast, with Mrs. Tanaka on Mondays and Fridays."),
        _block("toggle", "Medicines (details)", [
            _block("paragraph", "Blood pressure tablet: one each morning with water."),
            _block("paragraph", "Eye drops: two drops at bedtime."),
        ]),
    ]},
    {"title": f"{TEST_PREFIX} Kyoto trip", "blocks": [
        _block("paragraph", "Family trip plan. Synthetic test data for RoleEdge."),
        _block("bulleted_list_item", "Dates: Saturday 15 November to Monday 17 November 2026."),
        _block("bulleted_list_item", "Train: Nozomi 225 from Tokyo at 09:03, car 7, seats 12A and 12B."),
        _block("bulleted_list_item", "Hotel: Hotel Kamogawa, check-in from 15:00. Booking number KM-4471."),
        _block("bulleted_list_item", "Maya joins us on Sunday afternoon."),
    ]},
    {"title": f"{TEST_PREFIX} Grandma's miso soup", "blocks": [
        _block("paragraph", "Serves 4. Synthetic test data for RoleEdge."),
        _block("heading_2", "Ingredients"),
        _block("bulleted_list_item", "800 ml dashi, 3 tablespoons white miso, 150 g silken tofu, 1 spring onion, a handful of wakame."),
        _block("heading_2", "Steps"),
        _block("numbered_list_item", "Warm the dashi; do not let it boil."),
        _block("numbered_list_item", "Add the tofu and wakame for 2 minutes."),
        _block("numbered_list_item", "Take it off the heat and stir in the miso through a small sieve."),
        _block("numbered_list_item", "Top with sliced spring onion."),
    ]},
]


def create_test_pages() -> list[dict[str, str]]:
    _, db = _env()
    made = []
    for page in TEST_PAGES:
        res = _raw("POST", "/pages", {"parent": {"database_id": db},
                                      "properties": {"Name": {"title": _text(page["title"])}},
                                      "children": page["blocks"]})
        made.append({"title": page["title"], "status": str(res.status_code),
                     "id": res.json().get("id", "") if res.status_code == 200 else "",
                     "error": "" if res.status_code == 200 else res.json().get("message", "")[:200]})
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "test-pages.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


def trash_test_pages() -> list[str]:
    """Move our test pages to the Notion trash (restorable there for 30 days)."""
    path = DIR / "test-pages.json"
    made = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    done = []
    for page in made:
        if page["id"]:
            res = _raw("PATCH", f"/pages/{page['id']}", {"archived": True})
            done.append(f"{page['title']}: {res.status_code}")
    return done


# ---------------------------------------------------------------- 3. scenarios

SCENARIOS: list[dict[str, Any]] = [
    {"id": "fact", "kind": "retrieve one fact", "question": "What time is Linda's appointment with Dr. Sato?",
     "found": True, "terms": ["10:30"], "pages": ["Linda's week"]},
    {"id": "summary", "kind": "summarise a page", "question": "Summarise the Kyoto trip page in a few short lines.",
     "found": True, "terms": ["15 November", "Nozomi 225", "Kamogawa", "Sunday"], "pages": ["Kyoto trip"]},
    {"id": "question", "kind": "answer a question", "question": "Which train do we take to Kyoto, and which seats?",
     "found": True, "terms": ["Nozomi 225", "12A", "12B"], "pages": ["Kyoto trip"]},
    {"id": "combine", "kind": "combine two pages",
     "question": "How many days after Linda's doctor appointment does the Kyoto trip start?",
     "found": True, "terms": ["9"], "pages": ["Linda's week", "Kyoto trip"]},
    {"id": "nested", "kind": "a fact inside a toggle", "question": "How often does Linda use her eye drops?",
     "found": True, "terms": ["bedtime"], "pages": ["Linda's week"]},
    {"id": "missing", "kind": "information that isn't there", "question": "What is the Wi-Fi password at the Kyoto hotel?",
     "found": False, "terms": [], "pages": []},
    {"id": "missing_return", "kind": "information that isn't there",
     "question": "What time is our train back from Kyoto on Monday?", "found": False, "terms": [], "pages": []},
    {"id": "real_tip", "kind": "a real reel page", "question": "In the airport reel, what did he ask the gate agent for, and what did he get?",
     "found": True, "terms": ["row"], "pages": ["Airport Hack"]},
    {"id": "real_list", "kind": "a real reel page", "question": "Which calming films were recommended for when life gets overwhelming?",
     "found": True, "terms": ["Perfect Days", "Tokyo Sonata", "Man Without A Past", "Museum Hours"], "pages": ["Calming Films"]},
    {"id": "real_caption", "kind": "a real reel page, only in its caption toggle",
     "question": "Which airline does the free cockpit tour reel thank?", "found": True, "terms": ["KLM"], "pages": ["Cockpit Tour"]},
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def corpus(connector: Notion, limit: int) -> dict[str, dict[str, str]]:
    """Every page the connector lists, read through the connector, minus pages of other people's databases."""
    _, db = _env()
    allowed = {_id(p["id"]) for p in _db_pages(db)}
    pages = {}
    for item in connector.recent(limit=limit):
        if _id(item.id) not in allowed:
            continue
        title, text = connector.read(item.id)
        pages[item.id] = {"title": title, "text": text}
    return pages


def _db_pages(db: str) -> list[dict[str, Any]]:
    found, cursor = [], None
    while True:
        res = _raw("POST", f"/databases/{db}/query", {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}).json()
        found += res.get("results", [])
        cursor = res.get("next_cursor")
        if not res.get("has_more"):
            return found


def check(scenario: dict[str, Any], answer: NotionAnswer, pages: dict[str, dict[str, str]]) -> dict[str, Any]:
    by_id = {_id(k): v for k, v in pages.items()}
    grounded = [bool(c.quote.strip()) and _id(c.page_id) in by_id and _norm(c.quote) in _norm(by_id[_id(c.page_id)]["text"])
                for c in answer.citations]
    cited_titles = [by_id[_id(c.page_id)]["title"] for c in answer.citations if _id(c.page_id) in by_id]
    said = _norm(answer.answer_en)
    checks = {
        "found_flag": answer.found == scenario["found"],
        "terms": all(_norm(t) in said for t in scenario["terms"]),
        "pages_cited": all(any(want.lower() in t.lower() for t in cited_titles) for want in scenario["pages"]),
        "quotes_grounded": all(grounded),
    }
    if not scenario["found"]:
        checks["nothing_invented"] = not answer.citations or all(grounded)
    return {"passed": all(checks.values()), "checks": checks, "ungrounded_quotes": [c.quote for c, ok in zip(answer.citations, grounded, strict=True) if not ok]}


def run_scenarios(n: int, limit: int = 100) -> dict[str, Any]:
    token, _ = _env()
    DIR.mkdir(parents=True, exist_ok=True)
    ledger = DIR / f"ledger-r{n}.jsonl"
    ledger.unlink(missing_ok=True)
    swarm = Swarm(LLM(pipeline_provider(), ledger_file=ledger), CIRCLES["chen"], f"lab-notion-r{n}")
    connector = Notion(token)
    started = time.time()
    pages = corpus(connector, limit)
    index = "\n".join(f"- id {pid} | {p['title']} | {p['text'][:300].replace(chr(10), ' ')}" for pid, p in pages.items())
    results = []
    for scenario in SCENARIOS:
        row: dict[str, Any] = {**scenario}
        try:
            pick: PagePick = swarm.run(NOTION_PICK, f"Question: {scenario['question']}\n\nPages:\n{index}")  # type: ignore[assignment]
            chosen = {pid: pages[pid] for pid in pages if _id(pid) in {_id(x) for x in pick.page_ids[:4]}}
            given = "\n\n".join(f"Page id {pid}\nTitle: {p['title']}\n{p['text']}" for pid, p in chosen.items()) or "(no pages)"
            answer: NotionAnswer = swarm.run(NOTION_ANSWER, f"Question: {scenario['question']}\n\n{given}")  # type: ignore[assignment]
            row.update(picked=[pages[p]["title"] for p in chosen], answer=answer.model_dump(), **check(scenario, answer, pages))
        except Exception as exc:
            row.update(passed=False, error=f"{type(exc).__name__}: {str(exc)[:200]}")
        results.append(row)
    out = {"round": n, "pages_seen": len(pages), "listed_limit": limit, "seconds": round(time.time() - started, 1),
           "passed": sum(r["passed"] for r in results), "total": len(results), "results": results, "cost": ledger_cost(ledger)}
    (DIR / f"round-{n}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if ledger.exists():  # the app's spend meter (and the lab's budget) counts these calls too
        with open(LEDGER_FILE, "a", encoding="utf-8") as fh:
            fh.write(lab_rows(ledger))
    return out
