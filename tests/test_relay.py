"""The family relay: a grandchild asks their grandparent something and hears the answer, with the caregiver watching
over; what reaches each of them is checked first."""

import time

from fastapi.testclient import TestClient

from roleedge.app.server import create_app
from roleedge.llm import LLM, Usage
from roleedge.store import Store

from .conftest import FakeProvider

QUESTION = "おばあちゃん、子どものころ お祭りで なにを食べたの？"
ANSWER = "わたあめと、たこ焼きを食べたのよ。お祭りの夜は楽しかったわ。"
TO_GRANDMA = {"spoken_text": QUESTION, "english_gloss": "Grandma, what did you eat at festivals as a child?",
              "picture_en": "", "follow_up": ""}
TO_HANA = {"spoken_text": "おばあちゃんは、わたあめと たこやきを たべたんだって。", "picture_en": "cotton candy at a summer festival",
           "english_gloss": "I ate cotton candy and takoyaki. Festival nights were fun.",
           "follow_up": "おまつりで なにを して あそんだの？"}
SAFE = {"safe_for_child": True, "concerns_en": []}


class RelayModel(FakeProvider):
    """The relay writer answers by who is listening; the child guardian answers ``guardian``."""

    def __init__(self, to_hana=TO_HANA, guardian=SAFE, fail=None):
        super().__init__()
        self.to_hana, self.guardian, self.fail_writer = to_hana, guardian, fail

    def complete_json(self, messages, schema, schema_name, *, effort="low", model=None):
        self.calls.append((schema_name, messages))
        if schema_name == "child_guardian":
            return self.guardian, Usage(50, 0, 10, 0)
        if self.fail_writer:
            raise self.fail_writer
        return (self.to_hana if "retells" in messages[0]["content"] else TO_GRANDMA), Usage(80, 0, 40, 0)


def client_for(tmp_path, model):
    llm = LLM(model, cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    return TestClient(create_app(llm=llm, store=Store(tmp_path / "db.sqlite"), media=None))


def settled(client, item_id, limit=100):
    for _ in range(limit):
        item = {i["id"]: i for i in client.get("/api/circles/sato").json()["items"]}[item_id]
        if item["payload"]["stage"] == "ready":
            return item
        time.sleep(0.05)
    raise AssertionError("the relay never settled")


def relay(client, **form):
    return client.post("/api/circles/sato/relay", data=form)


def test_a_grandchild_asks_and_hears_her_grandmothers_answer(tmp_path):
    with client_for(tmp_path, RelayModel()) as client:
        asked = relay(client, **{"from": "hana", "text": QUESTION}).json()
        assert asked["kind"] == "relay" and asked["status"] == "draft" and asked["payload"]["stage"] == "writing"
        question = settled(client, asked["id"])
        assert question["status"] == "sent" and question["to"] == "parent" and question["payload"]["recipient"] == "yoshiko"
        assert question["payload"]["message"]["screen_title"] == "はなちゃんから"
        assert question["payload"]["message"]["english_gloss"].startswith("Grandma")  # Kenji reads it in English
        assert question["payload"]["guardian"] is None  # the child guard is for what reaches a child

        answered = relay(client, **{"from": "yoshiko", "text": ANSWER, "reply_to": asked["id"]}).json()
        answer = settled(client, answered["id"])
        assert answer["status"] == "sent" and answer["to"] == "child" and answer["payload"]["recipient"] == "hana"
        assert answer["payload"]["message"]["screen_title"] == "おばあちゃんから" and answer["payload"]["text"] == ANSWER
        assert answer["payload"]["guardian"]["safe_for_child"] and answer["payload"]["follow_up"]
        assert "picture" not in answer["payload"]  # pictures are only drawn next to the real Meta provider

        follow_up = relay(client, **{"from": "hana", "text": TO_HANA["follow_up"], "reply_to": answered["id"]})
        assert follow_up.status_code == 200  # and the conversation goes on


def test_a_relay_only_runs_between_a_grandchild_and_a_grandparent(tmp_path):
    with client_for(tmp_path, RelayModel()) as client:
        asked = relay(client, **{"from": "hana", "text": QUESTION}).json()
        assert relay(client, **{"from": "kenji", "text": "hi"}).status_code == 400  # the caregiver has their own channel
        assert relay(client, **{"from": "nobody", "text": "hi"}).status_code == 400
        assert relay(client, **{"from": "yoshiko", "text": "hi"}).status_code == 400  # to whom?
        assert relay(client, **{"from": "yoshiko", "text": "hi", "to": "yoshiko"}).status_code == 400
        assert relay(client, **{"from": "hana", "text": "hi", "reply_to": asked["id"]}).status_code == 400  # not hers to answer
        assert relay(client, **{"from": "hana", "text": "  "}).status_code == 400
        assert relay(client, **{"from": "yoshiko", "text": "hi", "to": "hana"}).status_code == 200  # she can start one too


def test_what_reaches_a_child_is_checked_and_held_for_the_parent(tmp_path):
    worried = {"safe_for_child": False, "concerns_en": ["Mentions a frightening accident."]}
    with client_for(tmp_path, RelayModel(guardian=worried)) as client:
        sent = relay(client, **{"from": "yoshiko", "text": ANSWER, "to": "hana"}).json()
        held = settled(client, sent["id"])
        assert held["status"] == "held" and "child_guardian" in held["gate"]["rules"]
        assert client.post(f"/api/items/{sent['id']}/approve", json={"allow_soft": False}).status_code == 422
        assert client.post(f"/api/items/{sent['id']}/approve", json={"allow_soft": True}).json()["status"] == "sent"

    linked = {**TO_HANA, "spoken_text": "おばあちゃんが ここを みてねって。http://festival-prize.top"}
    with client_for(tmp_path / "b", RelayModel(to_hana=linked)) as client:
        sent = relay(client, **{"from": "yoshiko", "text": ANSWER, "to": "hana"}).json()
        assert settled(client, sent["id"])["status"] == "held"
        assert client.post(f"/api/items/{sent['id']}/approve", json={"allow_soft": True}).status_code == 422  # never a link

    invented = {**TO_HANA, "spoken_text": "おばあちゃんは 7月20日に おまつりに いったんだって。"}
    with client_for(tmp_path / "c", RelayModel(to_hana=invented)) as client:
        sent = relay(client, **{"from": "yoshiko", "text": ANSWER, "to": "hana"}).json()
        assert "date_not_in_source" in settled(client, sent["id"])["gate"]["rules"]  # she never said a date


def test_if_the_writer_fails_words_pass_on_as_said_and_a_childs_wait_for_the_parent(tmp_path):
    with client_for(tmp_path, RelayModel(fail=RuntimeError("model down"))) as client:
        asked = settled(client, relay(client, **{"from": "hana", "text": QUESTION}).json()["id"])
        assert asked["status"] == "sent" and asked["payload"]["message"]["spoken_text"] == QUESTION
        answer = settled(client, relay(client, **{"from": "yoshiko", "text": ANSWER, "reply_to": asked["id"]}).json()["id"])
        assert answer["status"] == "held" and "child_guardian" in answer["gate"]["rules"]
