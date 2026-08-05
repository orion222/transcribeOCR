import base64
import json

import httpx
import pytest
from PIL import Image

from scoreocr.claude.interpreter import Interpreter, MeasureContext
from scoreocr.claude.schema import to_output_schema
from scoreocr.claude.tools import TOOL_DEFINITIONS, image_to_content_block
from scoreocr.models import MeasureIR, ScoreMeta
from scoreocr.openrouter import OpenRouterClient, OpenRouterError, translate
from scoreocr.openrouter import client as client_mod

VALID_IR = {
    "number": 1, "confidence": 0.8, "notes": "", "directions": [],
    "voices": {"treble": [{"kind": "rest", "duration": 96, "note_type": "whole",
                           "pitches": [], "dots": 0, "grace": False, "slash": False,
                           "stem": None, "beam": None, "tie": None, "tuplet": None}],
               "bass": []},
}


def _img():
    return Image.new("L", (60, 40), color=255)


def _ctx():
    img = _img()
    return MeasureContext(number=1, crop=img, system_crop=img, meta=ScoreMeta(),
                          previous=None, staff_line_ys=[10, 15, 20, 25, 30],
                          beat_xs=[15, 30, 45])


def _anthropic_kwargs(**overrides):
    kwargs = {
        "model": "anthropic/claude-opus-4.5",
        "max_tokens": 16000,
        "system": [{"type": "text", "text": "You are an engraver.",
                    "cache_control": {"type": "ephemeral"}}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high", "format": {
            "type": "json_schema", "schema": to_output_schema(MeasureIR)}},
        "tools": TOOL_DEFINITIONS,
        "messages": [{"role": "user", "content": [
            image_to_content_block(_img()),
            {"type": "text", "text": "Transcribe measure 1."},
        ]}],
    }
    kwargs.update(overrides)
    return kwargs


def _completion(content=None, tool_calls=None, finish_reason="stop",
                prompt_tokens=100, completion_tokens=50):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


# --------------------------------------------------------------------------- #
# Request translation
# --------------------------------------------------------------------------- #

def test_request_maps_core_anthropic_kwargs():
    body = translate.to_chat_request(_anthropic_kwargs(), default_model="fallback")

    assert body["model"] == "anthropic/claude-opus-4.5"
    assert body["max_tokens"] == 16000
    assert body["reasoning"] == {"effort": "high"}
    # Only route to endpoints that honour response_format / tools.
    assert body["provider"] == {"require_parameters": True}

    assert body["messages"][0] == {"role": "system", "content": "You are an engraver."}
    parts = body["messages"][1]["content"]
    assert parts[0]["type"] == "image_url"
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[1] == {"type": "text", "text": "Transcribe measure 1."}

    fn = body["tools"][0]["function"]
    assert body["tools"][0]["type"] == "function"
    assert fn["name"] == "zoom"
    assert fn["parameters"]["properties"]["x0"] == {"type": "integer"}


def test_request_default_model_used_when_kwargs_omit_it():
    kwargs = _anthropic_kwargs()
    kwargs.pop("model")
    body = translate.to_chat_request(kwargs, default_model="google/gemini-3-pro")
    assert body["model"] == "google/gemini-3-pro"


def test_response_format_is_strict_with_a_hardened_schema():
    body = translate.to_chat_request(_anthropic_kwargs(), default_model="m")
    json_schema = body["response_format"]["json_schema"]

    assert body["response_format"]["type"] == "json_schema"
    assert json_schema["strict"] is True
    schema = json_schema["schema"]
    # Strict enforcement requires every property to also be required; Pydantic
    # omits fields carrying defaults, so the hardening pass must add them.
    assert set(schema["required"]) == set(schema["properties"])
    assert "notes" in schema["required"]
    event = schema["$defs"]["Event"]
    assert set(event["required"]) == set(event["properties"])


