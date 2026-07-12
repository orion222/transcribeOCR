# scoreocr

Transcribes scanned piano sheet music (PNG/PDF page images) into MusicXML 4.0.
The pipeline detects staff/system/measure geometry with OpenCV, crops each
measure, and asks Claude (vision) to interpret notes, rhythm, and directions
measure-by-measure. Results are assembled into a validated MusicXML score,
rendered to SVG previews via Verovio, and optionally cross-checked against
the source page image.

## Install

Requires Python >= 3.11.

```
pip install -e ".[dev]"
```

## Environment

- `ANTHROPIC_API_KEY` — required; read by the Anthropic SDK when the CLI
  builds its Claude client.
- `DYLD_LIBRARY_PATH=/opt/homebrew/lib` (macOS only) — required only for
  `--self-check`, which rasterizes SVG previews via `cairosvg` (native
  cairo). Not needed for a plain `score-transcribe run`.

## Usage

```
score-transcribe run page1.png page2.png [--self-check] [--jobs-root DIR] [--max-workers N]
```

- `pages` — one or more input images or PDFs, in reading order.
- `--self-check` — after assembly, render each system back to an image and
  ask Claude to compare it against the source page, bouncing discrepant
  measures back through interpretation.
- `--jobs-root DIR` — where job workspaces are created (default `data/jobs`).
- `--max-workers N` — concurrency for per-measure interpretation (default 4).

Each run creates a new job workspace under `--jobs-root`. A failing stage
marks `job.json` with `status: "failed:<stage>"` and an `error` message
instead of crashing; the CLI exits 1 in that case.

## Output layout

For a job at `data/jobs/<job-id>/`:

- `output/score.musicxml` — the assembled full score.
- `output/preview/*.svg` — Verovio-rendered SVG previews of the full score.
- `pages/<page>/output/page.musicxml` — a standalone MusicXML file per input
  page (its own first measure carries a full `<attributes>` block).
- `pages/<page>/output/*.svg` — per-page SVG previews.
- `job.json` — job status, token usage, and (on failure) the error.

## Tests

```
pytest
```

(cairosvg-dependent tests need `DYLD_LIBRARY_PATH=/opt/homebrew/lib` on
stock macOS; see Environment above.)
