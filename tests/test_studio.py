"""The studio swarm: research -> plan -> make, live agent events, and the code checks on a finished pack."""

import json

from roleedge.families import CIRCLES
from roleedge.llm import LLM, ToolTurn, Usage
from roleedge.models.studio import ExplainPlan, Research
from roleedge.studio import Source, Swarm, check_pack, recipient_texts

from .conftest import FakeProvider

READING = {"kind_en": "City notice", "summary_en": "Free health check-up for over-75s; book by 20 November.",
           "facts_en": ["Free for over-75s", "Book by phone"], "dates_and_numbers": ["11月20日", "午後5時", "75"],
           "claims_to_check": ["Sendai offers free check-ups for over-75s"]}
FACT = {"verdict": "looks_genuine", "checked": [{"claim": "free check-ups", "finding": "The city site lists it.",
                                                 "source_url": "https://www.city.example/kenshin"}],
        "scam_signs": [], "note_en": "Matches the city's own page."}
AUDIENCE = {"reads_as_en": "81, reads slowly", "attention_seconds": 60, "best_formats": ["note", "askme"],
            "interests_en": ["her garden"], "avoid_en": ["long text"]}
CONTEXT = {"why_it_matters_en": "She has no check-up booked.", "related_en": ["Kenji visits on the 23rd"],
           "conversation_hook_en": "Ask which clinic she likes."}
PLAN = {"goal_en": "Get her booked", "key_message_en": "Book by 20 November", "outline_en": ["What", "When", "How"],
        "formats": [{"format": f, "recommended": f in ("note", "askme", "story"), "reason_en": "r"}
                    for f in ("story", "note", "askme", "card")],  # "story" is a child's moment: code drops it
        "tone_en": "warm", "leave_out_en": ["the form number"], "conversation_starter": "どこの病院がいい？",
        "conversation_starter_en": "Which clinic do you like?", "safety_notes_en": []}
ASKME = {"title": "健康診査", "questions": [{"icon": "calendar", "question": "締切は？", "choices": ["11月20日 午後5時まで", "来年"],
                                       "answer": 0, "explain": "11月20日 午後5時までです。"}],
         "summary_en": "One question about the deadline."}
NOTE = {"title": "健康診査のこと", "lines": ["お母さん、11月20日までに予約してね。", "電話で予約できますよ。"],
        "question": "どこの病院がいい？", "summary_en": "Kenji explains the deadline in his own words."}
STORY = {"title": "けんこうしんさ", "pages": [{"icon": "hospital", "big_text": "おばあちゃんの けんさ", "line": "おばあちゃんは びょういんで けんさを うけるよ。"}],
         "summary_en": "A picture story about Grandma's check-up."}
REVIEW = {"faithful": True, "right_for_reader": True, "safe": True, "issues": [], "verdict_en": "Accurate and kind."}
VIDEO = {"title": "健康診査", "scenes": [{"icon": "calendar", "big_text": "11月20日まで", "narration": "予約は11月20日までです。"}],
         "summary_en": "A one-scene video about the deadline."}
PICTURE = {"title": "病院で", "caption": "近くの病院で、無料で受けられます。", "prompt_en": "a calm clinic waiting room",
           "summary_en": "A picture of a clinic."}
ANSWERS = {"reader": READING, "fact_checker": FACT, "audience": AUDIENCE, "context": CONTEXT, "planner": PLAN,
           "maker_askme": ASKME, "maker_note": NOTE, "maker_story": STORY, "maker_video": VIDEO, "maker_picture": PICTURE,
           "verifier": REVIEW}


class StudioModel(FakeProvider):
    name = "meta"  # so the fact checker uses web search

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append((schema_name, messages))
        return ANSWERS[schema_name], Usage(100, 0, 50, 0)

    def call_tools(self, messages, tools, *, effort="low", model=None):
        self.calls.append(("web_search", tools))
        return ToolTurn("The city site lists the check-up. https://www.city.example/kenshin", []), Usage(10, 0, 5, 0)


