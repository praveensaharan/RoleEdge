from fastapi.testclient import TestClient

from roleedge.chat import create_app
from roleedge.chat.schemas import ChatRequest
from roleedge.llm import ProviderError

from .conftest import FakeProvider


def client(provider=None):
    return TestClient(create_app({"azure": provider or FakeProvider()}))


def chat_body(**overrides):
    body = {"provider": "azure", "model": "fake-1", "effort": "low", "messages": [{"role": "user", "text": "hi"}]}
    body.update(overrides)
    return body


def test_models_lists_every_known_provider():
    data = client().get("/api/models").json()
    by_id = {p["id"]: p for p in data["providers"]}
    assert list(by_id) == ["meta", "azure"]
    assert by_id["meta"]["models"] == []  # not configured
    assert by_id["azure"]["models"] == ["fake-1", "fake-2"]
    assert data["defaults"]["azure"] == "fake-1"


def test_chat_returns_text_and_usage():
    res = client().post("/api/chat", json=chat_body())
    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "hello"
    assert data["usage"] == {"input": 10, "cached": 4, "output": 3, "reasoning": 1}


def test_chat_validation_errors():
    c = client()
    assert c.post("/api/chat", json=chat_body(provider="meta")).status_code == 400  # not configured
    assert c.post("/api/chat", json=chat_body(effort="max")).status_code == 400
    last_is_assistant = chat_body(messages=[{"role": "assistant", "text": "hi"}])
    assert c.post("/api/chat", json=last_is_assistant).status_code == 400


def test_provider_errors_become_502():
    res = client(FakeProvider(fail=ProviderError("azure", "HTTP 404: model not found", 404))).post(
        "/api/chat", json=chat_body())
    assert res.status_code == 502 and "model not found" in res.json()["detail"]


def test_images_become_message_parts():
    req = ChatRequest.model_validate(chat_body(system="be kind", messages=[
        {"role": "user", "text": "", "images": ["data:image/png;base64,AA"]}]))
    system, user = req.to_messages()
    assert system == {"role": "system", "content": "be kind"}
    assert user["content"][0] == {"type": "text", "text": "(see image)"}
    assert user["content"][1]["image_url"]["url"].startswith("data:image/png")
