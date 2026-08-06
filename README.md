# scoreocr

Transcribes scanned piano sheet music into **MusicXML 4.0**.

Give it page images (PNG/JPG) or a PDF; it detects the staff/system/measure
geometry with OpenCV, asks a vision model to read each measure into a
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

2. **geometry** — Pure OpenCV, no ML. Staff lines are horizontal runs spanning
   ≥40% of the page width, grouped in fives and paired into grand-staff
   *systems*; barlines are vertical runs spanning ≥75% of a system's height, and
   delimit *measures*. Both tests look for one *continuous* run rather than for
   total ink in a row or column, so that collinear marks — a row of tuplet
   brackets between the staves, a treble stem above a bass stem — cannot add up
   into a phantom line.
   Measures are numbered absolutely and continuously across systems and pages.
   Writes `pages/<page>/geometry.json`. If the geometry is implausible
   (staff lines don't group into fives, no barlines found) it raises rather
   than feeding garbage downstream.

3. **crop** — Cuts a system image and a per-measure image for each detected
   measure into `pages/<page>/crops/`. The vertical span includes a margin
   above/below the system so ledger lines survive the crop.

4. **interpret** — The vision step (see [Providers](#providers) for how the
   model is chosen; default `anthropic/claude-opus-4.5` via OpenRouter). One
   score-metadata call per page (key, time signature, title), then one call
   per measure. Each measure call runs a **bounded tool loop**: the model may
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
   system back to an image (cairosvg) and asks the model to compare it against
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

The interpret and self-check stages call a vision model, so you need an API
key. Put it in a `.env` file in the project root — the CLI loads it
automatically at startup.

```bash
cp .env.example .env
# then edit .env and set your key:
# OPENROUTER_API_KEY=sk-or-v1-...
```

`.env` is git-ignored so your key is never committed. Real environment
variables exported in your shell take precedence over the file, so CI/other
environments can supply the key however they like.

### Providers

Two providers are supported. **OpenRouter is the default**, because it fronts
any vision model worth pointing at this pipeline.

| Provider | Key | Default model |
| --- | --- | --- |
| `openrouter` (default) | `OPENROUTER_API_KEY` | `anthropic/claude-opus-4.5` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-4-8` |

Both `run` and `serve` take `--provider` and `--model`; the equivalent
environment variables are `SCOREOCR_PROVIDER` and `SCOREOCR_MODEL`, and flags
win over them. Point it at any OpenRouter model that supports vision, tool
calling, and structured outputs:

```bash
score-transcribe run page.png --model google/gemini-3-pro-preview
score-transcribe run page.png --provider anthropic          # Anthropic API directly
```

Requests are sent with `provider.require_parameters`, so OpenRouter only routes
to endpoints that actually honour the JSON schema and tool definitions — a model
that silently ignored them would return prose that fails IR validation later in
the pipeline.

If `OPENROUTER_API_KEY` is unset but `ANTHROPIC_API_KEY` is present, the CLI
falls back to the Anthropic provider and says so on stderr. Passing
`--provider openrouter` explicitly disables that fallback and fails instead.

<details>
<summary>How the OpenRouter adapter works</summary>

`Interpreter` speaks the Anthropic Messages shape natively. Rather than refactor
it behind a provider protocol, `scoreocr.openrouter.OpenRouterClient` exposes the
same `client.messages.create(**kwargs)` surface and
`scoreocr.openrouter.translate` converts to and from OpenRouter's
OpenAI-compatible `/chat/completions` — so `interpreter.py`, `prompts.py`, and
`tools.py` are untouched and identical on both providers.

One asymmetry is worth knowing about: an OpenAI-shaped `role: "tool"` message
carries a plain string and cannot hold an image, but both of our tools (`zoom`,
`grid_overlay`) return images. The adapter therefore answers such a tool call
with a short text acknowledgement and attaches the image to the user turn that
immediately follows, so the tool loop behaves the same on both providers.

</details>

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
measure (plus up to 3 extra tool calls for measures the model chooses to zoom
into), so a typical page is a few dozen frontier-model calls. Switching
`--model` to something cheaper is the main cost lever.

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

## Web app

A browser front end lets you drag-and-drop a batch of page photos, watch
each page transcribe with per-photo progress, preview/play/download
finished pages as they land, and merge the whole batch into one score at
the end.

### Build and run

```
npm --prefix frontend install   # first time only
npm --prefix frontend run build
score-transcribe serve --jobs-root data/jobs
```

Then open http://127.0.0.1:8000 — FastAPI serves the built SPA at `/` and
the API under `/api/...` from the same process. `serve` also accepts
`--host` and `--port` (defaults `127.0.0.1:8000`), and `--reload` for
development (see below).

### Development workflow

Run the API and the Vite dev server side by side, so that backend and
frontend edits both take effect without a manual restart or rebuild:

```
# terminal 1
score-transcribe serve --jobs-root data/jobs --reload

# terminal 2
npm --prefix frontend run dev
```

Open the Vite dev server URL (typically http://127.0.0.1:5173); its dev
server proxies `/api` requests to `127.0.0.1:8000` (see
`frontend/vite.config.js`), so the UI talks to the real backend.

`--reload` restarts the API whenever a file under `src/scoreocr/` changes.
Without it the server keeps serving the pipeline code it imported at startup,
so editing a stage has no effect until you stop and restart — an easy way to
spend a while re-diagnosing a bug you already fixed. Two things to know:

- It watches `src/scoreocr/` only, not the working directory, so the files a
  running job writes under `data/jobs/` never trigger a restart.
- A restart kills in-flight transcriptions. Batches run in daemon threads, so
  one that was mid-flight is left at `status: "processing"` in its manifest and
  never resumes; discard that job directory and start over.

API keys are unaffected either way. `.env` is read when a transcription starts
rather than at server startup, so a new key applies to the next job without a
restart — it is only *code* that needs one.

The static-SPA serving behavior — mounting `frontend/dist` at `/`, with a
non-`/api` catch-all falling back to `index.html` — is covered by
`tests/test_web_api.py::test_root_serves_spa_when_built` (it points
FastAPI at a fake dist via the `SCOREOCR_FRONTEND_DIST` env var, so it
runs without a real `npm run build`). When `frontend/dist` doesn't exist
(e.g. it hasn't been built yet), the API-only routes still work; `/` and
other non-`/api` paths simply 404.

### Manual end-to-end smoke test

The automated tests above use a `StubInterpreter` and need no API key.
To verify the real flow against a live model end to end (requires
`OPENROUTER_API_KEY`, or `ANTHROPIC_API_KEY` with `--provider anthropic`):

```
# terminal 1 — build frontend then serve
cd frontend && npm run build && cd ..
score-transcribe serve --jobs-root data/jobs
# terminal 2 (or a browser): open http://127.0.0.1:8000
```

Verify: upload 2 page images → Convert → per-photo progress advances →
finished cards show preview + play + download while a later photo is
still processing → after completion, "Merge all" shows the combined
score with playback and download.

## Tests

```bash
pytest
cd frontend && npm test
```

The suite is fully offline — the interpreter is exercised with a fake
Anthropic client, and the OpenRouter adapter with an `httpx.MockTransport`,
so no test makes a network call or needs an API key. On
stock macOS, the cairosvg-dependent self-check tests need
`DYLD_LIBRARY_PATH=/opt/homebrew/lib` (see Configuration).
