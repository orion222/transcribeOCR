"""Translate between the Anthropic Messages shape and OpenRouter's chat API.

`Interpreter` speaks Anthropic Messages natively: base64 image blocks, tool_use
/ tool_result blocks, `output_config.format`, `thinking`. OpenRouter exposes an
OpenAI-compatible `/chat/completions` surface instead. Rather than refactor the
interpreter behind a provider protocol, the OpenRouter client accepts the exact
same kwargs and the functions here do the conversion, so `interpreter.py`,
`prompts.py`, and `tools.py` stay untouched and provider-agnostic.

The functions are pure so the mapping can be tested without a network call.
"""

import copy
import json
from dataclasses import dataclass, field

# An OpenAI-shaped `role: "tool"` message carries a plain string — it cannot hold
# an image. Both of our tools (zoom, grid_overlay) return images, so the tool
# message acknowledges the result in text and the image follows in a user turn.
TOOL_IMAGE_NOTE = "Image returned; it is attached in the following user message."
TOOL_IMAGE_FOLLOWUP = (
    "Above are the image(s) returned by the tool call(s) you just made. "
    "Continue from what you can now see."
)
EMPTY_TOOL_RESULT = "(tool returned no output)"

_TOOL_CHOICE = {"auto": "auto", "any": "required", "none": "none"}
_FALLBACK_SCHEMA_NAME = "result"
# Outside the keyword subset strict json_schema validators accept.
_STRICT_UNSUPPORTED_KEYS = frozenset({"default", "title"})


class OpenRouterError(RuntimeError):
    """An OpenRouter request failed, or returned a response we cannot use."""


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class ReasoningBlock:
    """Carries a turn's `reasoning_details` so the tool loop can replay it.

    Reasoning-capable models return provider-signed reasoning alongside a tool
    call, and OpenRouter requires it to be echoed back verbatim on the next
    request — Anthropic rejects a continued tool-use turn whose thinking block
    is missing. The interpreter replays `response.content` wholesale, so riding
    along as a content block is what gets this back onto the wire.

    `details` is opaque: store it, return it, never reconstruct it.
    """
    details: object
    type: str = "reasoning"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Response:
    content: list
    stop_reason: str
    usage: Usage


def _field(block, name, default=None):
    """Read `name` off a content block.

    Blocks arrive as plain dicts on the way in, but the assistant turn the
    interpreter echoes back is the dataclass list we returned from a previous
    call (it replays `response.content` verbatim), so both shapes must work.
    """
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


# --------------------------------------------------------------------------- #
# Request: Anthropic kwargs -> OpenAI chat-completions body
# --------------------------------------------------------------------------- #

def _image_url_part(source) -> dict:
    if not isinstance(source, dict):
        raise OpenRouterError(f"image block has no usable source: {source!r}")
    if source.get("type") == "url":
        url = source.get("url", "")
    else:
        media_type = source.get("media_type") or "image/png"
        url = f"data:{media_type};base64,{source.get('data', '')}"
    return {"type": "image_url", "image_url": {"url": url}}


def _assistant_message(blocks) -> dict:
    texts, tool_calls, reasoning = [], [], None
    for block in blocks:
        kind = _field(block, "type")
        if kind == "text":
            texts.append(_field(block, "text") or "")
        elif kind == "tool_use":
            tool_calls.append({
                "id": _field(block, "id") or "",
                "type": "function",
                "function": {
                    "name": _field(block, "name") or "",
                    "arguments": json.dumps(_field(block, "input") or {}),
                },
            })
        elif kind == "reasoning":
            reasoning = _field(block, "details")
        # Anthropic-native `thinking` / `redacted_thinking` blocks would only
        # reach here if something bypassed this adapter; they have no OpenAI
        # equivalent, so drop them rather than send garbage.
    message = {"role": "assistant", "content": "\n".join(t for t in texts if t)}
    if tool_calls:
        message["tool_calls"] = tool_calls
    if reasoning is not None:
        # Verbatim, per OpenRouter: the signature is computed over this payload.
        message["reasoning_details"] = reasoning
    return message


