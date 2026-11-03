import json

from roleedge.llm import strict_schema, tool_spec
from roleedge.models import CheckinRecord, Digest


def walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def test_strict_schema_is_flat_and_closed():
    schema = strict_schema(Digest)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and "title" not in schema
    for node in walk(schema):
        if isinstance(node, dict) and node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])  # strict mode: every field required


def test_optional_and_literal_fields():
    action = strict_schema(Digest)["properties"]["actions"]["items"]["properties"]
    assert action["due_date"] == {"type": ["string", "null"]}
    verdict = strict_schema(Digest)["properties"]["trust"]["properties"]["verdict"]
    assert verdict == {"type": "string", "enum": ["looks_genuine", "unverified", "likely_scam_or_misleading"]}


def test_field_order_follows_the_model():
    assert list(strict_schema(Digest)["properties"])[:3] == ["title", "one_line", "simple_summary"]


def test_tool_spec_shape():
    spec = tool_spec("record_checkin", "Save it.", CheckinRecord)
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "record_checkin"
    assert spec["function"]["parameters"]["required"][0] == "mood"
