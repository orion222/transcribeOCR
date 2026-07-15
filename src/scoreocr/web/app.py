import asyncio
import json as _json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
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

    @app.get("/api/batches/{bid}/events")
    async def events(bid: str, request: Request):
        # Bind the broker to the loop actually serving requests. Idempotent
        # (same loop under uvicorn/TestClient); guarantees worker-thread
        # publishes reach subscribers without a startup hook.
        broker.bind_loop(asyncio.get_running_loop())
        manifest = _require(store, bid)
        queue = broker.subscribe(bid)

        async def gen():
            try:
                yield f"event: snapshot\ndata: {manifest.model_dump_json()}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"event: message\ndata: {_json.dumps(event)}\n\n"
                    if event.get("type") == "batch" and event.get("status") == "complete":
                        break
            finally:
                broker.unsubscribe(bid, queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def _require(store: BatchStore, bid: str):
    try:
        return store.load(bid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown batch {bid}")
