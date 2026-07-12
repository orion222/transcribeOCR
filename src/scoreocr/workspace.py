import secrets
from datetime import datetime, timezone
from pathlib import Path

from scoreocr.models import JobState


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.job_id = self.root.name

    @classmethod
    def create(cls, jobs_root: Path) -> "Workspace":
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_id = f"{stamp}-{secrets.token_hex(2)}"
        root = Path(jobs_root) / job_id
        root.mkdir(parents=True)
        ws = cls(root)
        ws.save_state(JobState(job_id=job_id))
        return ws

    def load_state(self) -> JobState:
        return JobState.model_validate_json((self.root / "job.json").read_text())

    def save_state(self, state: JobState) -> None:
        (self.root / "job.json").write_text(state.model_dump_json(indent=2))

    def _ensured(self, p: Path) -> Path:
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def page_dir(self, page: str) -> Path:
        d = self.root / "pages" / page
        d.mkdir(parents=True, exist_ok=True)
        return d

    def source_path(self, page: str) -> Path:
        return self._ensured(self.page_dir(page) / "source.png")

    def geometry_path(self, page: str) -> Path:
        return self._ensured(self.page_dir(page) / "geometry.json")

    def crops_dir(self, page: str) -> Path:
        d = self.page_dir(page) / "crops"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def page_for_measure(self, number: int) -> str:
        for entry in self.load_state().pages:
            if entry.measure_start <= number <= entry.measure_end:
                return entry.page
        raise KeyError(f"no page contains measure {number}")

    def measure_ir_path(self, number: int) -> Path:
        page = self.page_for_measure(number)
        return self._ensured(self.page_dir(page) / "transcription" / f"m{number:03d}.json")

    def page_ir_paths(self, page: str) -> list[Path]:
        d = self.page_dir(page) / "transcription"
        return sorted(d.glob("m*.json")) if d.exists() else []

    @property
    def score_meta_path(self) -> Path:
        return self.root / "score-meta.json"

    @property
    def output_dir(self) -> Path:
        d = self.root / "output"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def page_output_dir(self, page: str) -> Path:
        d = self.page_dir(page) / "output"
        d.mkdir(parents=True, exist_ok=True)
        return d
