from scoreocr.models import DIVISIONS, MeasureIR, ScoreMeta

SYSTEM_PROMPT = f"""You are an expert music engraver transcribing piano sheet music.
You read one measure of a grand staff (treble + bass) at a time and produce a
structured transcription.

Conventions:
- durations are integers with {DIVISIONS} divisions per quarter note
  (whole=96, half=48, quarter=24, eighth=12, 16th=6, 32nd=3; a dot multiplies by 1.5)
- pitch `alter` is the SOUNDING alteration after applying the key signature and any
  accidentals, including accidental persistence within the measure
- grace notes have duration 0 and grace=true
- chord: one event, kind="chord", all pitches listed; the chord occupies one time slot
- each voice's non-grace durations must sum exactly to the measure total
- set `confidence` (0.0-1.0) honestly; describe anything ambiguous in `notes`

Use the zoom and grid_overlay tools when a detail is ambiguous. You may use at most
3 tool calls per measure; then you must commit to a reading."""


def measure_message(ctx) -> list[dict]:
    from scoreocr.claude.tools import image_to_content_block

    meta: ScoreMeta = ctx.meta
    lines = [
        f"Transcribe measure {ctx.number}.",
        f"Key signature: {meta.key_fifths} fifths. Time signature: "
        f"{meta.time_beats}/{meta.time_beat_type}. "
        f"Expected duration per voice: {DIVISIONS * meta.time_beats * 4 // meta.time_beat_type} divisions.",
        "First image: the measure crop. Second image: the full system for context "
        "(beams/ties may cross into neighbors).",
    ]
    if ctx.previous is not None:
        lines.append(
            "Previous measure IR (for accidental/voice continuity): "
            + ctx.previous.model_dump_json()
        )
    if ctx.prior_attempt is not None:
        lines.append(
            "Your earlier reading was REJECTED. Earlier reading: "
            + ctx.prior_attempt.model_dump_json()
        )
    if ctx.feedback:
        lines.append(f"Rejection reason / reviewer feedback: {ctx.feedback}")
    lines.append("Respond with the MeasureIR JSON.")
    return [
        {"role": "user", "content": [
            image_to_content_block(ctx.crop),
            image_to_content_block(ctx.system_crop),
            {"type": "text", "text": "\n".join(lines)},
        ]}
    ]


SCORE_META_PROMPT = """Read this full sheet-music page and report score-level metadata:
title (if printed), key signature as fifths (flats negative: 4 flats = -4),
time signature, tempo in BPM if marked, and the first printed measure number
(1 if unnumbered). Respond with the ScoreMeta JSON."""
