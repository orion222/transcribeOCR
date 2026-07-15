import asyncio
import json as _json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from scoreocr.web.audio import musicxml_to_midi
from scoreocr.web.batch import BatchStore
from scoreocr.web.broker import EventBroker
from scoreocr.web.merge import merge_batch
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
                if manifest.status == "complete":
                    return
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

    def _photo_ref(bid: str, pid: str):
        manifest = _require(store, bid)
        try:
            return manifest, next(p for p in manifest.photos if p.photo_id == pid)
        except StopIteration:
            raise HTTPException(status_code=404, detail=f"unknown photo {pid}")

    @app.get("/api/batches/{bid}/photos/{pid}/musicxml")
    def photo_musicxml(bid: str, pid: str):
        _, ref = _photo_ref(bid, pid)
        path = store.workspace(bid, ref.job_id).output_dir / "score.musicxml"
        if not path.exists():
            raise HTTPException(status_code=404, detail="not transcribed yet")
        return FileResponse(path, media_type="application/vnd.recordare.musicxml+xml",
                            filename=f"{ref.source_name}.musicxml")

    @app.get("/api/batches/{bid}/photos/{pid}/preview")
    def photo_preview(bid: str, pid: str):
        _, ref = _photo_ref(bid, pid)
        preview = store.workspace(bid, ref.job_id).output_dir / "preview"
        svgs = [p.read_text() for p in sorted(preview.glob("*.svg"))]
        return {"svgs": svgs}

    @app.get("/api/batches/{bid}/photos/{pid}/midi")
    def photo_midi(bid: str, pid: str):
        _, ref = _photo_ref(bid, pid)
        path = store.workspace(bid, ref.job_id).output_dir / "score.musicxml"
        if not path.exists():
            raise HTTPException(status_code=404, detail="not transcribed yet")
        return Response(musicxml_to_midi(path.read_text()), media_type="audio/midi")

    @app.post("/api/batches/{bid}/photos/{pid}/retry")
    def retry_photo(bid: str, pid: str):
        _photo_ref(bid, pid)

        def _work():
            from scoreocr.web.runner import process_photo
            interpreter = build_interpreter()
            process_photo(store, broker, bid, pid, interpreter)
            current = store.load(bid)
            if all(p.status == "done" or p.status.startswith("failed:")
                   for p in current.photos):
                current.status = "complete"
                store.save(current)
                broker.publish(bid, {"type": "batch", "status": "complete"})

        threading.Thread(target=_work, daemon=True).start()
        return {"status": "processing"}

    @app.post("/api/batches/{bid}/merge")
    def merge(bid: str):
        _require(store, bid)
        try:
            merge_batch(store, bid)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        svgs = list((store.merged_dir(bid) / "preview").glob("*.svg"))
        return {"musicxml_url": f"/api/batches/{bid}/merged/musicxml",
                "svg_count": len(svgs)}

    @app.get("/api/batches/{bid}/merged/musicxml")
    def merged_musicxml(bid: str):
        path = store.merged_dir(bid) / "score.musicxml"
        if not path.exists():
            raise HTTPException(status_code=404, detail="not merged yet")
        return FileResponse(path, media_type="application/vnd.recordare.musicxml+xml",
                            filename="merged.musicxml")

    @app.get("/api/batches/{bid}/merged/preview")
    def merged_preview(bid: str):
        preview = store.merged_dir(bid) / "preview"
        return {"svgs": [p.read_text() for p in sorted(preview.glob("*.svg"))]}

    @app.get("/api/batches/{bid}/merged/midi")
    def merged_midi(bid: str):
        path = store.merged_dir(bid) / "score.musicxml"
        if not path.exists():
            raise HTTPException(status_code=404, detail="not merged yet")
        return Response(musicxml_to_midi(path.read_text()), media_type="audio/midi")

    return app


def _require(store: BatchStore, bid: str):
    try:
        return store.load(bid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown batch {bid}")