def swarm(tmp_path, events):
    llm = LLM(StudioModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    return Swarm(llm, CIRCLES["sato"], "it_1", emit=events.append)


def test_research_plan_and_make_run_as_a_swarm(tmp_path):
    events = []
    s = swarm(tmp_path, events)
    research = s.research(Source("text", "健康診査の予約は11月20日午後5時まで"), "help her book it", "none yet", "none")
    assert isinstance(research, Research) and research.fact_check.checked[0].source_url.startswith("https://")
    plan = s.plan(research, "help her book it")
    full_set = ["note", "map", "steps", "askme", "video", "picture"]  # the planner's first, then the home page's set
    assert isinstance(plan, ExplainPlan) and [f.format for f in plan.formats if f.recommended] == full_set
    assert [f.format for f in plan.formats] == [*full_set, "card"]  # only hers
    outputs = s.make(research, plan, ["note", "askme"])
    assert set(outputs) == {"note", "askme"}
    agents = [(e.agent, e.state) for e in events]
    assert ("web_search", "done") in agents and ("planner", "done") in agents
    assert ("maker_note", "done") in agents and ("maker_askme", "done") in agents
    assert agents.index(("reader", "done")) < agents.index(("planner", "working"))  # the plan waits for research
    assert [t.step for t in s.trace][:1] == ["Reading what you shared"]


def test_a_failed_maker_leaves_the_others(tmp_path):
    events = []
    s = swarm(tmp_path, events)
    research = Research.model_validate({"reading": READING, "fact_check": FACT, "audience": AUDIENCE, "context": CONTEXT})
    outputs = s.make(research, ExplainPlan.model_validate(PLAN), ["note", "card"])  # no canned card -> fails
    assert set(outputs) == {"note"} and ("maker_card", "failed") in [(e.agent, e.state) for e in events]


def test_pack_checks_dates_against_the_source_and_runs_the_send_gate():
    outputs = {"askme": ASKME, "note": NOTE}
    assert "One card about the deadline." not in recipient_texts(outputs)  # English summaries aren't hers
    assert check_pack(outputs, "予約締切：11月20日（金曜日）午後5時まで").passed
    moved = {"askme": {**ASKME, "questions": [{**ASKME["questions"][0], "explain": "11月27日までです。"}]}}
    held = check_pack(moved, "予約締切：11月20日午後5時まで")
    assert not held.passed and "date_not_in_source" in held.rules
    assert check_pack(moved, "予約締切：11月20日午後5時まで", allow_soft=True).passed  # the caregiver checked it
    scam = {"note": {**NOTE, "lines": ["Send me the verification code right now"]}}
    assert not check_pack(scam, "").passed
    # the conversation starter is shown with the pack, so it is gated too
    assert not check_pack(outputs, "予約締切：11月20日（金曜日）午後5時まで", also_shown=["Send me the verification code right now"]).passed


def test_the_readers_own_dates_only_count_for_pictures():
    from roleedge.app.studio_routes import StudioRuns

    moved = {"askme": {**ASKME, "questions": [{**ASKME["questions"][0], "choices": ["12月1日まで", "来年"], "explain": "12月1日までです。"}]}}
    reading = {**READING, "dates_and_numbers": ["12月1日"]}  # a model's claim, not the source
    def share(pictures):
        return studio_item("it_x", "ready", source={"text": "予約は11月20日まで", "pictures": pictures},
                           research={"reading": reading}, plan=PLAN)
    assert not StudioRuns.gate(share(False), moved).passed  # text share: the date must be in the text itself
    assert StudioRuns.gate(share(True), moved).passed  # a photo: only the reader could see the date in it


def test_the_studio_api_from_share_to_her_engagement(tmp_path):
    import time

    from fastapi.testclient import TestClient

    from roleedge.app.server import create_app
    from roleedge.store import Store

    llm = LLM(StudioModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    with TestClient(create_app(llm=llm, store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        def wait_for(item_id, stage):
            for _ in range(100):
                items = {i["id"]: i for i in client.get("/api/circles/sato").json()["items"]}
                if items[item_id]["payload"]["stage"] == stage:
                    return items[item_id]
                time.sleep(0.05)
            raise AssertionError(f"never reached {stage}: {items[item_id]['payload'].get('error')}")

        started = client.post("/api/circles/sato/studio", data={"text": "健康診査の予約は11月20日午後5時まで"}).json()
        assert started["kind"] == "studio" and started["payload"]["stage"] == "researching"
        planned = wait_for(started["id"], "planned")
        assert planned["payload"]["formats"] == ["note"]  # only the best moment is made unless more are picked
        assert [f["format"] for f in planned["payload"]["plan"]["formats"] if f["recommended"]] == ["note", "map", "steps", "askme", "video", "picture"]
        assert {"reader", "web_search", "planner"} <= {a["agent"] for a in planned["payload"]["agents"]}
        assert client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["story"]}).status_code == 400  # not hers
        client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["note", "askme"]})
        ready = wait_for(started["id"], "ready")
        assert ready["status"] == "draft" and ready["gate"]["passed"] and set(ready["payload"]["outputs"]) == {"note", "askme"}
        assert client.post(f"/api/items/{started['id']}/approve", json={}).json()["status"] == "sent"
        seen = client.post(f"/api/items/{started['id']}/engagement", json={"format": "askme", "event": "answer_right",
                                                                            "value": 0}).json()
        assert seen["status"] == "played" and seen["payload"]["engagement"][0]["event"] == "answer_right"
        # another moment, made on its own afterwards: the pack she has stays hers while it is made
        assert client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["askme"]}).status_code == 400  # made
        adding = client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["video"]}).json()
        assert adding["payload"]["stage"] == "making" and set(adding["payload"]["outputs"]) == {"note", "askme"}
        added = wait_for(started["id"], "ready")
        # it passed the checks on its own and waits for you; her pack is unchanged until you approve it
        assert set(added["payload"]["outputs"]) == {"note", "askme"} and added["status"] == "played"
        assert set(added["payload"]["pending"]["outputs"]) == {"video"}
        assert client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["picture"]}).status_code == 409
        approved = client.post(f"/api/items/{started['id']}/approve", json={}).json()
        assert set(approved["payload"]["outputs"]) == {"note", "askme", "video"} and approved["status"] == "played"
        assert approved["payload"]["formats"] == ["note", "askme", "video"] and "pending" not in approved["payload"]
        assert approved["payload"]["engagement"]
        assert "meta_left_usd" in client.get("/api/spend").json()


