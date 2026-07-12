import argparse
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

    from scoreocr.claude.interpreter import Interpreter

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

    interpreter = build_interpreter()
    run_ingest(ws, args.pages)
    run_geometry(ws)
    run_crop(ws)
    run_interpret(ws, interpreter, max_workers=args.max_workers)
    run_assemble(ws)

    meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
    state = ws.load_state()
    expected = list(range(state.pages[0].measure_start, state.pages[-1].measure_end + 1))
    issues = validate_musicxml(
        (ws.output_dir / "score.musicxml").read_bytes(), meta, expected)
    for issue in issues:
        print(f"VALIDATION [{issue.code}] measure {issue.measure}: {issue.message}",
              file=sys.stderr)

    run_render(ws)
    if args.self_check:
        remaining = run_selfcheck(ws, interpreter)
        for d in remaining:
            print(f"SELF-CHECK m{d.measure} ({d.staff}): {d.description}",
                  file=sys.stderr)

    print(f"score:    {ws.output_dir / 'score.musicxml'}")
    for entry in ws.load_state().pages:
        print(f"page {entry.page}: {ws.page_output_dir(entry.page) / 'page.musicxml'}")
    print(f"previews: {ws.output_dir / 'preview'}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