def test_strict_schema_strips_keywords_outside_the_strict_subset():
    """Pydantic emits `default`/`title`; scoreocr.claude.schema only prunes what
    Anthropic rejects. Stricter validators reject the whole request over them."""
    body = translate.to_chat_request(_anthropic_kwargs(), default_model="m")
    schema = body["response_format"]["json_schema"]["schema"]

    def walk(node, path="$"):
        if isinstance(node, dict):
            for key in ("default", "title"):
                assert key not in node, f"{key!r} survived at {path}"
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(schema)
    # Stripping must not disturb the required-promotion or the $defs it walks.
    assert set(schema["required"]) == set(schema["properties"])
    assert "Event" in schema["$defs"]


def test_hardened_schema_still_accepts_real_model_output():
    """Forcing every field required must not reject output MeasureIR allows."""
    body = translate.to_chat_request(_anthropic_kwargs(), default_model="m")
    required = body["response_format"]["json_schema"]["schema"]["required"]
    assert set(VALID_IR) >= set(required)
    assert MeasureIR.model_validate(VALID_IR).number == 1


def test_schema_is_named_after_its_model():
    """Distinct shapes must not share a name — providers key compiled-schema
    caches on it."""
    body = translate.to_chat_request(_anthropic_kwargs(), default_model="m")
    assert body["response_format"]["json_schema"]["name"] == "MeasureIR"

    meta = translate.to_chat_request(
        _anthropic_kwargs(output_config={"effort": "high", "format": {
            "type": "json_schema", "schema": to_output_schema(ScoreMeta)}}),
        default_model="m")
    assert meta["response_format"]["json_schema"]["name"] == "ScoreMeta"


@pytest.mark.parametrize("title,expected", [
    ({"title": "Weird Name!"}, "Weird_Name_"),
    ({}, "result"),
])
def test_schema_name_is_sanitised(title, expected):
    assert translate.schema_name(title) == expected


def test_hardening_does_not_mutate_the_caller_schema():
    schema = to_output_schema(MeasureIR)
    before = json.dumps(schema, sort_keys=True)
    translate.harden_schema(schema)
    assert json.dumps(schema, sort_keys=True) == before


def test_tool_choice_none_keeps_the_tool_list():
    """Regression guard: dropping `tools` here also stops tool use, but the
    forced-final turn's history contains tool_use / tool_result blocks, and the
    Anthropic API OpenRouter forwards to rejects that combination when `tools`
    is absent."""
    body = translate.to_chat_request(
        _anthropic_kwargs(tool_choice={"type": "none"}), default_model="m")
    assert body["tool_choice"] == "none"
    assert [t["function"]["name"] for t in body["tools"]] == ["zoom", "grid_overlay"]


@pytest.mark.parametrize("anthropic_choice,expected", [
    ({"type": "auto"}, "auto"),
    ({"type": "any"}, "required"),
    ({"type": "tool", "name": "zoom"},
     {"type": "function", "function": {"name": "zoom"}}),
])
def test_tool_choice_translation(anthropic_choice, expected):
    body = translate.to_chat_request(
        _anthropic_kwargs(tool_choice=anthropic_choice), default_model="m")
    assert body["tool_choice"] == expected


def test_disabled_thinking_maps_to_reasoning_disabled():
    body = translate.to_chat_request(
        _anthropic_kwargs(thinking={"type": "disabled"}), default_model="m")
    assert body["reasoning"] == {"enabled": False}


def test_assistant_turn_with_tool_use_becomes_tool_calls():
    """The interpreter replays `response.content` verbatim, so the translator
    must accept the dataclass blocks a previous call returned, not just dicts."""
    assistant_content = [
        translate.TextBlock(text="Let me zoom in."),
        translate.ToolUseBlock(id="tu_1", name="zoom", input={"x0": 1, "y0": 2,
                                                              "x1": 3, "y1": 4}),
    ]
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[
            {"role": "user", "content": [{"type": "text", "text": "go"}]},
            {"role": "assistant", "content": assistant_content},
        ]),
        default_model="m",
    )
    assistant = body["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "Let me zoom in."
    call = assistant["tool_calls"][0]
    assert call == {"id": "tu_1", "type": "function", "function": {
        "name": "zoom", "arguments": json.dumps({"x0": 1, "y0": 2, "x1": 3, "y1": 4})}}


def test_image_tool_result_splits_into_tool_message_plus_user_image_turn():
    """OpenAI-shaped tool messages are text-only, so an image result becomes a
    text acknowledgement followed by a user turn carrying the image."""
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": [image_to_content_block(_img())]},
        ]}]),
        default_model="m",
    )
    tool_msg, image_msg = body["messages"][1], body["messages"][2]

    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "tu_1"
    assert tool_msg["content"] == translate.TOOL_IMAGE_NOTE

    assert image_msg["role"] == "user"
    assert image_msg["content"][0]["type"] == "image_url"
    assert image_msg["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert image_msg["content"][-1] == {"type": "text",
                                        "text": translate.TOOL_IMAGE_FOLLOWUP}