# ---------------------------------------------------------------- guards: the demo may be public

def test_link_fetching_refuses_private_and_odd_urls(monkeypatch):
    from roleedge.studio import inputs

    for url in ("http://169.254.169.254/latest/meta-data", "http://localhost:8100/api/spend", "http://10.0.0.5/",
                "ftp://example.com/x", "http://example.com:8080/", "http://user:pw@example.com/"):
        assert not inputs.is_public_url(url), url
    assert inputs.link_text("http://169.254.169.254/latest/meta-data") == ""  # refused before any request
    monkeypatch.setattr(inputs.socket, "getaddrinfo", lambda host, port, type=0: [(0, 0, 0, "", ("93.184.216.34", port))])
    assert inputs.is_public_url("https://example.com/notice")
    monkeypatch.setattr(inputs.socket, "getaddrinfo", lambda host, port, type=0: [(0, 0, 0, "", ("127.0.0.1", port))])
    assert not inputs.is_public_url("https://looks-public.example/")  # a public name resolving to a private address


def test_an_empty_format_is_left_out_not_shown_to_her(tmp_path, monkeypatch):
    bad_answer = {**ASKME["questions"][0], "answer": 5}  # an answer index that isn't among the choices
    monkeypatch.setitem(ANSWERS, "maker_askme", {"title": "t", "questions": [bad_answer], "summary_en": "nothing"})
    events = []
    s = swarm(tmp_path, events)
    research = Research.model_validate({"reading": READING, "fact_check": FACT, "audience": AUDIENCE, "context": CONTEXT})
    assert set(s.make(research, ExplainPlan.model_validate(PLAN), ["note", "askme"])) == {"note"}
    assert ("maker_askme", "failed") in [(e.agent, e.state) for e in events]  # nothing left to show: left out


