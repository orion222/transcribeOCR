import json
from dataclasses import dataclass, field

from PIL import Image

from scoreocr.claude import prompts
from scoreocr.claude.schema import to_output_schema
from scoreocr.claude.tools import (
    TOOL_DEFINITIONS, grid_overlay, image_to_content_block, zoom,
)
from scoreocr.models import MeasureIR, ScoreMeta

MODEL = "claude-opus-4-8"
MAX_TOOL_CALLS = 3


@dataclass
class MeasureContext:
    number: int
    crop: Image.Image
    system_crop: Image.Image
    meta: ScoreMeta
    previous: MeasureIR | None
    staff_line_ys: list[int]
    beat_xs: list[int] = field(default_factory=list)
    prior_attempt: MeasureIR | None = None
    feedback: str | None = None


class Interpreter:
    def __init__(self, client, model: str = MODEL, max_tool_calls: int = MAX_TOOL_CALLS):
        self.client = client
        self.model = model
        self.max_tool_calls = max_tool_calls

    def _base_kwargs(self, schema: dict) -> dict:
        return {
            "model": self.model,
            "max_tokens": 16000,
            # cache_control on the stable prefix (tools + system). Note: below
            # the model's minimum cacheable prefix this is a silent no-op, but
            # it pays off as the prompt grows and costs nothing either way.
            "system": [{
                "type": "text",
                "text": prompts.SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": "high",
                "format": {"type": "json_schema", "schema": schema},
            },
            "tools": TOOL_DEFINITIONS,
        }

    def _execute_tool(self, ctx: MeasureContext, name: str, tool_input: dict) -> dict:
        if name == "zoom":
            img = zoom(ctx.crop, tool_input["x0"], tool_input["y0"],
                       tool_input["x1"], tool_input["y1"])
        else:
            img = grid_overlay(ctx.crop, ctx.staff_line_ys, ctx.beat_xs)
        return image_to_content_block(img)

    @staticmethod
    def _final_text(response) -> str:
        return next(b.text for b in response.content if b.type == "text")

    @staticmethod
    def _usage_of(responses) -> dict:
        return {
            "input_tokens": sum(r.usage.input_tokens for r in responses),
            "output_tokens": sum(r.usage.output_tokens for r in responses),
        }

    def interpret_measure(self, ctx: MeasureContext) -> tuple[MeasureIR, dict]:
        messages = prompts.measure_message(ctx)
        kwargs = self._base_kwargs(to_output_schema(MeasureIR))
        responses = []
        tool_calls_used = 0
        while True:
            response = self.client.messages.create(messages=messages, **kwargs)
            responses.append(response)
            if response.stop_reason != "tool_use":
                break
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in tool_uses
            ]})
            results = []
            for block in tool_uses:
                if tool_calls_used < self.max_tool_calls:
                    tool_calls_used += 1
                    results.append({
                        "type": "tool_result", "tool_use_id": block.id,
                        "content": [self._execute_tool(ctx, block.name, block.input)],
                    })
                else:
                    results.append({
                        "type": "tool_result", "tool_use_id": block.id, "is_error": True,
                        "content": "Tool budget exhausted — emit your final "
                                   "transcription now based on what you have seen.",
                    })
            messages.append({"role": "user", "content": results})
            if tool_calls_used >= self.max_tool_calls:
                kwargs["tool_choice"] = {"type": "none"}
        ir = MeasureIR.model_validate(json.loads(self._final_text(response)))
        return ir, self._usage_of(responses)

    def read_score_meta(self, page_image: Image.Image) -> tuple[ScoreMeta, dict]:
        kwargs = self._base_kwargs(to_output_schema(ScoreMeta))
        kwargs.pop("tools")  # metadata call needs no tools
        response = self.client.messages.create(
            messages=[{"role": "user", "content": [
                image_to_content_block(page_image),
                {"type": "text", "text": prompts.SCORE_META_PROMPT},
            ]}],
            **kwargs,
        )
        meta = ScoreMeta.model_validate(json.loads(self._final_text(response)))
        return meta, self._usage_of([response])
