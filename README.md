# scoreocr

Transcribes scanned piano sheet music into **MusicXML 4.0**.

Give it page images (PNG/JPG) or a PDF; it detects the staff/system/measure
geometry with OpenCV, asks Claude (vision) to read each measure into a
structured musical representation, then deterministically assembles,
validates, and renders a MusicXML score you can open in MuseScore, Finale,
Dorico, or any notation editor.

It is a personal, local, command-line tool: all state for a transcription
lives in a single job directory on disk — there is no database and no server.

## How it works

The transcription is a filesystem pipeline. Each stage reads the previous
stage's files from the job directory and writes its own, advancing
`job.json`'s `status`. Because every input and output is a file, a run is
inspectable at every step and a failed stage can be diagnosed (and, later,
retried) from disk.

```
images/PDF
   │
   ▼
1. ingest ──► 2. geometry ──► 3. crop ──► 4. interpret ──► 5. assemble
                                                                │
                        8. self-check (optional) ◄─────────────┤
                                                                ▼
                                          7. render ◄──── 6. validate
```

1. **ingest** — Normalizes every input into one grayscale PNG per page under
   `pages/<page>/source.png`, preserving input order. PDFs are rasterized at
   300 DPI (pypdfium2); image files are converted with Pillow. All pages of a
   single run form one job / one song.

2. **geometry** — Pure OpenCV, no ML. Horizontal dark-pixel projections find
   staff lines, which are grouped in fives and paired into grand-staff
   *systems*; vertical projections find barlines, which delimit *measures*.
   Measures are numbered absolutely and continuously across systems and pages.
   Writes `pages/<page>/geometry.json`. If the geometry is implausible
   (staff lines don't group into fives, no barlines found) it raises rather
   than feeding garbage downstream.

3. **crop** — Cuts a system image and a per-measure image for each detected
   measure into `pages/<page>/crops/`. The vertical span includes a margin
   above/below the system so ledger lines survive the crop.

4. **interpret** — The vision step, using Claude (`claude-opus-4-8`). One
   score-metadata call per page (key, time signature, title), then one call
   per measure. Each measure call runs a **bounded tool loop**: Claude may
   call `zoom` or `grid_overlay` on the crop up to 3 times to look closer,
   then is forced to return a structured `MeasureIR` (notes, chords, rests,
   rhythm, beams, ties, tuplets, dynamics/tempo/harmony directions) via
   structured outputs. Measures are interpreted concurrently. If a measure's
   note durations don't sum to the time signature, it is automatically
   re-interpreted once with that discrepancy as feedback ("bounce-back").
   A measure that still fails is written as an `mNNN.error.json` sidecar and
   the job continues — one bad measure never kills the run.

5. **assemble** — Deterministically serializes the measure IR into MusicXML
   4.0: one piano part, two staves (treble = voice 1 / staff 1, bass =
   voice 2 / staff 2, with `<backup>` between them), `DIVISIONS = 24` per
   quarter note. Produces a consolidated `output/score.musicxml` for the whole
   song **plus** a standalone `pages/<page>/output/page.musicxml` per page
   (each re-states clef/key/time at its first measure so it renders alone).

6. **validate** — Structural and rhythmic checks on the assembled score
   (lxml): parseability, measure count and numbering continuity, per-voice
   duration sums, grace-note handling, final barline. Problems are reported,
   not fatal.

7. **render** — Verovio renders the MusicXML to SVG previews
   (`output/preview/*.svg` and per-page previews), honoring the encoded
   system/page breaks so the layout tracks the source.

8. **self-check** *(optional, `--self-check`)* — Rasterizes each rendered
   system back to an image (cairosvg) and asks Claude to compare it against
   the source crop. Discrepant measures are bounced back through interpret →
   assemble → render, up to 2 rounds. Remaining discrepancies are reported.

## Install

Requires Python ≥ 3.11.

```bash
pip install -e ".[dev]"
```

(Working from a virtualenv is recommended, e.g. `python -m venv .venv &&
source .venv/bin/activate` before installing.)

## Configuration

The interpret and self-check stages call the Anthropic API, so you need an
API key. Put it in a `.env` file in the project root — the CLI loads it
automatically at startup.

```bash
cp .env.example .env
# then edit .env and set your key:
# ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is git-ignored so your key is never committed. A real
`ANTHROPIC_API_KEY` exported in your shell takes precedence over the file, so
CI/other environments can supply the key however they like.

**macOS + `--self-check` only:** the self-check stage uses `cairosvg`, which
loads native cairo. If it fails to find it, install cairo
(`brew install cairo`) and export its location before running:

```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

This is not needed for a plain `score-transcribe run`.

## Running it

```bash
score-transcribe run page1.png page2.png
```

Pass pages in reading order; a PDF can be given instead of images. Each run
creates a fresh job directory under `--jobs-root` and prints the job path and
output locations when it finishes.

Options:

| Flag | Default | Meaning |
|------|---------|---------|
| `pages` | — | One or more input images or a PDF, in reading order. |
| `--self-check` | off | Render-vs-source comparison + auto-correction pass (see stage 8). |
| `--jobs-root DIR` | `data/jobs` | Where job directories are created. |
| `--max-workers N` | `4` | Concurrency for per-measure interpretation. |

Exit code is `0` on success, `1` if validation reported issues or a stage
failed. On failure the job is not left in a mystery state: `job.json` records
`status: "failed:<stage>"` and an `error` message, and the CLI prints the
failing stage to stderr.

Rough cost intuition: a page costs about one metadata call plus one call per
measure (plus up to 3 extra tool calls for measures Claude chooses to zoom
into), so a typical page is a few dozen Opus calls.

## Output layout

For a job at `data/jobs/<job-id>/`:

| Path | What it is |
|------|-----------|
| `output/score.musicxml` | The assembled full-song score — the main deliverable. |
| `output/preview/score-NN.svg` | Verovio SVG previews of the full score. |
| `pages/<page>/output/page.musicxml` | Standalone MusicXML for one page. |
| `pages/<page>/output/preview-NN.svg` | Per-page SVG previews. |
| `pages/<page>/source.png` | The normalized page image. |
| `pages/<page>/geometry.json` | Detected staves, systems, and barlines. |
| `pages/<page>/crops/` | System and per-measure crop images. |
| `pages/<page>/transcription/mNNN.json` | Per-measure interpreted IR. |
| `job.json` | Job status, token usage, and (on failure) the error. |

## Development

```bash
pytest
```

The suite is fully offline — the interpreter is exercised with a fake
Anthropic client, so no test makes a network call or needs an API key. On
stock macOS, the cairosvg-dependent self-check tests need
`DYLD_LIBRARY_PATH=/opt/homebrew/lib` (see Configuration).
