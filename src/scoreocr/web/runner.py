from scoreocr.pipeline import ProgressEvent, run_pipeline
from scoreocr.web.batch import BatchStore
from scoreocr.web.broker import EventBroker


def _find(manifest, photo_id):
    return next(p for p in manifest.photos if p.photo_id == photo_id)


def _photo_event(ref) -> dict:
    return {
        "type": "photo",
        "photo_id": ref.photo_id,
        "status": ref.status,
        "stage": ref.stage,
        "measures_done": ref.measures_done,
        "measures_total": ref.measures_total,
        "error": ref.error,
    }


def process_photo(store: BatchStore, broker: EventBroker, batch_id: str,
                  photo_id: str, interpreter) -> None:
    def _start(m):
        ref = _find(m, photo_id)
        ref.status = "processing"
        ref.stage = "ingest"
        ref.error = None

    manifest = store.update(batch_id, _start)
    ref = _find(manifest, photo_id)
    broker.publish(batch_id, _photo_event(ref))

    ws = store.workspace(batch_id, ref.job_id)
    input_path = store.input_path(batch_id, ref)
    self_check = manifest.self_check
    last_stage = {"value": "ingest"}

    def on_progress(ev: ProgressEvent) -> None:
        # Persist only on stage transitions (avoid per-measure disk churn),
        # but publish every tick over SSE.
        if ev.stage != last_stage["value"]:
            last_stage["value"] = ev.stage

            def _tick(m):
                pref = _find(m, photo_id)
                pref.stage = ev.stage
                pref.measures_done = ev.measures_done
                pref.measures_total = ev.measures_total

            updated = store.update(batch_id, _tick)
            broker.publish(batch_id, _photo_event(_find(updated, photo_id)))
        else:
            broker.publish(batch_id, {
                "type": "photo", "photo_id": photo_id, "status": "processing",
                "stage": ev.stage, "measures_done": ev.measures_done,
                "measures_total": ev.measures_total, "error": None})

    result = run_pipeline(
        ws, interpreter, [input_path],
        self_check=self_check, on_progress=on_progress,
    )

    def _final(m):
        pref = _find(m, photo_id)
        pref.status = result.status
        pref.error = result.error

    updated = store.update(batch_id, _final)
    broker.publish(batch_id, _photo_event(_find(updated, photo_id)))


def run_batch(store: BatchStore, broker: EventBroker, batch_id: str,
              build_interpreter) -> None:
    store.update(batch_id, lambda m: setattr(m, "status", "processing"))
    broker.publish(batch_id, {"type": "batch", "status": "processing"})

    interpreter = build_interpreter()
    for ref in sorted(store.load(batch_id).photos, key=lambda p: p.order):
        try:
            process_photo(store, broker, batch_id, ref.photo_id, interpreter)
        except Exception as exc:  # a single photo's failure never aborts the batch
            def _fail(m, pid=ref.photo_id, err=str(exc)):
                pref = _find(m, pid)
                pref.status = "failed:runner"
                pref.error = err

            updated = store.update(batch_id, _fail)
            broker.publish(batch_id, _photo_event(_find(updated, ref.photo_id)))

    store.update(batch_id, lambda m: setattr(m, "status", "complete"))
    broker.publish(batch_id, {"type": "batch", "status": "complete"})