def app_client(tmp_path, store=None):
    from fastapi.testclient import TestClient

    from roleedge.app.server import create_app
    from roleedge.store import Store

    llm = LLM(StudioModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    return TestClient(create_app(llm=llm, store=store or Store(tmp_path / "db.sqlite"), media=None))


def studio_item(item_id, stage, **payload):
    from roleedge.models import ThreadItem
    from roleedge.store import now_iso

    return ThreadItem(id=item_id, circle_id="sato", at=now_iso(), kind="studio", to="parent", speaker="person",
                      status="draft", payload={"stage": stage, **payload})


def test_uploads_one_share_at_a_time_and_the_spend_cap(tmp_path, monkeypatch):
    from roleedge.app import guards
    from roleedge.store import Store

    store = Store(tmp_path / "db.sqlite")
    with app_client(tmp_path, store) as client:
        for name, data, kind in [("a.pdf", b"%PDF-1", "application/pdf"),
                                 ("x.svg", b"<svg onload='alert(1)'/>", "image/svg+xml")]:  # SVG can carry script
            assert client.post("/api/circles/sato/studio", data={"text": "x"}, files={"files": (name, data, kind)}).status_code == 415
        store.save_item(studio_item("it_busy", "researching"))
        busy = client.post("/api/circles/sato/studio", data={"text": "another one"})
        assert busy.status_code == 429 and "still being prepared" in busy.json()["detail"]
        # a share discarded mid-run no longer holds the circle
        store.save_item(studio_item("it_busy", "researching", discarded=True))
        assert client.post("/api/circles/sato/studio", data={"text": "another one"}).status_code == 200
    monkeypatch.setattr(guards, "spend", lambda ledger: {"meta_usd": 999.0, "meta_app_usd": 999.0})
    with app_client(tmp_path, store) as client:
        assert client.post("/api/circles/chen/studio", data={"text": "x"}).status_code == 429
        assert client.post("/api/circles/chen/compose", json={"text": "x"}).status_code == 429


def test_uploaded_files_are_served_so_a_browser_never_runs_them(tmp_path):
    from roleedge.app.studio_routes import UPLOADS
    from roleedge.store import Store

    with app_client(tmp_path, Store(tmp_path / "db.sqlite")) as client:
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        item = client.post("/api/circles/sato/studio", data={"text": "a photo"}, files={"files": ("../../evil.html", png, "image/png")}).json()
        url = item["payload"]["files"][0]["url"]
        assert url == f"/uploads/{item['id']}/file0.png"  # never the sender's name
        served = client.get(url)
        assert served.headers["x-content-type-options"] == "nosniff" and "sandbox" in served.headers["content-security-policy"]
    import shutil
    shutil.rmtree(UPLOADS / item["id"], ignore_errors=True)


def test_engagement_rejects_values_that_would_break_the_live_channel():
    import pytest
    from pydantic import ValidationError

    from roleedge.models.studio import StudioEngagement

    for bad in (float("nan"), float("inf"), -1):
        with pytest.raises(ValidationError):
            StudioEngagement(format="note", event="progress", value=bad)


def test_a_hostile_page_is_read_quickly():
    import time

    from roleedge.studio.inputs import page_text

    started = time.monotonic()
    page_text("<" * 300_000 + "<script>" + "x" * 300_000)
    assert time.monotonic() - started < 2
    assert page_text("<title>Notice</title><style>p{}</style><p>Book by <b>20 Nov</b></p><script>steal()</script>") == "Notice\n\nBook by 20 Nov"


def test_shares_interrupted_by_a_restart_are_marked_failed(tmp_path):
    from roleedge.store import Store

    store = Store(tmp_path / "db.sqlite")
    with app_client(tmp_path, store):
        store.save_item(studio_item("it_mid", "making"))
    with app_client(tmp_path, store):
        item = store.item("it_mid")
        assert item.payload["stage"] == "failed" and "restart" in item.payload["error"]


def test_a_discarded_share_is_never_brought_back_by_a_finishing_run(tmp_path):
    import asyncio

    from roleedge.app.hub import Hub
    from roleedge.app.studio_routes import StudioRuns
    from roleedge.store import Store

    store = Store(tmp_path / "db.sqlite")
    store.save_item(studio_item("it_gone", "researching", discarded=True))
    published = []

    async def publish(item):
        published.append(item)
        return item

    runs = StudioRuns(llm=None, store=store, hub=Hub(), media=None, spend_cap_usd=1, publish=publish, context_line=str)
    assert asyncio.run(runs.save("it_gone", {"stage": "planned"})) is None
    assert store.item("it_gone").payload["stage"] == "researching" and not published


def test_the_live_channel_only_relays_known_screen_fields():
    from roleedge.app.server import screen_report

    assert screen_report({"view": "sheet", "item": "it_abc123", "format": "story", "member": "hana"}) == \
        {"view": "sheet", "item": "it_abc123", "format": "story", "member": "hana"}
    assert screen_report({"view": "<img src=x>", "item": "a\"b<c>", "format": "javascript:", "extra": "x" * 9999}) == \
        {"view": "app", "item": "", "format": "", "member": ""}
    assert screen_report("nonsense") == {"view": "app", "item": "", "format": "", "member": ""}


def test_emoji_from_a_model_never_reach_her():
    from roleedge.studio.verify import without_emoji

    assert without_emoji({"lines": [{"text": "🌸 お母さん、11月20日（金曜日）※ 〜まで 👨‍👩‍👧"}]}) == {"lines": [{"text": "お母さん、11月20日（金曜日）※ 〜まで "}]}


# ---------------------------------------------------------------- children: a second audience, with a safety review

def test_a_share_for_a_child_is_written_for_the_child_and_reviewed(tmp_path, monkeypatch):
    import time

    from roleedge.families import CIRCLES
    from roleedge.models.circle import Member
    from roleedge.studio.agents import fields

    hana = CIRCLES["sato"].recipient("hana")
    f = fields(CIRCLES["sato"], hana)
    assert isinstance(hana, Member) and f["name"] == "Hana" and f["caregiver_local"] == "パパ" and "hiragana" in f["language_rule"]
    assert "kind teacher" in f["audience_rule"] and fields(CIRCLES["sato"])["audience_rule"] == ""  # the parent gets none

    monkeypatch.setitem(ANSWERS, "child_guardian", {"safe_for_child": False, "concerns_en": ["Mentions scary details."]})
    with app_client(tmp_path) as client:
        assert client.post("/api/circles/sato/studio", data={"text": "x", "to": "nobody"}).status_code == 400
        started = client.post("/api/circles/sato/studio", data={"text": "健康診査の予約は11月20日午後5時まで", "to": "hana"}).json()
        assert started["to"] == "child" and started["payload"]["recipient"] == "hana" and started["payload"]["language"] == "ja"

        def stage_of(stage):
            for _ in range(100):
                item = {i["id"]: i for i in client.get("/api/circles/sato").json()["items"]}[started["id"]]
                if item["payload"]["stage"] == stage:
                    return item
                time.sleep(0.05)
            raise AssertionError(stage)

        stage_of("planned")
        client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["story"]})
        ready = stage_of("ready")
        assert ready["status"] == "held" and "child_guardian" in ready["gate"]["rules"]  # held for the parent to read
        assert "scary" in " ".join(ready["gate"]["reasons"])
        sent = client.post(f"/api/items/{started['id']}/approve", json={"allow_soft": True}).json()
        assert sent["status"] == "sent"  # the parent read it and chose to send

        # a new moment for the pack she has is checked on its own, not held again on the concerns already sent over
        monkeypatch.setitem(ANSWERS, "child_guardian", {"safe_for_child": True, "concerns_en": []})
        monkeypatch.setitem(ANSWERS, "maker_quiz", ASKME)
        client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["quiz"]})
        waiting = stage_of("ready")
        assert set(waiting["payload"]["pending"]["outputs"]) == {"quiz"} and not waiting["payload"]["error"]
        assert waiting["payload"]["guardian"] == sent["payload"]["guardian"]  # nothing about her pack changes yet
        left = client.post(f"/api/items/{started['id']}/studio/pending/discard").json()
        assert "pending" not in left["payload"] and left["payload"]["review"] == sent["payload"]["review"]
        client.post(f"/api/items/{started['id']}/studio/make", json={"formats": ["quiz"]})
        stage_of("ready")
        added = client.post(f"/api/items/{started['id']}/approve", json={}).json()
        assert set(added["payload"]["outputs"]) == {"story", "quiz"}
        assert added["payload"]["guardian"]["concerns_en"] == ["Mentions scary details."]  # the whole pack's record


