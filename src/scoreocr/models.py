from typing import Literal

from pydantic import BaseModel, Field

DIVISIONS = 24  # divisions per quarter note, fixed for the whole score


class Pitch(BaseModel):
    step: Literal["A", "B", "C", "D", "E", "F", "G"]
    alter: int = Field(0, ge=-2, le=2)
    octave: int = Field(ge=0, le=9)


class TupletInfo(BaseModel):
    actual: int
    normal: int
    position: Literal["start", "middle", "stop"]


class Event(BaseModel):
    kind: Literal["note", "chord", "rest"]
    duration: int = Field(ge=0)  # 0 only for grace notes
    note_type: str
    pitches: list[Pitch] = []
    dots: int = Field(0, ge=0, le=2)
    grace: bool = False
    slash: bool = False
    stem: Literal["up", "down"] | None = None
    beam: Literal["begin", "continue", "end"] | None = None
    tie: Literal["start", "stop", "both"] | None = None
    tuplet: TupletInfo | None = None


class Direction(BaseModel):
    kind: Literal["dynamic", "tempo", "harmony", "text"]
    value: str
    beat: float = 1.0
    staff: Literal["treble", "bass"] | None = None


class MeasureIR(BaseModel):
    number: int
    voices: dict[str, list[Event]]  # keys: "treble", "bass"
    directions: list[Direction] = []
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class ScoreMeta(BaseModel):
    title: str = ""
    key_fifths: int = Field(0, ge=-7, le=7)
    time_beats: int = 4
    time_beat_type: int = 4
    tempo_bpm: float | None = None
    first_measure_number: int = 1


def measure_total(meta: ScoreMeta) -> int:
    """Expected duration sum per voice per measure, in divisions."""
    return DIVISIONS * meta.time_beats * 4 // meta.time_beat_type


class StaffBox(BaseModel):
    line_ys: list[int]  # exactly 5, top to bottom

    @property
    def top(self) -> int:
        return self.line_ys[0]

    @property
    def bottom(self) -> int:
        return self.line_ys[-1]


class SystemBox(BaseModel):
    top: int
    bottom: int
    left: int
    right: int
    staves: list[StaffBox]      # [treble, bass]
    barline_xs: list[int]       # includes left and right edges
    measure_numbers: list[int]  # absolute; len == len(barline_xs) - 1


class PageGeometry(BaseModel):
    page: str  # "p01"
    width: int
    height: int
    systems: list[SystemBox]


class PageEntry(BaseModel):
    page: str            # "p01"
    source_name: str     # original filename
    measure_start: int = 0
    measure_end: int = 0  # inclusive; 0 = not yet assigned


class JobState(BaseModel):
    job_id: str
    status: str = "created"
    self_check: bool = False
    pages: list[PageEntry] = []
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
