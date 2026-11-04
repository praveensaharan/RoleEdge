"""The Reel Lab's code checks (no model, no network): quality bands, transcript agreement, Notion reading and the
Notion answer checks."""

from roleedge.connectors import Notion
from roleedge.lab.agents import Citation, NotionAnswer
from roleedge.lab.inventory import bands
from roleedge.lab.notion import check
from roleedge.lab.rounds import agreement


def test_quality_bands():
    good = {"width": 1080, "height": 1920, "fps": 30, "audio": True, "loudness_lufs": -14.0, "silence_share": 0.1,
            "blurry_share": 0.1, "frozen_share": 0.0, "brightness": 100}
    assert set(bands(good).values()) == {"pass"}
    poor = {**good, "width": 360, "height": 640, "fps": 12, "blurry_share": 0.9, "frozen_share": 0.8, "brightness": 20}
    b = bands(poor)
    assert (b["resolution"], b["frame_rate"], b["sharpness"], b["frozen"], b["brightness"]) == ("fail", "fail", "fail", "fail", "weak")
    assert bands({**good, "audio": False})["audio"] == "fail"


def test_transcript_agreement():
    assert agreement("If you do this, your face wakes up", "if you do this your face wakes up") == 1.0
    assert agreement("anything", "") is None
    assert agreement("one two three four", "five six seven eight") == 0.0
    assert agreement("इस आदमी को एक अजीब सा चश्मा मिलता है", "اس آدمی کو اچیب سچاشما ملتے ہیں") is None  # two scripts


class PagesApi(Notion):
    """A Notion page with a property, a toggle holding a paragraph, and a second page of blocks."""

    def __init__(self) -> None:
        super().__init__("secret")
        self.calls: list[str] = []

    def _call(self, method, path, body=None):
        self.calls.append(path)
        para = lambda text, **kw: {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": text}]}, **kw}  # noqa: E731
        if path.startswith("/pages/"):
            return {"properties": {"Name": {"type": "title", "title": [{"plain_text": "Linda's week"}]},
                                   "Category": {"type": "select", "select": {"name": "family"}},
                                   "Likes": {"type": "number", "number": None}}}
        if path.startswith("/blocks/t1/"):
            return {"results": [para("Eye drops: two drops at bedtime.")], "has_more": False}
        if "start_cursor=c2" in path:
            return {"results": [para("Walk 20 minutes after breakfast.")], "has_more": False}
        return {"results": [para("Doctor on Thursday at 10:30."),
                            {"id": "t1", "type": "toggle", "has_children": True, "toggle": {"rich_text": [{"plain_text": "Medicines"}]}}],
                "has_more": True, "next_cursor": "c2"}


def test_notion_reads_properties_toggles_and_every_page_of_blocks():
    api = PagesApi()
    title, text = api.read("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
    assert title == "Linda's week"
    assert text.splitlines() == ["Category: family", "Doctor on Thursday at 10:30.", "Medicines",
                                 "  Eye drops: two drops at bedtime.", "Walk 20 minutes after breakfast."]


def test_notion_answer_checks_catch_an_invented_quote():
    pages = {"p1": {"title": "[RoleEdge test] Kyoto trip", "text": "Train: Nozomi 225 from Tokyo at 09:03, car 7."}}
    scenario = {"found": True, "terms": ["Nozomi 225"], "pages": ["Kyoto trip"]}
    honest = NotionAnswer(found=True, answer_en="Take Nozomi 225.", missing_en=[],
                          citations=[Citation(page_id="p1", quote="Nozomi 225 from Tokyo at 09:03")])
    assert check(scenario, honest, pages)["passed"]
    invented = honest.model_copy(update={"citations": [Citation(page_id="p1", quote="Nozomi 225, seats 3A and 3B")]})
    result = check(scenario, invented, pages)
    assert not result["passed"] and result["ungrounded_quotes"] == ["Nozomi 225, seats 3A and 3B"]
    missing = {"found": False, "terms": [], "pages": []}
    assert check(missing, NotionAnswer(found=False, answer_en="It isn't in the pages.", citations=[], missing_en=["the password"]),
                 pages)["passed"]


def test_the_lab_page_shows_kinds_only_in_aggregate_and_uses_the_last_judged_round(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from roleedge.app import lab_routes
    from roleedge.lab.report import _by_kind, _latest_with

    moment = {"format": "note", "faithful": 4, "clear": 4, "engaging": 4, "useful": 4, "format_fit": 4, "natural": 4}
    reel = lambda kind: {"profile": {"content_type": kind}, "judgement_v4": {"moments": [moment]}}  # noqa: E731
    rows = {"a": reel("news"), "b": reel("news"), "c": reel("product"), "d": reel("recipe"), "e": reel("scam_or_warning")}
    kinds = _by_kind(rows, "judgement_v4")
    assert {k: v["reels"] for k, v in kinds.items()} == {"news": 2, "other": 3}  # no kind shows one reel's own score
    assert _by_kind({"a": reel("news")}, "judgement_v4") == {}  # "Other" with one reel is left out too
    by_round = {1: rows, 2: {"a": {"profile": {}}}}  # round 2 isn't judged on v4 yet
    assert _latest_with([1, 2], lambda n: by_round[n], "judgement_v4") is rows and _latest_with([], by_round.get, "x") == {}

    monkeypatch.setattr(lab_routes, "SUMMARY", tmp_path / "summary.json")  # the shipped data/lab/summary.json, replaced
    app = FastAPI()
    lab_routes.add_lab_routes(app, tmp_path)
    client = TestClient(app)
    assert client.get("/api/lab/summary").status_code == 404
    (tmp_path / "summary.json").write_text('{"reels": 44}')
    assert client.get("/api/lab/summary").json() == {"reels": 44}
    assert client.get("/api/lab").status_code == 404 and client.get("/lab-media/abcdef/f01.jpg").status_code == 404


def test_the_lab_results_ship_with_the_app():
    """/lab reads data/lab/summary.json, which is committed and goes into the image and the zip (output/ goes in
    neither). Without it a deployed /lab is empty, so the deploy's test step stops here."""
    import json

    from roleedge.config import LAB_SUMMARY

    s = json.loads(LAB_SUMMARY.read_text(encoding="utf-8"))
    assert s["usable"] and s["v4"] and s["kids_v2"] and s["robotic"] and s["change_log"] and s["spend"]
    assert len(s["change_log"]) == s["changes"]