def test_text_only_error_tool_result_stays_a_single_tool_message():
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_9", "is_error": True,
             "content": "Tool budget exhausted."},
        ]}]),
        default_model="m",
    )
    assert body["messages"][1:] == [
        {"role": "tool", "tool_call_id": "tu_9", "content": "Tool budget exhausted."},
    ]


def test_parallel_tool_results_emit_one_tool_message_each_before_the_images():
    """OpenAI requires every tool_call to be answered before the next user turn."""
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": [image_to_content_block(_img())]},
            {"type": "tool_result", "tool_use_id": "tu_2",
             "content": [image_to_content_block(_img())]},
        ]}]),
        default_model="m",
    )
    roles = [m["role"] for m in body["messages"][1:]]
    assert roles == ["tool", "tool", "user"]
    assert [m["tool_call_id"] for m in body["messages"][1:3]] == ["tu_1", "tu_2"]
    images = [p for p in body["messages"][3]["content"] if p["type"] == "image_url"]
    assert len(images) == 2


# --------------------------------------------------------------------------- #
# Response translation
# --------------------------------------------------------------------------- #

def test_response_text_and_usage():
    response = translate.from_chat_response(_completion(content="hello"))
    assert response.stop_reason == "end_turn"
    assert [b.type for b in response.content] == ["text"]
    assert response.content[0].text == "hello"
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 50


def test_response_tool_calls_become_tool_use_blocks():
    response = translate.from_chat_response(_completion(
        content=None, finish_reason="tool_calls",
        tool_calls=[{"id": "call_1", "type": "function", "function": {
            "name": "zoom", "arguments": '{"x0": 1, "y0": 2, "x1": 3, "y1": 4}'}}],
    ))
    assert response.stop_reason == "tool_use"
    block = response.content[0]
    assert (block.type, block.id, block.name) == ("tool_use", "call_1", "zoom")
    assert block.input == {"x0": 1, "y0": 2, "x1": 3, "y1": 4}


def test_response_tolerates_unparseable_tool_arguments():
    response = translate.from_chat_response(_completion(
        content=None, finish_reason="tool_calls",
        tool_calls=[{"id": "c", "type": "function",
                     "function": {"name": "grid_overlay", "arguments": "not json"}}],
    ))
    assert response.content[0].input == {}


def test_truncated_output_raises_a_named_error():
    """A `length` finish means the JSON payload is cut off; the interpreter
    would otherwise report it as an opaque JSONDecodeError."""
    with pytest.raises(OpenRouterError, match="truncated"):
        translate.from_chat_response(
            _completion(content='{"number": 1, "confi', finish_reason="length"))


def test_tool_calls_without_ids_get_distinct_synthesised_ids():
    """Some providers behind OpenRouter (Gemini) omit tool-call ids; empty ones
    would collide across parallel calls and break tool_call_id pairing."""
    response = translate.from_chat_response(_completion(
        content=None, finish_reason="tool_calls",
        tool_calls=[
            {"type": "function", "function": {"name": "zoom", "arguments": "{}"}},
            {"type": "function", "function": {"name": "grid_overlay",
                                              "arguments": "{}"}},
        ],
    ))
    ids = [b.id for b in response.content]
    assert all(ids) and len(set(ids)) == 2


def test_response_multipart_content_is_joined():
    payload = _completion(content=[{"type": "text", "text": "a"},
                                   {"type": "text", "text": "b"}])
    assert translate.from_chat_response(payload).content[0].text == "ab"


