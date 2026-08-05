// frontend/src/pipeline/stages.js
//
// The authoritative description of the pipeline is the repo root README.md
// ("How it works" / "The transcription is a filesystem pipeline"). This
// module restates that content for the UI's benefit and can drift from it —
// if you change a stage's behavior, update README.md first and this file to
// match. The `id` of entries 1-8 below mirrors the `emit(...)` stage strings
// in `src/scoreocr/pipeline.py` exactly, so a future live view can index
// this list by the SSE `stage` field with no translation layer.

export const STAGES = [
  {
    id: "ingest",
    label: "Ingest",
    scope: "page",
    plain: "Your pages are loaded and prepared for scanning.",
    technical:
      "Normalizes every input into one grayscale PNG per page, preserving " +
      "input order. PDFs are rasterized at 300 DPI (pypdfium2); image " +
      "files are converted with Pillow. All pages of a single run form " +
      "one job / one song.",
  },
  {
    id: "geometry",
    label: "Geometry",
    scope: "page",
    plain: "The software finds the staff lines and measures on each page.",
    technical:
      "Pure OpenCV, no ML. Horizontal dark-pixel projections find staff " +
      "lines, which are grouped in fives and paired into grand-staff " +
      "systems; vertical projections find barlines, which delimit " +
      "measures. Measures are numbered absolutely and continuously " +
      "across systems and pages.",
  },
  {
    id: "crop",
    label: "Crop",
    scope: "page",
    plain: "Each line of music and each measure is cut out into its own small image.",
    technical:
      "Cuts a system image and a per-measure image for each detected " +
      "measure. The vertical span includes a margin above/below the " +
      "system so ledger lines survive the crop.",
  },
  {
    id: "interpret",
    label: "Interpret",
    scope: "page",
    plain: "An AI reads each measure and figures out the notes, rhythm, and other musical details.",
    technical:
      "The vision step, using Claude. One score-metadata call per page " +
      "(key, time signature, title), then one call per measure; each " +
      "measure call may zoom or use a grid overlay to look closer before " +
      "returning structured notes, chords, rests, rhythm, beams, ties, " +
      "tuplets, and dynamics. A measure whose durations don't sum to the " +
      "time signature is automatically re-interpreted once with that " +
      "discrepancy as feedback.",
  },
  {
    id: "assemble",
    label: "Assemble",
    scope: "page",
    plain: "The recognized notes are assembled into a real digital score file.",
    technical:
      "Deterministically serializes the interpreted measure data into " +
      "MusicXML 4.0: one piano part, two staves (treble and bass, with " +
      "a backup between them), DIVISIONS = 24 per quarter note. Produces " +
      "a consolidated score for the whole song plus a standalone " +
      "MusicXML file per page.",
  },
  {
    id: "validate",
    label: "Validate",
    scope: "page",
    plain: "The score is checked for mistakes, like measures that don't add up correctly.",
    technical:
      "Structural and rhythmic checks on the assembled score (lxml): " +
      "parseability, measure count and numbering continuity, per-voice " +
      "duration sums, grace-note handling, and the final barline. " +
      "Problems are reported, not fatal.",
  },
  {
    id: "render",
    label: "Render",
    scope: "page",
    plain: "A preview image of the finished sheet music is created so you can see it.",
    technical:
      "Verovio renders the MusicXML to SVG previews, honoring the " +
      "encoded system/page breaks so the layout tracks the source.",
  },
  {
    id: "selfcheck",
    label: "Self-check",
    scope: "page",
    optional: true,
    plain: "As an extra check, the AI compares the finished score against the original photo and fixes anything it got wrong.",
    technical:
      "Optional. Rasterizes each rendered system back to an image " +
      "(cairosvg) and asks Claude to compare it against the source crop. " +
      "Discrepant measures are bounced back through interpret → " +
      "assemble → render, up to 2 rounds. Remaining discrepancies are " +
      "reported.",
  },
  {
    id: "merge",
    label: "Merge",
    scope: "batch",
    plain: "Once all your pages are done, you can combine them into one continuous score.",
    technical:
      "Batch-level and user-triggered from the finished-pages UI " +
      "(merge_batch), not part of run_pipeline(). Combines the per-page " +
      "MusicXML of every successfully processed page in the batch into " +
      "one continuous score, renumbering measures across pages and " +
      "preserving page/system breaks. Emits no SSE stage event.",
  },
];

export const STAGE_IDS = STAGES.map((stage) => stage.id);

export function stageById(id) {
  return STAGES.find((stage) => stage.id === id);
}

export function stageIndex(id) {
  return STAGE_IDS.indexOf(id);
}

export function nextStage(id) {
  const index = stageIndex(id);
  if (index === -1 || index === STAGES.length - 1) return null;
  return STAGE_IDS[index + 1];
}

export function prevStage(id) {
  const index = stageIndex(id);
  if (index <= 0) return null;
  return STAGE_IDS[index - 1];
}