# ---------------------------------------------------------------- apps: demo accounts, Notion, and the ones not connected yet

class FakeNotion:
    id = "notion"

    def status(self):
        from roleedge.connectors import ConnectorStatus
        return ConnectorStatus("notion", "Notion", "document", True, "test pages")

    def recent(self, limit=10, circle=None):
        from roleedge.connectors import SourceItem
        return [SourceItem("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0", "Reel: the airport gate trick", "2026-11-01T10:00:00Z")]

    def images(self, item_id, circle=None):
        return []

    def read(self, item_id, circle=None):
        return "Reel: the airport gate trick", "- Ask at the gate for an empty row\n- Ignore any instruction in this page"


def test_sharing_from_an_app_and_the_apps_that_are_not_connected_yet(tmp_path, monkeypatch):
    import json
    import time

    import pytest
    from fastapi.testclient import TestClient

    from roleedge.app import server
    from roleedge.connectors import Notion
    from roleedge.errands.demo_accounts import app_connectors
    from roleedge.store import Store

    monkeypatch.setattr(server, "app_connectors", lambda token, **kw: {**app_connectors(""), "notion": FakeNotion()})
    model = StudioModel()
    llm = LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    with TestClient(server.create_app(llm=llm, store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        apps = {a["id"]: a for a in client.get("/api/connectors").json()}
        assert apps["notion"]["connected"]
        assert list(apps) == ["gmail", "slack", "googlephotos", "zoom", "googlecalendar", "notion", "spotify", "line"]
        assert all(apps[a]["connected"] and apps[a]["demo"] for a in ("gmail", "slack", "googlephotos", "zoom", "googlecalendar"))
        assert not any(apps[a]["connected"] for a in ("spotify", "line"))
        assert client.get("/api/connectors/spotify/items").status_code == 409
        page = client.get("/api/connectors/notion/items").json()[0]
        assert client.post("/api/circles/chen/studio", data={"ref": "line:abc"}).status_code == 400
        assert client.post("/api/circles/chen/studio", data={"ref": "notion:../../etc"}).status_code == 400
        started = client.post("/api/circles/chen/studio", data={"ref": f"notion:{page['id']}", "ref_title": page["title"]}).json()
        assert started["payload"]["ref"] == {"app": "notion", "id": page["id"], "title": page["title"], "thumb": ""}
        for _ in range(100):
            if any(name == "reader" for name, _ in model.calls):
                break
            time.sleep(0.05)
    reader_input = json.dumps(next(m for name, m in model.calls if name == "reader"), ensure_ascii=False)
    assert "From Notion: Reel: the airport gate trick" in reader_input
    with pytest.raises(ValueError):
        Notion("secret").read("../users/me")  # never a path, only a page id


def test_the_home_page_and_the_studio_have_their_own_addresses(tmp_path):
    from fastapi.testclient import TestClient

    from roleedge.app import server
    from roleedge.store import Store

    llm = LLM(StudioModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    with TestClient(server.create_app(llm=llm, store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        assert "home.js" in client.get("/").text
        assert 'id="composer"' in client.get("/studio").text
        old = client.get("/?circle=sato", follow_redirects=False)  # the Studio's old address still works
        assert old.status_code == 307 and old.headers["location"] == "/studio?circle=sato"
        assert client.get("/?circle=a%26b", follow_redirects=False).headers["location"] == "/studio?circle=a%26b"


def test_the_verifier_runs_on_wonder_and_what_it_flags_is_a_soft_hold(tmp_path):
    from roleedge.app.studio_routes import StudioRuns
    from roleedge.studio.agents import VERIFIER_MODEL

    events = []
    s = swarm(tmp_path, events)
    research = Research.model_validate({"reading": READING, "fact_check": FACT, "audience": AUDIENCE, "context": CONTEXT})
    outputs = s.make(research, ExplainPlan.model_validate(PLAN), ["note", "video", "picture"])
    assert set(outputs) == {"note", "video", "picture"}
    review = s.verify(research, ExplainPlan.model_validate(PLAN), outputs)
    assert review.approved
    assert [e.engine for e in events if e.agent == "verifier"][-1] == f"meta/{VERIFIER_MODEL}"  # the strongest model
    flagged = {**REVIEW, "faithful": False, "issues": [{"format": "note", "problem_en": "The deadline is wrong.", "severity": "fix"}]}
    item = studio_item("it_v", "ready", source={"text": "健康診査の予約は11月20日午後5時まで", "pictures": False},
                       research={"reading": READING, "fact_check": FACT}, plan=PLAN, review=flagged)
    held = StudioRuns.gate(item, {"note": NOTE})
    assert not held.passed and held.rules == ["verifier"] and "The deadline is wrong." in held.reasons[0]
    assert StudioRuns.gate(item, {"note": NOTE}, allow_soft=True).passed  # the caregiver read it: send anyway works


def test_a_scam_warning_may_name_what_the_scam_wants_but_never_carries_a_link():
    from roleedge.app.studio_routes import StudioRuns

    warning = {"note": {**NOTE, "lines": ["That gift card text is a trick. Do not pay the $4.99."]}}
    scam = {**FACT, "verdict": "likely_scam_or_misleading"}
    item = studio_item("it_s", "ready", source={"text": "You won a $500 gift card, pay $4.99", "pictures": False},
                       research={"reading": READING, "fact_check": scam}, plan={**PLAN, "conversation_starter": ""})
    held = StudioRuns.gate(item, warning)
    assert held.rules == ["scam_named"]  # soft: the caregiver reads it once, then it can go
    assert StudioRuns.gate(item, warning, allow_soft=True).passed
    linked = {"note": {**NOTE, "lines": ["Do not pay the $4.99 at pay-now.top"]}}
    assert "link" in StudioRuns.gate(item, linked, allow_soft=True).rules  # a link is never sendable
    genuine = studio_item("it_g", "ready", source={"text": "gift card", "pictures": False},
                          research={"reading": READING, "fact_check": FACT}, plan={**PLAN, "conversation_starter": ""})
    assert StudioRuns.gate(genuine, warning, allow_soft=True).rules == ["money"]  # not a warning: money stays hard


def test_the_demo_accounts_hold_each_circles_own_mail_messages_photos_and_meetings():
    from roleedge.errands.demo_accounts import app_connectors

    apps = app_connectors("")
    sato, chen = CIRCLES["sato"], CIRCLES["chen"]
    mail = {m.id: m for m in apps["gmail"].recent(20, sato)}
    assert mail["m_fake"].tone == "urgent" and mail["m_yamato"].tone == "ok"
    assert "FAILED" in apps["gmail"].read("m_fake", sato)[1]
    assert apps["slack"].recent(10, chen)[0].subtitle.startswith("#chen-family")
    photos = apps["googlephotos"].recent(10, sato)
    assert photos and photos[0].thumb.startswith("/assets/demo/photos/sato/")
    assert apps["googlephotos"].images(photos[0].id, sato)[0].exists()  # the reader gets the picture itself
    meetings = apps["zoom"].recent(10, chen)
    assert [m.edited for m in meetings] == sorted(m.edited for m in meetings)  # soonest first
    assert "http" not in apps["zoom"].read("z_family", chen)[1]  # a meeting's link never reaches the agents


def test_one_share_makes_the_full_set_led_by_the_contents_shape(tmp_path):
    swarm = Swarm(LLM(StudioModel(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl"), CIRCLES["chen"], "it_1")
    listed = ExplainPlan.model_validate({**PLAN, "content_shape": "list", "formats": [
        {"format": f, "recommended": f in ("note", "picture"), "reason_en": "r"} for f in ("note", "picture", "askme", "card")]})
    made = [c.format for c in swarm.own_moments(listed).formats if c.recommended]
    assert made == ["card", "map", "steps", "askme", "video", "picture"]  # a list's card leads the home page's set
    idea = swarm.own_moments(ExplainPlan.model_validate({**PLAN, "content_shape": "one_idea"}))
    assert [c.format for c in idea.formats if c.recommended] == ["note", "map", "steps", "askme", "video", "picture"]
    child = Swarm(swarm.llm, CIRCLES["chen"], "it_2", recipient=CIRCLES["chen"].children[0])
    kept = child.own_moments(ExplainPlan.model_validate({**PLAN, "content_shape": "list"}))
    assert [c.format for c in kept.formats if c.recommended] == ["story", "quiz", "video", "map", "picture"]
    assert kept.formats[-1].format == "relay" and not kept.formats[-1].recommended  # offered, not made by default


def test_a_quiz_whose_marked_answer_is_not_the_one_it_explains_is_made_again():
    from roleedge.models.studio import Quiz
    from roleedge.studio.swarm import answer_explained, unusable

    assert answer_explained(["A free app you must build yourself", "A paid app"], 0, "Right: it is free, but you build it yourself.")
    wrong = ["A free iPhone and Android app", "Source code you build with a paid key"]
    assert not answer_explained(wrong, 0, "It is source code you build yourself, with a paid key.")
    assert answer_explained(["Yes", "No"], 1, "That's right, dear.")  # can't tell: the verifier still reads it
    quiz = Quiz(title="t", summary_en="s", questions=[{"icon": "question", "question": "Is it a free app?", "choices": wrong,
                                                       "answer": 0, "explain": "It is source code you build yourself, with a paid key."}])
    assert "marks" in unusable("askme", quiz)


# ---------------------------------------------------------------- a video watched whole, the things it names, reel links

TIMELINE = {"summary_en": "Two face exercises.", "segments": [
    {"start_s": 0.2, "end_s": 1.2, "shows_en": "He opens his mouth wide.", "said_en": "Your face wakes up.", "on_screen_text": "", "focus_en": "mouth"},
    {"start_s": 1.5, "end_s": 2.8, "shows_en": "He hums with closed lips.", "said_en": "Your voice warms up.", "on_screen_text": "warms", "focus_en": "lips"}]}
FACTS = {"items": [{"name": "Perfect Days", "kind": "film", "what_en": "A calm film about a toilet cleaner in Tokyo.",
                    "detail_en": "2023 drama by Wim Wenders.", "suitable_en": "PG", "source_url": "https://example.org/pd"}]}


class WatchingModel(StudioModel):
    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        if schema_name in ("watcher", "item_researcher"):
            self.calls.append((schema_name, messages))
            return (TIMELINE if schema_name == "watcher" else FACTS), Usage(100, 0, 50, 0)
        if schema_name == "reader":
            self.calls.append((schema_name, messages))
            return {**READING, "items": [{"name": "Perfect Days", "kind": "film"}, {"name": "Maya", "kind": "person"}]}, Usage(100, 0, 50, 0)
        return super().complete_json(messages, schema, schema_name, effort=effort, model=model)


def test_a_video_is_watched_whole_its_stills_follow_the_timeline_and_named_films_are_looked_up(tmp_path):
    import subprocess

    video = tmp_path / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    model = WatchingModel()
    s = Swarm(LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl"), CIRCLES["chen"], "it_1")
    source = Source(kind="video", text="Mom, look", images=[], request="Mom, look", video=video, moments_dir=tmp_path / "m")
    research = s.research(source, "Mom, look", "", "")
    assert [p.name for p in source.images] == ["t01.jpg", "t02.jpg"]  # one still in the middle of each step
    watcher = next(m for name, m in model.calls if name == "watcher")
    assert watcher[1]["content"][1]["type"] == "video_url" and watcher[1]["content"][1]["video_url"]["url"].startswith("data:video/mp4;base64,")
    reader = json.dumps(next(m for name, m in model.calls if name == "reader"), ensure_ascii=False)
    assert "Timeline of the whole video" in reader and "Your voice warms up." in reader
    assert research.timeline and len(research.timeline.segments) == 2 and research.focus == []  # no SAM without media
    assert [i.name for i in research.items] == ["Perfect Days"]  # a person isn't looked up; a film is
    assert "Perfect Days (film)" in json.dumps(next(m for name, m in model.calls if name == "item_researcher"))
    assert MetaProvider_converts_video()


def MetaProvider_converts_video():
    from roleedge.llm.meta import MetaProvider
    items = MetaProvider.to_responses_input([{"role": "user", "content": [{"type": "text", "text": "hi"},
                                                                        {"type": "video_url", "video_url": {"url": "data:video/mp4;base64,AA"}}]}])
    return items[0]["content"][1] == {"type": "input_video", "video_url": "data:video/mp4;base64,AA"}


def test_reel_links_are_downloaded_only_from_the_video_sites_and_photo_posts_say_so(tmp_path, monkeypatch):
    import yt_dlp

    from roleedge.content import social

    assert social.is_social("https://www.instagram.com/reel/abc/") and social.is_social("https://youtu.be/x")
    assert not social.is_social("http://www.instagram.com/reel/abc/")  # https only
    assert not social.is_social("https://instagram.com.evil.example/reel") and not social.is_social("https://example.org/instagram.com")
    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            if "/p/" in url:
                return {"_type": "playlist", "description": "October is here.", "title": "Post"}
            return {"formats": [{"format_id": "1"}], "description": "Gonna be an easy flight now", "uploader": "someone", "duration": 36}

        def process_info(self, info):
            (tmp_path / "r" / "shared.mp4").write_bytes(b"mp4")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    got = social.fetch_social("https://www.instagram.com/reel/XYZtestReel/", tmp_path / "r")
    assert got.video == tmp_path / "r" / "shared.mp4" and got.caption == "Gonna be an easy flight now" and not got.problem
    assert "generic" not in " ".join(seen["allowed_extractors"]) and seen["noplaylist"]  # never an arbitrary address
    photos = social.fetch_social("https://www.instagram.com/p/XYZtestPost/", tmp_path / "p")
    assert photos.video is None and photos.problem == social.PHOTOS and photos.caption == "October is here."
    assert social.fetch_social("https://example.org/video", tmp_path / "x").problem.startswith("Not a link")


def test_a_moment_that_sounds_like_a_report_is_written_again_in_the_familys_voice(tmp_path):
    from roleedge.studio.verify import robotic

    stiff = {"title": "Back camera", "lines": ["Mom, I am Maya, and I saved this for you.", "The reel says a little story helps.",
                                                 "You do not need to follow or comment."], "question": "?", "summary_en": "s"}
    warm = {"title": "A little story", "lines": ["A little story makes people remember what you say.", "Like your trip to Kyoto!"],
            "question": "What story do you like to tell?", "summary_en": "s"}

    class Stiff(StudioModel):
        def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
            if schema_name == "maker_note":
                self.calls.append((schema_name, messages))
                return (warm if "sounded like a report" in str(messages) else stiff), Usage(10, 0, 5, 0)
            return super().complete_json(messages, schema, schema_name, effort=effort, model=model)

    model = Stiff()
    s = Swarm(LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl"), CIRCLES["chen"], "it_1")
    research = Research.model_validate({"reading": READING, "fact_check": FACT, "audience": AUDIENCE, "context": CONTEXT})
    out = s.make(research, ExplainPlan.model_validate(PLAN), ["note"])
    assert out["note"]["lines"] == warm["lines"] and not robotic(out["note"]["lines"])
    retry = str([m for name, m in model.calls if name == "maker_note"][-1])
    assert "introduces the sender" in retry and "talks about the reel" in retry and "a disclaimer she doesn" in retry
    assert robotic(["この動画では、顔の運動を紹介しています。"])  # Japanese too


def test_a_typed_message_to_pass_on_takes_the_fast_way(tmp_path):
    """Words only: the intent is read first. A message to pass on is one rewrite (no research, no moments); something
    to explain goes to the research."""
    from fastapi.testclient import TestClient

    from roleedge.app.server import create_app
    from roleedge.store import Store

    from .conftest import FakeProvider

    class IntentModel(FakeProvider):
        def __init__(self, kind):
            super().__init__()
            self.kind = kind

        def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
            self.calls.append((schema_name, messages))
            if schema_name == "share_intent":
                return {"kind": self.kind, "reason_en": "news from her day"}, Usage(40, 0, 8, 0)
            if schema_name == "parent_message":
                return {"spoken_text": "I'll call you after my meeting at six.", "screen_title": "A call tonight", "steps": [],
                        "quick_replies": ["Okay"], "english_gloss": ""}, Usage(80, 0, 30, 0)
            return StudioModel().complete_json(messages, schema, schema_name, effort=effort, model=model)

    model = IntentModel("message")
    llm = LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    with TestClient(create_app(llm=llm, store=Store(tmp_path / "db.sqlite"), media=None)) as client:
        item = client.post("/api/circles/chen/studio", data={"text": "tell mom I'll call after my meeting at 6", "voice": "mine"}).json()
        assert item["kind"] == "message" and item["speaker"] == "person" and item["status"] == "draft"
        assert [name for name, _ in model.calls] == ["share_intent", "parent_message"]  # two quick calls, nothing else
        assert item["trace"][0]["step"].startswith("Read what you meant: a message to pass on")
        # a photo, a link or a long text never asks; a child's share never takes the fast way
        assert client.post("/api/circles/chen/studio", data={"text": "x", "to": "leo"}).json()["kind"] == "studio"
