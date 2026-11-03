"""Turn pydantic models into the JSON Schema that strict structured outputs require.

Strict mode needs every object to list all properties as required and to forbid extra keys,
with no ``$ref`` indirection. Pydantic's own schema has titles, ``$defs`` and ``anyOf`` for
optional fields, so ``strict_schema`` rewrites it into the plain form:

    str | None        -> {"type": ["string", "null"]}
    Literal["a", "b"] -> {"type": "string", "enum": ["a", "b"]}
    nested model      -> inlined object with additionalProperties: false

The pydantic models in ``roleedge.models`` are therefore the single source of truth for both
the prompt contract and the parsed result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_DROP = {"title", "default", "description"}


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    return _convert(raw, raw.get("$defs", {}))


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        return _convert(defs[node["$ref"].split("/")[-1]], defs)
    if "anyOf" in node:  # Optional[X] -> {"type": [X, "null"]}
        options = [_convert(o, defs) for o in node["anyOf"]]
        if all(set(o) == {"type"} and isinstance(o["type"], str) for o in options):
            return {"type": [o["type"] for o in options]}
        raise ValueError(f"Only unions of simple types are supported, got: {node}")

    kind = node.get("type")
    if kind == "object":
        props = {name: _convert(p, defs) for name, p in node.get("properties", {}).items()}
        return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    if kind == "array":
        return {"type": "array", "items": _convert(node["items"], defs)}
    return {k: v for k, v in node.items() if k not in _DROP}


def tool_spec(name: str, description: str, parameters: type[BaseModel]) -> dict[str, Any]:
    """A Chat Completions function-tool definition whose arguments are ``parameters``."""
    return {"type": "function",
            "function": {"name": name, "description": description, "parameters": strict_schema(parameters)}}
