import asyncio
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from scoreocr.web.batch import BatchStore
from scoreocr.web.broker import EventBroker
from scoreocr.web.runner import run_batch


class CreateBatchBody(BaseModel):
    self_check: bool = False
    meta: dict = {}


def _default_build_interpreter():
    from scoreocr.cli import build_interpreter
    return build_interpreter()


def create_app(jobs_root: Path, build_interpreter=_default_build_interpreter) -> FastAPI:
    app = FastAPI(title="scoreocr")
    store = BatchStore(Path(jobs_root))
    broker = EventBroker()
    app.state.store = store
    app.state.broker = broker
    # NOTE: the broker's event loop is bound lazily in the SSE events handler
    # (Task 9), so it works under Starlette's TestClient without a context
    # manager and avoids the deprecated on_event("startup") hook.

    @app.post("/api/batches")
    def create_batch(body: CreateBatchBody):
        meta = {k: v for k, v in body.meta.items() if v not in (None, "")}
        m = store.create(self_check=body.self_check, meta_overrides=meta)
        return {"batch_id": m.batch_id}

    @app.post("/api/batches/{bid}/photos")
    async def add_photos(bid: str, files: list[UploadFile]):
        _require(store, bid)
        refs = []
        for f in files:
            suffix = Path(f.filename or "upload.png").suffix.lower() or ".png"
            data = await f.read()
            refs.append(store.add_photo(bid, f.filename or "upload.png", data, suffix))
        return {"photos": [r.model_dump() for r in refs]}

    @app.post("/api/batches/{bid}/start")
    def start(bid: str):
        _require(store, bid)
        thread = threading.Thread(
            target=run_batch, args=(store, broker, bid, build_interpreter),
            daemon=True,
        )
        thread.start()
        return {"status": "processing"}

    @app.get("/api/batches/{bid}")
    def snapshot(bid: str):
        return JSONResponse(_require(store, bid).model_dump())

    return app


def _require(store: BatchStore, bid: str):
    try:
        return store.load(bid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown batch {bid}")