def test_reasoning_details_are_captured_as_a_block():
    payload = _completion(content="done")
    payload["choices"][0]["message"]["reasoning_details"] = [
        {"type": "reasoning.encrypted", "data": "opaque", "signature": "sig"},
    ]
    response = translate.from_chat_response(payload)
    reasoning = [b for b in response.content if b.type == "reasoning"]
    assert len(reasoning) == 1
    assert reasoning[0].details == [
        {"type": "reasoning.encrypted", "data": "opaque", "signature": "sig"},
    ]


def test_reasoning_details_round_trip_unmodified_on_replay():
    """Regression guard for the tool loop on reasoning-capable models.

    OpenRouter requires reasoning_details to be echoed back verbatim; Anthropic
    rejects a continued tool-use turn whose thinking block went missing, which
    would fail every measure where the model zoomed in.
    """
    details = [{"type": "reasoning.encrypted", "data": "opaque", "signature": "sig"}]
    assistant_content = [
        translate.ReasoningBlock(details=details),
        translate.ToolUseBlock(id="tu_1", name="grid_overlay", input={}),
    ]
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[
            {"role": "user", "content": [{"type": "text", "text": "go"}]},
            {"role": "assistant", "content": assistant_content},
        ]),
        default_model="m",
    )
    assistant = body["messages"][-1]
    assert assistant["reasoning_details"] == details
    assert assistant["tool_calls"][0]["id"] == "tu_1"


def test_absent_reasoning_details_adds_no_field():
    body = translate.to_chat_request(
        _anthropic_kwargs(messages=[
            {"role": "user", "content": [{"type": "text", "text": "go"}]},
            {"role": "assistant", "content": [translate.TextBlock(text="hi")]},
        ]),
        default_model="m",
    )
    assert "reasoning_details" not in body["messages"][-1]


def test_error_payload_raises_with_the_provider_message():
    with pytest.raises(OpenRouterError, match="rate limited"):
        translate.from_chat_response({"error": {"code": 429, "message": "rate limited"}})


def test_missing_choices_raises():
    with pytest.raises(OpenRouterError, match="no choices"):
        translate.from_chat_response({"choices": []})


def test_empty_final_content_raises_instead_of_confusing_the_interpreter():
    """Interpreter._final_text would otherwise raise a bare StopIteration."""
    with pytest.raises(OpenRouterError, match="empty response"):
        translate.from_chat_response(_completion(content=""))


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

def _client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://openrouter.test/api/v1")
    return OpenRouterClient(model="anthropic/claude-opus-4.5", http_client=http, **kwargs)


def test_client_posts_translated_body_and_returns_translated_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion(content="ok"))

    response = _client(handler).create(**_anthropic_kwargs())

    assert seen["url"].endswith("/chat/completions")
    assert seen["body"]["model"] == "anthropic/claude-opus-4.5"
    assert seen["body"]["messages"][0]["role"] == "system"
    assert response.content[0].text == "ok"


def test_client_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("scoreocr.openrouter.client.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"retry-after": "0"}, text="slow down")
        return httpx.Response(200, json=_completion(content="ok"))

    assert _client(handler).create(**_anthropic_kwargs()).content[0].text == "ok"
    assert len(calls) == 3


def test_client_retries_a_200_carrying_a_retryable_error_payload(monkeypatch):
    """OpenRouter reports many upstream failures — rate limits included — as
    HTTP 200 with an error object, so status alone would skip the retry path."""
    monkeypatch.setattr("scoreocr.openrouter.client.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(200, json={"error": {"code": 429,
                                                       "message": "upstream limited"}})
        return httpx.Response(200, json=_completion(content="ok"))

    assert _client(handler).create(**_anthropic_kwargs()).content[0].text == "ok"
    assert len(calls) == 3


def test_client_does_not_retry_a_non_retryable_error_payload():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"error": {"code": 400, "message": "bad schema"}})

    with pytest.raises(OpenRouterError, match="error payload"):
        _client(handler).create(**_anthropic_kwargs())
    assert len(calls) == 1


def test_client_does_not_retry_an_error_payload_without_a_code():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"error": {"message": "something broke"}})

    with pytest.raises(OpenRouterError):
        _client(handler).create(**_anthropic_kwargs())
    assert len(calls) == 1


