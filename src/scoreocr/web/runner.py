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
    manifest = store.load(batch_id)
    ref = _find(manifest, photo_id)
    ref.status = "processing"
    ref.stage = "ingest"
    ref.error = None
    store.save(manifest)
    broker.publish(batch_id, _photo_event(ref))

    ws = store.workspace(batch_id, ref.job_id)
    input_path = store.input_path(batch_id, ref)
    last_stage = {"value": "ingest"}

    def on_progress(ev: ProgressEvent) -> None:
        current = store.load(batch_id)
        pref = _find(current, photo_id)
        pref.stage = ev.stage
        pref.measures_done = ev.measures_done
        pref.measures_total = ev.measures_total
        # persist only on stage transitions to avoid per-measure disk churn
        if ev.stage != last_stage["value"]:
            last_stage["value"] = ev.stage
            store.save(current)
        broker.publish(batch_id, _photo_event(pref))

    result = run_pipeline(
        ws, interpreter, [input_path],
        self_check=manifest.self_check, on_progress=on_progress,
    )

    current = store.load(batch_id)
    pref = _find(current, photo_id)
    pref.status = "done" if result.status == "done" else result.status
    pref.error = result.error
    store.save(current)
    broker.publish(batch_id, _photo_event(pref))


def run_batch(store: BatchStore, broker: EventBroker, batch_id: str,
              build_interpreter) -> None:
    manifest = store.load(batch_id)
    manifest.status = "processing"
    store.save(manifest)
    broker.publish(batch_id, {"type": "batch", "status": "processing"})

    interpreter = build_interpreter()
    for ref in sorted(store.load(batch_id).photos, key=lambda p: p.order):
        try:
            process_photo(store, broker, batch_id, ref.photo_id, interpreter)
        except Exception as exc:  # a single photo's failure never aborts the batch
            current = store.load(batch_id)
            pref = _find(current, ref.photo_id)
            pref.status = "failed:runner"
            pref.error = str(exc)
            store.save(current)
            broker.publish(batch_id, _photo_event(pref))

    manifest = store.load(batch_id)
    manifest.status = "complete"
    store.save(manifest)
    broker.publish(batch_id, {"type": "batch", "status": "complete"})