def _user_messages(blocks) -> list[dict]:
    """Expand one Anthropic user turn into the OpenAI messages it maps to.

    A turn carrying tool_result blocks becomes one `role: "tool"` message per
    result (OpenAI requires them to directly follow the assistant turn that made
    the calls), optionally followed by a user turn carrying any images those
    results produced.
    """
    tool_messages, deferred_images, parts = [], [], []
    for block in blocks:
        kind = _field(block, "type")
        if kind != "tool_result":
            if kind == "image":
                parts.append(_image_url_part(_field(block, "source")))
            elif kind == "text":
                parts.append({"type": "text", "text": _field(block, "text") or ""})
            continue

        raw = _field(block, "content")
        texts, images = [], []
        if isinstance(raw, str):
            texts.append(raw)
        else:
            for inner in raw or []:
                inner_kind = _field(inner, "type")
                if inner_kind == "text":
                    texts.append(_field(inner, "text") or "")
                elif inner_kind == "image":
                    images.append(_image_url_part(_field(inner, "source")))
        if images:
            texts.append(TOOL_IMAGE_NOTE)
        tool_messages.append({
            "role": "tool",
            "tool_call_id": _field(block, "tool_use_id") or "",
            "content": "\n".join(t for t in texts if t) or EMPTY_TOOL_RESULT,
        })
        deferred_images.extend(images)

    messages = list(tool_messages)
    if deferred_images:
        messages.append({"role": "user", "content": [
            *deferred_images, {"type": "text", "text": TOOL_IMAGE_FOLLOWUP},
        ]})
    if parts:
        messages.append({"role": "user", "content": parts})
    return messages


def _system_text(system) -> str:
    if not system:
        return ""
    if isinstance(system, str):
        return system
    # `cache_control` is deliberately dropped: it is Anthropic-specific, and the
    # system prompt here sits below every model's minimum cacheable prefix, so
    # preserving it would buy nothing while risking rejection by other providers.
    return "\n".join(_field(b, "text") or "" for b in system).strip()


def _convert_messages(system, messages) -> list[dict]:
    out = []
    if text := _system_text(system):
        out.append({"role": "system", "content": text})
    for message in messages:
        role = _field(message, "role")
        content = _field(message, "content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif role == "assistant":
            out.append(_assistant_message(content or []))
        else:
            out.extend(_user_messages(content or []))
    return out


def _convert_tools(tools) -> list[dict]:
    return [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    } for tool in tools]


def _convert_tool_choice(choice):
    if choice is None:
        return None
    if isinstance(choice, str):
        return choice
    kind = choice.get("type")
    if kind == "tool":
        return {"type": "function", "function": {"name": choice.get("name", "")}}
    return _TOOL_CHOICE.get(kind, "auto")


def _convert_reasoning(thinking, effort):
    if not thinking:
        return None
    if _field(thinking, "type") == "disabled":
        return {"enabled": False}
    return {"effort": effort or "high"}


def schema_name(schema: dict) -> str:
    """Name the response schema after the model it came from.

    Pydantic emits the class name as `title` and `to_output_schema` keeps it.
    Providers key their compiled-schema caches partly on this name, so sending
    MeasureIR, ScoreMeta, and DiscrepancyReport all as "result" risks one shape
    being validated against another's compiled schema.
    """
    title = schema.get("title") or ""
    cleaned = "".join(c if c.isalnum() or c in "_-" else "_" for c in title)
    return cleaned or _FALLBACK_SCHEMA_NAME


def harden_schema(schema: dict) -> dict:
    """Make a Pydantic schema acceptable to a strict `json_schema` validator.

    Two changes. Every key in `properties` is promoted into `required`, because
    strict enforcement demands it and Pydantic omits fields carrying defaults;
    each such field in our IR models is either nullable or has a value the model
    can state explicitly, so this cannot make `model_validate` reject otherwise
    valid output. And `default` / `title` are stripped, because they sit outside
    the keyword subset strict validators accept — leaving them in gets the whole
    request rejected by stricter providers (`scoreocr.claude.schema` only prunes
    the keywords Anthropic rejects). Promoting everything to required also makes
    `default` moot.

    Both changes are keyword-level, so the walk has to know which dicts are
    schema nodes and which are maps of field name to schema. Recursing over
    every value alike deletes a *field* called `title` or `default` from a
    `properties` map while `required` still names it, and the request is then
    rejected for requiring a property the schema no longer declares.
    """
    out = copy.deepcopy(schema)
    _harden(out)
    return out


# Where child schemas live, so the walk can tell a keyword from a field name.
_CHILD_SCHEMA_MAPS = ("properties", "$defs", "definitions", "patternProperties")
_CHILD_SCHEMA_LISTS = ("anyOf", "oneOf", "allOf", "prefixItems")
_CHILD_SCHEMA_NODES = ("items", "not", "if", "then", "else", "additionalProperties")


def _harden(node) -> None:
    if not isinstance(node, dict):
        return
    for key in _STRICT_UNSUPPORTED_KEYS & node.keys():
        del node[key]
    for key in _CHILD_SCHEMA_MAPS:
        if isinstance(node.get(key), dict):
            for child in node[key].values():
                _harden(child)
    for key in _CHILD_SCHEMA_LISTS:
        if isinstance(node.get(key), list):
            for child in node[key]:
                _harden(child)
    for key in _CHILD_SCHEMA_NODES:
        if isinstance(node.get(key), dict):
            _harden(node[key])
    # After the recursion, so `required` can only ever name properties that
    # actually survived it.
    properties = node.get("properties")
    if node.get("type") == "object" and isinstance(properties, dict):
        node["required"] = list(properties)


