from __future__ import annotations

import logging
from collections.abc import Callable

from adapters.pydantic_ai_agents import PydanticAIAgentFactory
from config import root_config
from domain.normalize_run import (
    PipelineNormalizeRunJobResponse,
    PipelineNormalizeRunRequest,
    PipelineNormalizeRunResponse,
    PipelineNormalizeRunStatusResponse,
)
from managers.normalize_run_jobs import NormalizeRunJobManager
from services.coordinate_normalization_service import CoordinateNormalizationService

logger = logging.getLogger(__name__)


class NormalizeRunPipelineService:
    def __init__(
        self,
        *,
        job_manager: NormalizeRunJobManager,
        coordinate_service: CoordinateNormalizationService,
        pipeline_executor: Callable[
            [PipelineNormalizeRunRequest, str | None],
            PipelineNormalizeRunResponse,
        ],
        ai_agent_factory: PydanticAIAgentFactory | None = None,
    ) -> None:
        self._job_manager = job_manager
        self._coordinate_service = coordinate_service
        self._pipeline_executor = pipeline_executor
        self._ai_agent_factory = ai_agent_factory or PydanticAIAgentFactory()

    def create_job(self, user_id: str | None) -> PipelineNormalizeRunJobResponse:
        return self._job_manager.create_job(user_id)

    def run_job(self, job_id: str, request: PipelineNormalizeRunRequest) -> None:
        self._job_manager.run_job(job_id, request, self.execute)

    def is_valid_job_id(self, job_id: str) -> bool:
        return self._job_manager.is_valid_job_id(job_id)

    def status_response(self, job_id: str) -> PipelineNormalizeRunStatusResponse | None:
        return self._job_manager.status_response(job_id)

    def read_result(self, job_id: str) -> PipelineNormalizeRunResponse | None:
        return self._job_manager.read_result(job_id)

    def execute(
        self,
        req: PipelineNormalizeRunRequest,
        job_id: str | None = None,
    ) -> PipelineNormalizeRunResponse:
        logger.debug(
            "normalize-run execute input: job_id=%s payload=%s",
            job_id,
            req.model_dump(mode="json", exclude_none=True),
        )
        response = self._pipeline_executor(
            req,
            job_id=job_id,
        )
        logger.debug(
            "normalize-run execute output: job_id=%s payload=%s",
            job_id,
            response.model_dump(mode="json", exclude_none=True),
        )
        ai_summary = self._selection_summary_note(
            req=req,
            selected_option_id=response.selectedOptionId,
            option_count=len(response.options),
        )
        if ai_summary:
            selection_summary = dict(response.selectionSummary or {})
            selection_summary["assistant_summary"] = ai_summary
            response = response.model_copy(
                update={"selectionSummary": selection_summary}
            )
        return response

    def _selection_summary_note(
        self,
        *,
        req: PipelineNormalizeRunRequest,
        selected_option_id: str | None,
        option_count: int,
    ) -> str | None:
        try:
            agent_config = root_config.services.pydantic_ai.agent(
                "normalize_run_summary"
            )
        except ValueError:
            return None

        agent = self._ai_agent_factory.text_agent(agent_config)
        prompt = (
            "Summarize this normalize-run result in one short paragraph. "
            f"selected_option_id={selected_option_id or 'none'}; "
            f"option_count={option_count}; "
            f"style={req.style or 'unspecified'}; "
            f"tenant_id={req.tenant_id or 'unspecified'}. "
            "Return plain text only."
        )
        try:
            result = agent.run_sync(prompt)
        except Exception:
            logger.exception(
                (
                    "normalize-run pydantic-ai summary failed: "
                    "user_id=%s selected_option_id=%s"
                ),
                req.user_id,
                selected_option_id,
            )
            return None

        output = getattr(result, "output", result)
        summary = str(output).strip()
        return summary or None


def build_normalize_run_pipeline_service(
    *,
    job_manager: NormalizeRunJobManager,
    coordinate_service: CoordinateNormalizationService,
    pipeline_executor: Callable[
        [PipelineNormalizeRunRequest, str | None],
        PipelineNormalizeRunResponse,
    ],
) -> NormalizeRunPipelineService:
    return NormalizeRunPipelineService(
        job_manager=job_manager,
        coordinate_service=coordinate_service,
        pipeline_executor=pipeline_executor,
    )
