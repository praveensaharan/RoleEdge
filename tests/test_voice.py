"""Your own voice on a message: the recording is made clearer by code, her captions come from what you said, and the
words she will hear go through the final send gate."""

import subprocess

from fastapi.testclient import TestClient

from roleedge.app import voice_routes
from roleedge.app.audio import clean_voice
from roleedge.app.server import create_app
from roleedge.app.voice_routes import words_heard
from roleedge.llm import LLM
from roleedge.llm.meta_media import Transcript
from roleedge.models import ThreadItem
from roleedge.store import Store, now_iso

from .conftest import FakeProvider

SAID = "Mom, the soup is ready. Do you want some tonight?"


def quiet_recording(path, seconds=4):
    """A quiet, distant-sounding voice stand-in: a tone that comes and goes, at about -40 dBFS, after a second of
    silence (what a laptop picks up across a room)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                    "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.002:duration=5",
                    "-filter_complex", "[0]volume=0.02,tremolo=f=3:d=0.9,adelay=1000[v];[v][1]amix=inputs=2:duration=first",
                    "-ac", "1", "-ar", "44100", str(path)], check=True)
    return path


class FakeMedia:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def transcribe(self, wav, languages=None, keywords=None):
        self.calls += 1
        assert wav[:4] == b"RIFF"
        return Transcript(text=self.text, duration_s=3.0, turns=[], latency_s=0.1)


def client_for(tmp_path, monkeypatch, heard):
    monkeypatch.setattr(voice_routes, "UPLOADS", tmp_path / "uploads")
    store = Store(tmp_path / "db.sqlite")
    llm = LLM(FakeProvider(), cache_dir=tmp_path / "c", ledger_file=tmp_path / "u.jsonl")
    media = FakeMedia(heard)
    client = TestClient(create_app(llm=llm, store=store, media=media))  # type: ignore[arg-type]
    item = ThreadItem(id="it_soup", circle_id="chen", at=now_iso(), kind="message", to="parent", speaker="assistant",
                      status="draft", voice="assistant",
                      payload={"source_text": "soup", "language": "en",
                               "message": {"spoken_text": SAID, "screen_title": "Soup", "steps": [], "quick_replies": [],
                                           "english_gloss": ""}})
    store.save_item(item)
    return client, store, media


def test_how_much_of_the_message_was_heard():
    assert words_heard(SAID, "mom the soup is ready, do you want some tonight") == 1.0
    assert words_heard(SAID, "Mom, soup's ready!") < 0.5
    assert words_heard("お母さん、カレーできたよ。", "お母さん カレーできたよ") == 1.0
    assert words_heard("", "anything") == 0.0


def test_a_quiet_recording_comes_out_at_speech_level(tmp_path):
    clear = clean_voice(quiet_recording(tmp_path / "quiet.wav"))
    assert clear.before_lufs < -30 and -20 <= clear.after_lufs <= -16
    assert clear.seconds < 4.5  # the second of silence before it is trimmed
    assert clear.data[4:8] == b"ftyp"  # an .m4a every browser plays


def test_she_hears_your_recording_with_your_words_as_captions(tmp_path, monkeypatch):
    client, store, media = client_for(tmp_path, monkeypatch, heard="Mom, the soup is ready. Do you want some tonight?")
    wav = quiet_recording(tmp_path / "me.wav").read_bytes()
    res = client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")})
    assert res.status_code == 200, res.text
    item = res.json()
    own = item["payload"]["own_voice"]
    assert item["speaker"] == "person" and item["voice"] == "mine" and media.calls == 1
    assert own["match"] == 1.0 and own["caption"] == SAID and -20 <= own["after_lufs"] <= -16
    assert (tmp_path / "uploads" / "it_soup" / "voice-1.m4a").exists()
    assert (tmp_path / "uploads" / "it_soup" / "voice-1-original.m4a").exists()
    assert any(t["engine"] == "code (ffmpeg)" for t in item["trace"])

    # a second take replaces the first; removing it goes back to the device voice
    item = client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")}).json()
    assert item["payload"]["own_voice"]["version"] == 2
    assert not (tmp_path / "uploads" / "it_soup" / "voice-1.m4a").exists()
    item = client.delete("/api/items/it_soup/own-voice").json()
    assert "own_voice" not in item["payload"] and not list((tmp_path / "uploads" / "it_soup").glob("voice-*"))


def test_said_your_way_her_captions_show_what_you_said(tmp_path, monkeypatch):
    client, _, _ = client_for(tmp_path, monkeypatch, heard="Hi Mom, I made soup, come have some.")
    wav = quiet_recording(tmp_path / "me.wav").read_bytes()
    own = client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")}).json()["payload"]["own_voice"]
    assert own["match"] < 0.85 and own["caption"] == "Hi Mom, I made soup, come have some."


def test_recorded_words_go_through_the_send_gate(tmp_path, monkeypatch):
    client, store, _ = client_for(tmp_path, monkeypatch, heard="Mom, read me the one-time code from your bank.")
    wav = quiet_recording(tmp_path / "me.wav").read_bytes()
    res = client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")})
    assert res.status_code == 422 and "code" in res.json()["detail"]
    assert "own_voice" not in store.item("it_soup").payload


def test_only_your_own_unheard_messages_take_a_recording(tmp_path, monkeypatch):
    client, store, _ = client_for(tmp_path, monkeypatch, heard=SAID)
    wav = quiet_recording(tmp_path / "me.wav").read_bytes()
    item = store.item("it_soup")
    item.status = "played"
    store.save_item(item)
    assert client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")}).status_code == 409
    item.status, item.kind = "draft", "reply"
    store.save_item(item)
    assert client.post("/api/items/it_soup/own-voice", files={"audio": ("me.wav", wav, "audio/wav")}).status_code == 400