def test_negative_max_retries_still_raises_the_real_error():
    """Guard against `raise None` -> TypeError from an empty retry loop."""
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(OpenRouterError, match="HTTP 500"):
        _client(handler, max_retries=-1).create(**_anthropic_kwargs())


def test_backoff_is_jittered():
    """Four interpret workers share one client; identical delays would make them
    retry in lockstep and re-trip the same rate limit."""
    delays = {round(client_mod._backoff(1), 6) for _ in range(50)}
    assert len(delays) > 1
    assert all(1.0 <= d <= 3.0 for d in delays)


def test_client_does_not_retry_client_errors():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, text="bad schema")

    with pytest.raises(OpenRouterError, match="HTTP 400"):
        _client(handler).create(**_anthropic_kwargs())
    assert len(calls) == 1


def test_client_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr("scoreocr.openrouter.client.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, text="unavailable")

    with pytest.raises(OpenRouterError, match="HTTP 503"):
        _client(handler, max_retries=2).create(**_anthropic_kwargs())
    assert len(calls) == 3


def test_client_reports_non_json_bodies():
    def handler(request):
        return httpx.Response(200, text="<html>gateway</html>")

    with pytest.raises(OpenRouterError, match="non-JSON"):
        _client(handler).create(**_anthropic_kwargs())


def test_missing_api_key_raises_an_actionable_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
        OpenRouterClient()


# --------------------------------------------------------------------------- #
# End to end: the unmodified Interpreter driving a full tool loop over OpenRouter
# --------------------------------------------------------------------------- #

def test_interpreter_tool_loop_round_trips_through_the_adapter():
    """The whole point of the adapter: Interpreter runs unchanged, including the
    tool loop where it echoes assistant content back and returns image results."""
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(200, json=_completion(
                content=None, finish_reason="tool_calls",
                tool_calls=[{"id": "call_1", "type": "function", "function": {
                    "name": "grid_overlay", "arguments": "{}"}}]))
        return httpx.Response(200, json=_completion(content=json.dumps(VALID_IR)))

    ir, usage = Interpreter(_client(handler),
                            model="anthropic/claude-opus-4.5").interpret_measure(_ctx())

    assert isinstance(ir, MeasureIR) and ir.number == 1
    assert usage == {"input_tokens": 200, "output_tokens": 100}
    assert len(requests) == 2

    roles = [m["role"] for m in requests[1]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "user"]
    # The tool's image reached the model on the follow-up user turn.
    tool_msg, image_msg = requests[1]["messages"][3], requests[1]["messages"][4]
    assert tool_msg["tool_call_id"] == "call_1"
    assert image_msg["content"][0]["type"] == "image_url"
    b64 = image_msg["content"][0]["image_url"]["url"].split(",", 1)[1]
    assert base64.standard_b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n"


def test_interpreter_tool_budget_exhaustion_disables_tools_on_the_wire():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) <= 4:
            return httpx.Response(200, json=_completion(
                content=None, finish_reason="tool_calls",
                tool_calls=[{"id": f"call_{len(requests)}", "type": "function",
                             "function": {"name": "grid_overlay", "arguments": "{}"}}]))
        return httpx.Response(200, json=_completion(content=json.dumps(VALID_IR)))

    ir, _ = Interpreter(_client(handler), model="m",
                        max_tool_calls=3).interpret_measure(_ctx())

    assert isinstance(ir, MeasureIR)
    assert "tool_choice" not in requests[0]
    # Once the budget is spent the interpreter sets tool_choice=none. The tool
    # list must stay on the wire, because by now the history carries tool_calls
    # and tool messages that the downstream provider validates against it.
    assert requests[-1]["tool_choice"] == "none"
    assert "tools" in requests[-1]


def test_interpreter_read_score_meta_sends_no_tools():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_completion(
            content=json.dumps({"key_fifths": -1, "time_beats": 3,
                                "time_beat_type": 4})))

    meta, usage = Interpreter(_client(handler), model="m").read_score_meta(_img())

    assert isinstance(meta, ScoreMeta) and meta.time_beats == 3
    assert usage == {"input_tokens": 100, "output_tokens": 50}
    assert "tools" not in requests[0]
