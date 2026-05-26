from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from fastapi import HTTPException

from api.errors import http_exception_detail
from domain.normalize_run import (
    ApiErrorDetail,
    ApiErrorReason,
    NormalizeRunJobRecord,
    NormalizeRunJobStatus,
    PipelineCaseStatusPayload,
    PipelineNormalizeRunJobResponse,
    PipelineNormalizeRunRequest,
    PipelineNormalizeRunResponse,
    PipelineNormalizeRunStatusResponse,
)
from repositories.normalize_run_jobs import NormalizeRunJobRepository

PipelineRunCallable = Callable[
    [PipelineNormalizeRunRequest, str | None],
    PipelineNormalizeRunResponse,
]

logger = logging.getLogger(__name__)


class NormalizeRunJobManager:
    _VALID_JOB_ID_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]+")
    _MAX_JOB_ID_LENGTH: ClassVar[int] = 160

    def __init__(
        self,
        *,
        repository: NormalizeRunJobRepository,
        cases_root: Path,
    ) -> None:
        self._repository: NormalizeRunJobRepository = repository
        self._cases_root: Path = cases_root

    def create_job(self, user_id: str | None) -> PipelineNormalizeRunJobResponse:
        job_id = self._make_job_id(user_id)
        now = self._now_utc_iso()
        _ = self._repository.create(
            NormalizeRunJobRecord(
                id=job_id,
                status="queued",
                stage="queued",
                message="Normalize-run job queued.",
                created_at_utc=now,
                updated_at_utc=now,
            )
        )
        urls = self._job_urls(job_id)
        return PipelineNormalizeRunJobResponse(
            id=job_id,
            status="queued",
            statusUrl=urls["statusUrl"],
            resultUrl=urls["resultUrl"],
        )

    def update(
        self,
        job_id: str,
        *,
        status: NormalizeRunJobStatus | None = None,
        stage: str | None = None,
        message: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        case_ids: list[str] | None = None,
        current_case_id: str | None = None,
        result_path: str | None = None,
        error: ApiErrorDetail | None = None,
    ) -> None:
        record = self._repository.get(job_id)
        if record is None:
            now = self._now_utc_iso()
            record = NormalizeRunJobRecord(
                id=job_id,
                status="queued",
                created_at_utc=now,
                updated_at_utc=now,
            )

        update_data = record.model_dump()
        if status is not None:
            update_data["status"] = status
        if stage is not None:
            update_data["stage"] = stage
        if message is not None:
            update_data["message"] = message
        if progress_current is not None:
            update_data["progress_current"] = progress_current
        if progress_total is not None:
            update_data["progress_total"] = progress_total
        if current_case_id is not None:
            update_data["current_case_id"] = current_case_id
        if result_path is not None:
            update_data["result_path"] = result_path
        if error is not None:
            update_data["error"] = error
        elif status != "error":
            update_data["error"] = None
        if case_ids is not None:
            update_data["case_ids"] = self._merge_case_ids(record.case_ids, case_ids)
        update_data["updated_at_utc"] = self._now_utc_iso()
        self._repository.save(NormalizeRunJobRecord.model_validate(update_data))

    def status_response(
        self,
        job_id: str,
    ) -> PipelineNormalizeRunStatusResponse | None:
        record = self._repository.get(job_id)
        if record is None:
            return None

        stage = record.stage
        message = record.message
        progress_current = record.progress_current
        progress_total = record.progress_total
        updated_at_utc = record.updated_at_utc
        active_case_id = record.current_case_id or (
            record.case_ids[-1] if record.case_ids else None
        )
        active_case_status = self._case_status(active_case_id)

        if record.status == "running" and stage == "running_pipeline":
            case_stage = active_case_status.get("stage")
            case_message = active_case_status.get("message")
            case_progress_current = active_case_status.get("progress_current")
            case_progress_total = active_case_status.get("progress_total")
            case_updated_at_utc = active_case_status.get("updated_at_utc")
            if isinstance(case_stage, str):
                stage = case_stage
            if isinstance(case_message, str):
                message = case_message
            if isinstance(case_progress_current, int):
                progress_current = case_progress_current
            if isinstance(case_progress_total, int):
                progress_total = case_progress_total
            if isinstance(case_updated_at_utc, str):
                updated_at_utc = case_updated_at_utc

        urls = self._job_urls(job_id)
        return PipelineNormalizeRunStatusResponse(
            id=record.id,
            status=record.status,
            stage=stage,
            message=message,
            progressCurrent=progress_current,
            progressTotal=progress_total,
            createdAtUtc=record.created_at_utc,
            updatedAtUtc=updated_at_utc,
            caseIds=record.case_ids,
            currentCaseId=active_case_id,
            error=record.error,
            statusUrl=urls["statusUrl"],
            resultUrl=urls["resultUrl"],
        )

    def read_result(self, job_id: str) -> PipelineNormalizeRunResponse | None:
        return self._repository.read_result(job_id)

    def is_valid_job_id(self, job_id: str) -> bool:
        return (
            bool(job_id)
            and len(job_id) <= self._MAX_JOB_ID_LENGTH
            and self._VALID_JOB_ID_RE.fullmatch(job_id) is not None
        )

    def run_job(
        self,
        job_id: str,
        request: PipelineNormalizeRunRequest,
        run_pipeline: PipelineRunCallable,
    ) -> None:
        try:
            self.update(
                job_id,
                status="running",
                stage="normalizing_input",
                message="Normalizing frontend room payload.",
            )
            response = run_pipeline(request, job_id)
            result_path = self._repository.write_result(job_id, response)
            self.update(
                job_id,
                status="ready",
                stage="ready",
                message="Normalize-run result ready.",
                result_path=str(result_path),
            )
        except HTTPException as exc:
            detail = http_exception_detail(exc)
            logger.warning(
                "normalize-run job failed: job_id=%s reason=%s",
                job_id,
                detail.reason,
            )
            self.update(
                job_id,
                status="error",
                stage="error",
                message=detail.message,
                error=detail,
            )
        except Exception as exc:
            logger.exception("normalize-run job crashed: job_id=%s", job_id)
            self.update(
                job_id,
                status="error",
                stage="error",
                message="Normalize-run job failed.",
                error=ApiErrorDetail(
                    reason=ApiErrorReason.NORMALIZE_RUN_JOB_FAILED,
                    message=str(exc),
                    context={"error_type": type(exc).__name__},
                ),
            )

    def _case_status(self, case_id: str | None) -> dict[str, str | int]:
        if case_id is None:
            return {}
        path = self._cases_root / case_id / "status.json"
        if not path.exists():
            return {}
        try:
            payload = PipelineCaseStatusPayload.model_validate_json(path.read_text())
        except (OSError, ValueError):
            return {}

        out: dict[str, str | int] = {}
        if payload.stage is not None:
            out["stage"] = payload.stage
        if payload.message is not None:
            out["message"] = payload.message
        if payload.updated_at_utc is not None:
            out["updated_at_utc"] = payload.updated_at_utc
        if payload.progress_current is not None:
            out["progress_current"] = int(payload.progress_current)
        if payload.progress_total is not None:
            out["progress_total"] = int(payload.progress_total)
        return out

    @staticmethod
    def _job_urls(job_id: str) -> dict[str, str]:
        return {
            "statusUrl": f"/pipeline/normalize-run/{job_id}/status",
            "resultUrl": f"/pipeline/normalize-run/{job_id}/result",
        }

    @staticmethod
    def _make_job_id(user_id: str | None) -> str:
        safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", user_id or "normalize_run")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"{safe_user}_{timestamp}_{uuid4().hex[:12]}"

    @staticmethod
    def _merge_case_ids(existing: list[str], new_case_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for case_id in [*existing, *new_case_ids]:
            if not case_id or case_id in seen:
                continue
            seen.add(case_id)
            merged.append(case_id)
        return merged

    @staticmethod
    def _now_utc_iso() -> str:
        return datetime.now(UTC).isoformat()
