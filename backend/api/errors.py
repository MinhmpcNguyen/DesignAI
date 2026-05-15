from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from domain.normalize_run import ApiErrorDetail, ApiErrorReason
from domain.types import JsonObject


def api_error_detail(
    reason: ApiErrorReason,
    message: str,
    *,
    context: JsonObject | None = None,
) -> ApiErrorDetail:
    return ApiErrorDetail(
        reason=reason,
        message=message,
        context=context or {},
    )


def raise_api_error(
    status_code: int,
    reason: ApiErrorReason,
    message: str,
    *,
    context: JsonObject | None = None,
) -> NoReturn:
    raise api_exception(status_code, reason, message, context=context)


def api_exception(
    status_code: int,
    reason: ApiErrorReason,
    message: str,
    *,
    context: JsonObject | None = None,
) -> HTTPException:
    detail = api_error_detail(reason, message, context=context)
    return HTTPException(status_code=status_code, detail=detail.model_dump(mode="json"))


def http_exception_detail(exc: HTTPException) -> ApiErrorDetail:
    if isinstance(exc.detail, dict):
        try:
            return ApiErrorDetail.model_validate(exc.detail)
        except ValueError:
            pass
    return api_error_detail(
        ApiErrorReason.NORMALIZE_RUN_JOB_FAILED,
        str(exc.detail),
        context={"status_code": exc.status_code},
    )
