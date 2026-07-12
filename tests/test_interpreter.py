import json
from types import SimpleNamespace

from PIL import Image

from scoreocr.claude.interpreter import Interpreter, MeasureContext
from scoreocr.claude.schema import to_output_schema
from scoreocr.models import MeasureIR, ScoreMeta


VALID_IR = {
    "number": 1, "confidence": 0.8, "notes": "", "directions": [],
    "voices": {"treble": [{"kind": "rest", "duration": 96, "note_type": "whole",
                           "pitches": [], "dots": 0, "grace": False, "slash": False,
                           "stem": None, "beam": None, "tie": None, "tuplet": None}],
               "bass": []},
}


def _text_response(payload):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


def _tool_response(name="grid_overlay", tool_input=None):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", id="tu_1", name=name,
                                 input=tool_input or {})],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def _thinking_block(text="let me look closer at this measure..."):
    return SimpleNamespace(type="thinking", thinking=text, signature="sig_1")


def _tool_response_with_thinking(name="grid_overlay", tool_input=None):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[
            _thinking_block(),
            SimpleNamespace(type="tool_use", id="tu_1", name=name,
                            input=tool_input or {}),
        ],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _ctx():
    img = Image.new("L", (300, 200), color=255)
    return MeasureContext(number=1, crop=img, system_crop=img, meta=ScoreMeta(),
                          previous=None, staff_line_ys=[40, 52, 64, 76, 88],
                          beat_xs=[75, 150, 225])


def test_direct_answer_no_tools():
    client = FakeClient([_text_response(VALID_IR)])
    ir, usage = Interpreter(client).interpret_measure(_ctx())
    assert isinstance(ir, MeasureIR) and ir.number == 1
    assert usage == {"input_tokens": 100, "output_tokens": 50}
    assert len(client.calls) == 1


def test_tool_then_answer():
    client = FakeClient([_tool_response(), _text_response(VALID_IR)])
    ir, _ = Interpreter(client).interpret_measure(_ctx())
    assert ir.confidence == 0.8
    assert len(client.calls) == 2
    # second call carries the tool result back
    last_msg = client.calls[1]["messages"][-1]
    assert last_msg["content"][0]["type"] == "tool_result"


def test_tool_loop_echoes_full_assistant_content_including_thinking():
    """Regression test: the assistant turn re-sent into the next request must be
    the model's full response content (thinking block included), not a
    reconstruction that keeps only the tool_use blocks. With
    thinking={"type": "adaptive"}, the API requires thinking blocks to be
    echoed back unchanged on the next turn — dropping them causes a 400.
    """
    first_response = _tool_response_with_thinking()
    client = FakeClient([first_response, _text_response(VALID_IR)])
    ir, _ = Interpreter(client).interpret_measure(_ctx())
    assert isinstance(ir, MeasureIR)

    second_call_messages = client.calls[1]["messages"]
    assistant_turns = [m for m in second_call_messages if m["role"] == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0]["content"] == first_response.content
    assert assistant_turns[0]["content"][0].type == "thinking"


def test_cap_forces_final_answer():
    client = FakeClient([
        _tool_response(), _tool_response(), _tool_response(),
        _tool_response(),  # 4th request exceeds cap of 3
        _text_response(VALID_IR),
    ])
    ir, _ = Interpreter(client, max_tool_calls=3).interpret_measure(_ctx())
    assert isinstance(ir, MeasureIR)
    # the forced-final call disallows tools
    assert client.calls[-1]["tool_choice"] == {"type": "none"}


def test_output_schema_is_api_safe():
    schema = to_output_schema(MeasureIR)
    text = json.dumps(schema)
    assert '"minimum"' not in text and '"maximum"' not in text
    assert schema["additionalProperties"] is False


def test_output_schema_voices_wire_adapter():
    """Regression test for the dict[str, list[Event]] -> object schema adapter.

    Pydantic emits `voices` as an object whose `additionalProperties` is the
    Event-array schema. The Anthropic structured-outputs API only accepts
    `additionalProperties: false`, so every additionalProperties in the emitted
    schema must be exactly False, and `voices` must be rewritten into an
    explicit object schema with `treble`/`bass` array properties.
    """
    schema = to_output_schema(MeasureIR)

    def _walk(node):
        if isinstance(node, dict):
            if "additionalProperties" in node:
                assert node["additionalProperties"] is False, (
                    "additionalProperties must be exactly False, got "
                    f"{node['additionalProperties']!r}"
                )
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)

    voices_schema = schema["properties"]["voices"]
    assert voices_schema["type"] == "object"
    assert voices_schema["additionalProperties"] is False
    assert set(voices_schema["required"]) == {"treble", "bass"}
    for voice_name in ("treble", "bass"):
        voice_prop = voices_schema["properties"][voice_name]
        assert voice_prop["type"] == "array"
        assert voice_prop["items"] == {"$ref": "#/$defs/Event"}
