import json

import pytest

from roleedge.config import AzureConfig, ConfigError, MetaConfig, Settings
from roleedge.llm import LLM, ProviderError, Usage, configured_providers, pipeline_provider
from roleedge.llm.azure import AzureProvider
from roleedge.llm.meta import MetaProvider
from roleedge.models import ParentReply

from .conftest import FakeProvider


def test_cache_replays_second_call_and_writes_ledger(tmp_path):
    provider = FakeProvider(json_answer={"reply": "हाँ"})
    llm = LLM(provider, cache_dir=tmp_path / "cache", ledger_file=tmp_path / "usage.jsonl")
    messages = [{"role": "user", "content": "hi"}]
    first = llm.complete_json("t/x", messages, ParentReply, "reply")
    second = llm.complete_json("t/x", messages, ParentReply, "reply")
    assert (first.cached, second.cached) == (False, True)
    assert second.data == {"reply": "हाँ"} and second.usage == Usage(100, 0, 50, 10)
    assert len(provider.calls) == 1  # the replay did not call the provider
    lines = [json.loads(line) for line in (tmp_path / "usage.jsonl").read_text().splitlines()]
    assert [line["replayed_from_cache"] for line in lines] == [False, True]


def test_cache_key_changes_with_messages(tmp_path):
    provider = FakeProvider(json_answer={"reply": "x"})
    llm = LLM(provider, cache_dir=tmp_path, ledger_file=tmp_path / "u.jsonl")
    llm.complete_json("t", [{"role": "user", "content": "a"}], ParentReply, "reply")
    llm.complete_json("t", [{"role": "user", "content": "b"}], ParentReply, "reply")
    assert len(provider.calls) == 2


def test_meta_converts_chat_messages_to_responses_input():
    items = MetaProvider.to_responses_input([
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": [{"type": "text", "text": "what is this?"},
                                     {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}]},
    ])
    assert items[0] == {"role": "system", "content": "be brief"}
    assert items[1]["content"] == [{"type": "input_text", "text": "what is this?"},
                                   {"type": "input_image", "image_url": "data:image/png;base64,AA"}]


def settings(meta_model="muse-spark-1.3", allow=False, provider="meta"):
    return Settings(azure=AzureConfig("https://x.example", "k", "gpt5mini"),
                    meta=MetaConfig("k", "https://api.meta.ai/v1/responses", meta_model),
                    pipeline_provider=provider, allow_contributor_models=allow)


def test_configured_providers():
    assert set(configured_providers(settings())) == {"meta", "azure"}
    assert configured_providers(Settings(azure=None, meta=None)) == {}


def test_pipelines_refuse_training_contributor_models():
    with pytest.raises(ConfigError, match="trains on your data"):
        pipeline_provider(settings("muse-spark-1.3-contributor"))
    assert pipeline_provider(settings("muse-spark-1.3-contributor", allow=True)).name == "meta"
    assert pipeline_provider(settings(provider="azure")).name == "azure"


def test_unconfigured_pipeline_provider_is_a_config_error():
    with pytest.raises(ConfigError, match="not configured"):
        pipeline_provider(Settings(azure=None, meta=None, pipeline_provider="meta"))


def test_azure_json_reply_without_content_is_a_clear_provider_error(monkeypatch):
    provider = AzureProvider(AzureConfig("https://x.example", "k", "gpt5mini"))
    empty = {"choices": [{"message": {"content": None, "refusal": None}, "finish_reason": "content_filter"}], "usage": {}}
    monkeypatch.setattr(provider, "_completions", lambda model, body: empty)
    with pytest.raises(ProviderError, match="no complete JSON in the reply.*finish_reason: content_filter"):
        provider.complete_json([{"role": "user", "content": "hi"}], {}, "x")


def test_meta_tool_calls_round_trip_in_the_responses_format():
    history = [
        {"role": "system", "content": "s"},
        {"role": "assistant", "content": "Let me note that.",
         "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "record", "arguments": '{"a": 1}'}}]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'},
    ]
    items = MetaProvider.to_responses_input(history)
    assert items[1] == {"role": "assistant", "content": "Let me note that."}
    assert items[2] == {"type": "function_call", "call_id": "c1", "name": "record", "arguments": '{"a": 1}'}
    assert items[3] == {"type": "function_call_output", "call_id": "c1", "output": '{"ok": true}'}
    flat = MetaProvider.to_responses_tools([{"type": "function", "function": {"name": "record", "parameters": {}}}])
    assert flat == [{"type": "function", "name": "record", "parameters": {}}]
    calls = MetaProvider.tool_calls({"output": [{"type": "function_call", "call_id": "c2", "name": "end_call",
                                                 "arguments": "{}", "status": "completed"}]})
    assert calls[0].id == "c2" and calls[0].name == "end_call"


def test_a_copy_with_only_a_meta_key_runs_on_meta(monkeypatch):
    """The organisers' zip: they add a Meta key and nothing else, so Meta is the default provider."""
    from roleedge import config

    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    for name in ("ROLEEDGE_PROVIDER", "CARECIRCLE_PROVIDER", "AZURE_AI_ENDPOINT", "AZURE_AI_API_KEY", "API_KEY", "MODEL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("META_API_KEY", "test-key")
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().pipeline_provider == "meta"
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://example.openai.azure.com")
        monkeypatch.setenv("AZURE_AI_API_KEY", "x")
        config.get_settings.cache_clear()
        assert config.get_settings().pipeline_provider == "azure"  # unchanged where Azure is set up
    finally:
        config.get_settings.cache_clear()
