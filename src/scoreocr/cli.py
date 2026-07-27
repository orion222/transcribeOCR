import argparse
import os
import sys
from pathlib import Path

from scoreocr.pipeline import run_pipeline
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


def _run(args) -> int:
    ws = Workspace.create(args.jobs_root)
    print(f"job: {ws.root}")
    try:
        interpreter = build_interpreter()
    except Exception as exc:
        state = ws.load_state()
        state.status = "failed:startup"
        state.error = str(exc)
        ws.save_state(state)
        print(f"error: failed:startup: {exc}", file=sys.stderr)
        return 1
    result = run_pipeline(
        ws, interpreter, args.pages,
        self_check=args.self_check, max_workers=args.max_workers,
    )
    if result.status.startswith("failed:"):
        print(f"error: {result.status}: {result.error}", file=sys.stderr)
        return 1
    for issue in result.issues:
        print(f"VALIDATION [{issue.code}] measure {issue.measure}: {issue.message}",
              file=sys.stderr)
    print(f"score:    {ws.output_dir / 'score.musicxml'}")
    for entry in ws.load_state().pages:
        print(f"page {entry.page}: {ws.page_output_dir(entry.page) / 'page.musicxml'}")
    print(f"previews: {ws.output_dir / 'preview'}")
    return 1 if result.issues else 0


def _serve(args) -> int:
    import uvicorn

    from scoreocr.web.app import create_app

    app = create_app(args.jobs_root, build_interpreter=build_interpreter)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="score-transcribe")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="transcribe pages into MusicXML")
    run.add_argument("pages", nargs="+", type=Path)
    run.add_argument("--jobs-root", type=Path, default=Path("data/jobs"))
    run.add_argument("--self-check", action="store_true")
    run.add_argument("--max-workers", type=int, default=4)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--jobs-root", type=Path, default=Path("data/jobs"))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "serve":
        return _serve(args)
    parser.error(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
