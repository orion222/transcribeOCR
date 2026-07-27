import argparse
import os
import sys
from pathlib import Path

from scoreocr.models import ScoreMeta
from scoreocr.stages.assemble import run_assemble
from scoreocr.stages.crop import run_crop
from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.ingest import run_ingest
from scoreocr.stages.interpret import run_interpret
from scoreocr.stages.render import run_render
from scoreocr.stages.selfcheck import run_selfcheck
from scoreocr.stages.validate import validate_musicxml
from scoreocr.workspace import Workspace


def build_interpreter():
    import anthropic
    from dotenv import load_dotenv

    from scoreocr.claude.interpreter import Interpreter

    # Load ANTHROPIC_API_KEY (and any other vars) from a .env file in the
    # project root if present. Real shell environment variables take
    # precedence — load_dotenv does not override what is already set.
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key, or export ANTHROPIC_API_KEY in your shell."
        )
    return Interpreter(anthropic.Anthropic())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="score-transcribe")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="transcribe pages into MusicXML")
    run.add_argument("pages", nargs="+", type=Path)
    run.add_argument("--jobs-root", type=Path, default=Path("data/jobs"))
    run.add_argument("--self-check", action="store_true")
    run.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)

    ws = Workspace.create(args.jobs_root)
    print(f"job: {ws.root}")
    state = ws.load_state()
    state.self_check = args.self_check
    ws.save_state(state)

    stage = "startup"
    try:
        interpreter = build_interpreter()

        stage = "ingest"
        run_ingest(ws, args.pages)
        stage = "geometry"
        run_geometry(ws)
        stage = "crop"
        run_crop(ws)
        stage = "interpret"
        run_interpret(ws, interpreter, max_workers=args.max_workers)
        stage = "assemble"
        run_assemble(ws)

        stage = "validate"
        meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
        state = ws.load_state()
        expected = list(range(state.pages[0].measure_start, state.pages[-1].measure_end + 1))
        issues = validate_musicxml(
            (ws.output_dir / "score.musicxml").read_bytes(), meta, expected)
        for issue in issues:
            print(f"VALIDATION [{issue.code}] measure {issue.measure}: {issue.message}",
                  file=sys.stderr)

        stage = "render"
        run_render(ws)
        if args.self_check:
            stage = "selfcheck"
            remaining = run_selfcheck(ws, interpreter)
            for d in remaining:
                print(f"SELF-CHECK m{d.measure} ({d.staff}): {d.description}",
                      file=sys.stderr)
    except Exception as exc:
        # A failing stage marks the job failed:<stage> rather than crashing
        # with a raw traceback; the caller can inspect job.json for details.
        state = ws.load_state()
        state.status = f"failed:{stage}"
        state.error = str(exc)
        ws.save_state(state)
        print(f"error: stage '{stage}' failed: {exc}", file=sys.stderr)
        return 1

    print(f"score:    {ws.output_dir / 'score.musicxml'}")
    for entry in ws.load_state().pages:
        print(f"page {entry.page}: {ws.page_output_dir(entry.page) / 'page.musicxml'}")
    print(f"previews: {ws.output_dir / 'preview'}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
