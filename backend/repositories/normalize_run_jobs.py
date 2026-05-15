from __future__ import annotations

import json
from pathlib import Path

from domain.normalize_run import (
    NormalizeRunJobRecord,
    PipelineNormalizeRunResponse,
)


class NormalizeRunJobRepository:
    def __init__(self, root: Path) -> None:
        self._root: Path = root

    def exists(self, job_id: str) -> bool:
        return self._meta_path(job_id).exists()

    def create(self, record: NormalizeRunJobRecord) -> NormalizeRunJobRecord:
        self.save(record)
        return record

    def get(self, job_id: str) -> NormalizeRunJobRecord | None:
        path = self._meta_path(job_id)
        if not path.exists():
            return None
        try:
            return NormalizeRunJobRecord.model_validate_json(path.read_text())
        except (OSError, ValueError):
            return None

    def save(self, record: NormalizeRunJobRecord) -> None:
        self._write_json(self._meta_path(record.id), record.model_dump(mode="json"))

    def write_result(
        self,
        job_id: str,
        response: PipelineNormalizeRunResponse,
    ) -> Path:
        path = self.result_path(job_id)
        self._write_json(path, response.model_dump(mode="json"))
        return path

    def read_result(self, job_id: str) -> PipelineNormalizeRunResponse | None:
        path = self.result_path(job_id)
        if not path.exists():
            return None
        try:
            return PipelineNormalizeRunResponse.model_validate_json(path.read_text())
        except (OSError, ValueError):
            return None

    def result_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "result.json"

    def _meta_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "job.json"

    def _job_root(self, job_id: str) -> Path:
        return self._root / job_id

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        _ = temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        _ = temp_path.replace(path)
