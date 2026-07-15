import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from scoreocr.models import ScoreMeta
from scoreocr.workspace import Workspace


class PhotoRef(BaseModel):
    photo_id: str
    job_id: str
    source_name: str
    input_name: str
    order: int
    status: str = "queued"
    stage: str = ""
    measures_done: int = 0
    measures_total: int = 0
    error: str | None = None


class BatchManifest(BaseModel):
    batch_id: str
    status: str = "created"
    self_check: bool = False
    meta_overrides: dict = Field(default_factory=dict)
    photos: list[PhotoRef] = Field(default_factory=list)


class BatchStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, batch_id: str) -> Path:
        return self.root / batch_id

    def _manifest_path(self, batch_id: str) -> Path:
        return self._dir(batch_id) / "batch.json"

    def _photos_root(self, batch_id: str) -> Path:
        d = self._dir(batch_id) / "photos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def merged_dir(self, batch_id: str) -> Path:
        d = self._dir(batch_id) / "merged"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def create(self, *, self_check: bool = False, meta_overrides: dict | None = None) -> BatchManifest:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        batch_id = f"batch-{stamp}-{secrets.token_hex(2)}"
        self._dir(batch_id).mkdir(parents=True)
        m = BatchManifest(batch_id=batch_id, self_check=self_check,
                          meta_overrides=meta_overrides or {})
        self.save(m)
        return m

    def save(self, m: BatchManifest) -> None:
        path = self._manifest_path(m.batch_id)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(m.model_dump_json(indent=2))
        os.replace(tmp, path)

    def load(self, batch_id: str) -> BatchManifest:
        return BatchManifest.model_validate_json(self._manifest_path(batch_id).read_text())

    def add_photo(self, batch_id: str, source_name: str, data: bytes, suffix: str) -> PhotoRef:
        m = self.load(batch_id)
        order = len(m.photos) + 1
        ws = Workspace.create(self._photos_root(batch_id))
        input_name = f"input{suffix or '.png'}"
        (ws.root / input_name).write_bytes(data)
        if m.meta_overrides:
            merged = {**ScoreMeta().model_dump(), **m.meta_overrides}
            ws.score_meta_path.write_text(ScoreMeta(**merged).model_dump_json(indent=2))
        ref = PhotoRef(photo_id=f"ph{order:02d}", job_id=ws.job_id,
                       source_name=source_name, input_name=input_name, order=order)
        m.photos.append(ref)
        self.save(m)
        return ref

    def workspace(self, batch_id: str, job_id: str) -> Workspace:
        return Workspace(self._photos_root(batch_id) / job_id)

    def input_path(self, batch_id: str, ref: PhotoRef) -> Path:
        return self.workspace(batch_id, ref.job_id).root / ref.input_name