def to_chat_request(kwargs: dict, *, default_model: str) -> dict:
    """Build an OpenRouter chat-completions body from Anthropic Messages kwargs.

    Keys the Anthropic API understands but OpenRouter has no equivalent for are
    dropped rather than forwarded; anything new added to `Interpreter._base_kwargs`
    needs a case here to reach the wire.
    """
    kwargs = dict(kwargs)
    body = {
        "model": kwargs.pop("model", None) or default_model,
        "messages": _convert_messages(kwargs.pop("system", None), kwargs.pop("messages", [])),
    }
    if (max_tokens := kwargs.pop("max_tokens", None)) is not None:
        body["max_tokens"] = max_tokens

    output_config = kwargs.pop("output_config", None) or {}
    fmt = output_config.get("format") or {}
    if fmt.get("type") == "json_schema" and fmt.get("schema"):
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": fmt.get("name") or schema_name(fmt["schema"]),
            "strict": True,
            "schema": harden_schema(fmt["schema"]),
        }}

    if reasoning := _convert_reasoning(kwargs.pop("thinking", None), output_config.get("effort")):
        body["reasoning"] = reasoning

    tools = kwargs.pop("tools", None)
    choice = _convert_tool_choice(kwargs.pop("tool_choice", None))
    if tools:
        # Keep sending `tools` even when the interpreter has spent its tool
        # budget and set tool_choice=none. Dropping the list would also stop
        # tool use, but OpenRouter maps this onto each provider's native API,
        # and Anthropic's rejects any request whose history contains tool_use /
        # tool_result blocks while `tools` is absent — which is exactly the
        # state the forced-final turn is in.
        body["tools"] = _convert_tools(tools)
        if choice is not None:
            body["tool_choice"] = choice

    # Only route to endpoints that actually honour the parameters above —
    # otherwise a provider silently ignoring response_format would hand back
    # prose that fails IR validation downstream.
    body["provider"] = {"require_parameters": True}
    return body


# --------------------------------------------------------------------------- #
# Response: OpenAI chat completion -> Anthropic-shaped response
# --------------------------------------------------------------------------- #

def _message_text(content) -> str:
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return content or ""


def from_chat_response(payload: dict) -> Response:
    if isinstance(payload.get("error"), dict):
        error = payload["error"]
        raise OpenRouterError(
            f"OpenRouter error {error.get('code', 'unknown')}: "
            f"{error.get('message', 'no message')}"
        )
    choices = payload.get("choices") or []
    if not choices:
        raise OpenRouterError(f"response contained no choices: {str(payload)[:500]}")

    choice = choices[0]
    message = choice.get("message") or {}
    finish = choice.get("finish_reason") or choice.get("native_finish_reason")
    if finish == "length":
        # Whatever came back is cut off — the JSON payload and any tool-call
        # arguments are both unparseable. Say so here rather than let the
        # interpreter surface it as a bewildering JSONDecodeError.
        raise OpenRouterError(
            "model output was truncated before it finished (finish_reason='length'); "
            "raise max_tokens or pick a model with a larger output budget"
        )

    blocks = []
    # Must come first so it survives back onto the next request unmodified.
    if (reasoning := message.get("reasoning_details")) is not None:
        blocks.append(ReasoningBlock(details=reasoning))
    if text := _message_text(message.get("content")):
        blocks.append(TextBlock(text=text))
    for index, call in enumerate(message.get("tool_calls") or []):
        function = call.get("function") or {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
        blocks.append(ToolUseBlock(
            # Some providers behind OpenRouter (Gemini among them) omit the id.
            # Synthesising one here means the id the assistant turn declares and
            # the id the tool result answers with are the same value — leaving
            # it "" would collide across parallel calls.
            id=call.get("id") or f"call_{index}",
            name=function.get("name") or "",
            input=arguments if isinstance(arguments, dict) else {},
        ))

    stop_reason = (
        "tool_use" if any(block.type == "tool_use" for block in blocks)
        else "end_turn"
    )

    if stop_reason != "tool_use" and not text:
        # The interpreter's next move is to read the final text block; failing
        # here names the cause instead of raising StopIteration from a genexp.
        raise OpenRouterError(
            f"model returned an empty response (finish_reason={finish!r})"
        )

    usage = payload.get("usage") or {}
    return Response(
        content=blocks,
        stop_reason=stop_reason,
        usage=Usage(
            input_tokens=usage.get("prompt_tokens") or 0,
            output_tokens=usage.get("completion_tokens") or 0,
        ),
    )
