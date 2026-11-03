from fastapi.testclient import TestClient

from roleedge import checkin, content
from roleedge.chat import create_app
from roleedge.chat.story import build
from roleedge.checkin import CallRecord
from roleedge.models import DigestRecord

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


def test_demo_page_and_assets_are_served(tmp_path):
    content_dir, checkin_dir = save_fixture(tmp_path)
    client = TestClient(create_app({"azure": FakeProvider()}, content_dir=content_dir, checkin_dir=checkin_dir))
    page = client.get("/demo")
    assert page.status_code == 200 and 'id="stage"' in page.text
    assert client.get("/demo-static/js/main.js").status_code == 200


def test_story_carries_measured_costs_and_the_icon_set_is_served(tmp_path):
    content_dir, checkin_dir = save_fixture(tmp_path)
    (tmp_path / "costs.json").write_text('{"avg_llm_cost_per_content_item_usd": 0.0073, '
                                         '"avg_llm_cost_per_checkin_logic_usd": 0.0131}')
    assert build(content_dir, checkin_dir)["metrics"] == {"cost_per_item_usd": 0.0073, "cost_per_call_usd": 0.0131}
    client = TestClient(create_app({"azure": FakeProvider()}, content_dir=content_dir, checkin_dir=checkin_dir))
    icons = client.get("/api/demo/icons").json()
    assert "calendar" in icons and icons["calendar"].startswith("<rect")


def test_story_without_costs_has_no_metrics(tmp_path):
    assert build(*save_fixture(tmp_path))["metrics"] is None
