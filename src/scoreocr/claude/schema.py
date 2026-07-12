import copy

from pydantic import BaseModel

UNSUPPORTED_KEYS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "minItems", "maxItems",
}


def _clean(node):
    if isinstance(node, dict):
        for key in list(node):
            if key in UNSUPPORTED_KEYS:
                del node[key]
            else:
                _clean(node[key])
        if node.get("type") == "object":
            node["additionalProperties"] = False
    elif isinstance(node, list):
        for item in node:
            _clean(item)


def _rewrite_voices(schema: dict) -> None:
    """Rewrite `voices: dict[str, list[Event]]` into an explicit object schema.

    Pydantic emits a `dict[str, list[Event]]` field as an object whose
    `additionalProperties` is the Event-array schema. The Anthropic
    structured-outputs API only accepts `additionalProperties: false`, so a
    dict-valued additionalProperties must be replaced before the generic
    cleaning pass runs (which would otherwise overwrite it with `false` and
    silently drop the value schema, forcing `voices` to always deserialize
    empty). The wire JSON shape is unchanged: a dict with treble/bass keys is
    the same JSON as an object with treble/bass properties.
    """
    voices = schema.get("properties", {}).get("voices")
    if voices is None:
        return
    event_array_schema = voices["additionalProperties"]
    schema["properties"]["voices"] = {
        "type": "object",
        "properties": {
            "treble": copy.deepcopy(event_array_schema),
            "bass": copy.deepcopy(event_array_schema),
        },
        "required": ["treble", "bass"],
        "additionalProperties": False,
    }


def to_output_schema(model_cls: type[BaseModel]) -> dict:
    schema = model_cls.model_json_schema()
    _rewrite_voices(schema)
    _clean(schema)
    return schema
