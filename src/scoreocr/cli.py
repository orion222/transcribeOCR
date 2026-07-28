import argparse
import os
import sys
from functools import partial
from pathlib import Path

from scoreocr.pipeline import run_pipeline
from scoreocr.workspace import Workspace

PROVIDERS = ("openrouter", "anthropic")
DEFAULT_PROVIDER = "openrouter"


def _default_anthropic_model() -> str:
    from scoreocr.claude.interpreter import MODEL

    return MODEL


def _build_anthropic(model: str | None):
    import anthropic

    from scoreocr.claude.interpreter import Interpreter

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key, or export ANTHROPIC_API_KEY in your shell."
        )
    if model and "/" in model:
        # "vendor/model" is OpenRouter's namespace; the Anthropic API would just
        # 404 on it. Fail here naming both, rather than silently rewriting a
        # model the user asked for by name.
        raise RuntimeError(
            f"model {model!r} looks like an OpenRouter id, but the anthropic "
            f"provider was selected. Use a bare Anthropic model id (e.g. "
            f"{_default_anthropic_model()}), or switch to --provider openrouter."
        )
    return Interpreter(anthropic.Anthropic(), model=model or _default_anthropic_model())


def _build_openrouter(model: str | None):
    from scoreocr.claude.interpreter import Interpreter
    from scoreocr.openrouter import DEFAULT_MODEL, OpenRouterClient

    model = model or DEFAULT_MODEL
    return Interpreter(OpenRouterClient(model=model), model=model)


def build_interpreter(provider: str | None = None, model: str | None = None):
    """Construct an Interpreter for the selected provider.

    OpenRouter is the default because it fronts every model worth pointing at
    this pipeline. `--provider` / `--model` win over `SCOREOCR_PROVIDER` /
    `SCOREOCR_MODEL`, which win over these defaults.
    """
    from dotenv import load_dotenv

    # Load API keys from a .env file in the project root if present. Real shell
    # environment variables take precedence — load_dotenv does not override
    # what is already set.
    load_dotenv()

    requested = provider or os.environ.get("SCOREOCR_PROVIDER")
    resolved = (requested or DEFAULT_PROVIDER).lower()
    model = model or os.environ.get("SCOREOCR_MODEL") or None
    if resolved not in PROVIDERS:
        raise RuntimeError(
            f"unknown provider {resolved!r}; expected one of {', '.join(PROVIDERS)}."
        )

    if resolved == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        # Only fall back when openrouter was the default rather than a choice —
        # an explicit --provider openrouter should fail loudly instead.
        if requested is None and os.environ.get("ANTHROPIC_API_KEY"):
            # An OpenRouter-namespaced model id ("vendor/model") is meaningless
            # to the Anthropic API, so drop it rather than pass it through.
            carried = model if model and "/" not in model else None
            print(
                "warning: OPENROUTER_API_KEY is not set; falling back to the "
                f"anthropic provider (model {carried or _default_anthropic_model()}). "
                "Set OPENROUTER_API_KEY, or pass --provider anthropic to silence this.",
                file=sys.stderr,
            )
            return _build_anthropic(carried)
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
            "your key, export OPENROUTER_API_KEY in your shell, or pass "
            "--provider anthropic to use the Anthropic API directly."
        )

    if resolved == "openrouter":
        return _build_openrouter(model)
    return _build_anthropic(model)


def _add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider", choices=PROVIDERS, default=None,
        help=f"inference provider (default: {DEFAULT_PROVIDER}, or $SCOREOCR_PROVIDER)",
    )
    parser.add_argument(
        "--model", default=None,
        help="model id for the chosen provider (default: $SCOREOCR_MODEL, "
             "else the provider default)",
    )


def _run(args) -> int:
    ws = Workspace.create(args.jobs_root)
    print(f"job: {ws.root}")
    try:
        interpreter = build_interpreter(args.provider, args.model)
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

    app = create_app(
        args.jobs_root,
        build_interpreter=partial(build_interpreter, args.provider, args.model),
    )
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
    _add_provider_args(run)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--jobs-root", type=Path, default=Path("data/jobs"))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    _add_provider_args(serve)

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "serve":
        return _serve(args)
    parser.error(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
