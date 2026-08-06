import json
import os
from pathlib import Path

import pytest
from PIL import Image

import scoreocr.cli as cli
from scoreocr.claude.interpreter import Interpreter
from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.openrouter import OpenRouterClient


class StubInterpreter(Interpreter):
    def __init__(self):
        super().__init__(client=None)

    def read_score_meta(self, page_image):
        return ScoreMeta(), {"input_tokens": 0, "output_tokens": 0}

    def interpret_measure(self, ctx):
        ir = MeasureIR(number=ctx.number, confidence=0.9, voices={
            "treble": [Event(kind="note", duration=96, note_type="whole",
                             pitches=[Pitch(step="C", octave=5)])],
            "bass": [Event(kind="rest", duration=96, note_type="whole")]})
        return ir, {"input_tokens": 0, "output_tokens": 0}


def test_end_to_end(tmp_path, synthetic_page, monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_interpreter", lambda *_: StubInterpreter())
    code = cli.main([
        "run", str(synthetic_page), "--jobs-root", str(tmp_path / "jobs"),
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "score.musicxml" in out
    jobs = list((tmp_path / "jobs").iterdir())
    assert len(jobs) == 1
    score = jobs[0] / "output" / "score.musicxml"
    assert score.exists()
    previews = list((jobs[0] / "output" / "preview").glob("*.svg"))
    assert previews


def test_stage_failure_marks_job_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_interpreter", lambda *_: StubInterpreter())
    blank = tmp_path / "blank.png"
    Image.new("L", (400, 300), color=255).save(blank)  # no staff lines at all

    code = cli.main([
        "run", str(blank), "--jobs-root", str(tmp_path / "jobs"),
    ])
    assert code == 1

    jobs = list((tmp_path / "jobs").iterdir())
    assert len(jobs) == 1
    state = json.loads((jobs[0] / "job.json").read_text())
    assert state["status"] == "failed:geometry"
    assert state["error"]


def test_interpreter_build_failure_marks_failed_startup(tmp_path, synthetic_page, monkeypatch):
    def boom(*_):
        raise RuntimeError("no OPENROUTER_API_KEY")
    monkeypatch.setattr(cli, "build_interpreter", boom)

    code = cli.main([
        "run", str(synthetic_page), "--jobs-root", str(tmp_path / "jobs"),
    ])
    assert code == 1

    jobs = list((tmp_path / "jobs").iterdir())
    assert len(jobs) == 1
    state = json.loads((jobs[0] / "job.json").read_text())
    assert state["status"] == "failed:startup"
    assert state["error"]


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #

@pytest.fixture
def clean_env(monkeypatch):
    """Isolate provider resolution from the developer's real environment.

    build_interpreter() calls load_dotenv(), which would otherwise pull a real
    .env into these assertions.
    """
    import dotenv

    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                 "SCOREOCR_PROVIDER", "SCOREOCR_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: False)


def test_defaults_to_openrouter(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    interpreter = cli.build_interpreter()
    assert isinstance(interpreter.client, OpenRouterClient)
    assert interpreter.model == "anthropic/claude-opus-4.5"


def test_model_override_reaches_both_client_and_interpreter(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    interpreter = cli.build_interpreter(model="google/gemini-3-pro")
    assert interpreter.model == "google/gemini-3-pro"
    assert interpreter.client.model == "google/gemini-3-pro"


def test_env_selects_provider_and_model(clean_env, monkeypatch):
    monkeypatch.setenv("SCOREOCR_PROVIDER", "anthropic")
    monkeypatch.setenv("SCOREOCR_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert cli.build_interpreter().model == "claude-sonnet-4-6"


def test_flag_beats_env(clean_env, monkeypatch):
    monkeypatch.setenv("SCOREOCR_PROVIDER", "anthropic")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert isinstance(cli.build_interpreter("openrouter").client, OpenRouterClient)


def test_falls_back_to_anthropic_when_openrouter_key_missing(clean_env, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    interpreter = cli.build_interpreter()
    assert not isinstance(interpreter.client, OpenRouterClient)
    assert interpreter.model == cli._default_anthropic_model()
    assert "falling back to the anthropic provider" in capsys.readouterr().err


def test_fallback_drops_an_openrouter_namespaced_model(clean_env, monkeypatch):
    """"vendor/model" ids mean nothing to the Anthropic API."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SCOREOCR_MODEL", "google/gemini-3-pro")
    assert cli.build_interpreter().model == cli._default_anthropic_model()


def test_fallback_keeps_a_bare_model_id(clean_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert cli.build_interpreter(model="claude-sonnet-4-6").model == "claude-sonnet-4-6"


def test_explicit_anthropic_rejects_an_openrouter_namespaced_model(clean_env, monkeypatch):
    """.env.example suggests SCOREOCR_MODEL=anthropic/claude-opus-4.5; combined
    with --provider anthropic that id would 404, so fail with a clear message
    instead of silently rewriting the model the user named."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SCOREOCR_MODEL", "anthropic/claude-opus-4.5")
    with pytest.raises(RuntimeError, match="looks like an OpenRouter id"):
        cli.build_interpreter("anthropic")


def test_explicit_openrouter_never_falls_back(clean_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
        cli.build_interpreter("openrouter")


def test_no_keys_at_all_reports_openrouter(clean_env):
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
        cli.build_interpreter()


def test_unknown_provider_is_rejected(clean_env, monkeypatch):
    monkeypatch.setenv("SCOREOCR_PROVIDER", "hotdog")
    with pytest.raises(RuntimeError, match="unknown provider 'hotdog'"):
        cli.build_interpreter()


def test_serve_reload_passes_an_import_string_and_exports_config(tmp_path, monkeypatch):
    """Reload spawns a child that re-imports the app, so it cannot take an
    instance, and the CLI's arguments have to reach it as environment."""
    import uvicorn

    seen = {}
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, **kw: seen.update(app=app, **kw))
    monkeypatch.delenv("SCOREOCR_MODEL", raising=False)

    cli.main([
        "serve", "--reload", "--jobs-root", str(tmp_path / "jobs"),
        "--model", "google/gemini-3-pro-preview",
    ])

    assert seen["app"] == "scoreocr.web.app:app_from_env"
    assert seen["factory"] is True and seen["reload"] is True
    # Watching the cwd would rebuild on every file a running job writes.
    assert seen["reload_dirs"] == [str(Path(cli.__file__).resolve().parent)]
    assert os.environ["SCOREOCR_JOBS_ROOT"] == str(tmp_path / "jobs")
    assert os.environ["SCOREOCR_MODEL"] == "google/gemini-3-pro-preview"


def test_serve_without_reload_passes_the_app_instance(tmp_path, monkeypatch):
    import uvicorn
    from fastapi import FastAPI

    seen = {}
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, **kw: seen.update(app=app, **kw))
    monkeypatch.setattr(cli, "build_interpreter", lambda *a: StubInterpreter())

    cli.main(["serve", "--jobs-root", str(tmp_path / "jobs")])

    assert isinstance(seen["app"], FastAPI)
    assert "reload" not in seen


def test_provider_flags_are_parsed_and_forwarded(tmp_path, synthetic_page, monkeypatch):
    seen = {}

    def capture(provider, model):
        seen.update(provider=provider, model=model)
        return StubInterpreter()

    monkeypatch.setattr(cli, "build_interpreter", capture)
    cli.main([
        "run", str(synthetic_page), "--jobs-root", str(tmp_path / "jobs"),
        "--provider", "anthropic", "--model", "claude-sonnet-4-6",
    ])
    assert seen == {"provider": "anthropic", "model": "claude-sonnet-4-6"}
