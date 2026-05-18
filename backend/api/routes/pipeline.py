# Legacy route helpers bridge dynamic JSON from the existing orchestrator boundary.
# Public request, response, job, and error shapes are validated with Pydantic models.
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportPrivateUsage=false

from __future__ import annotations

import json
import logging
import math
from copy import deepcopy
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from adapters.catalog_api import (
    CatalogApiError,
    load_catalog_api_settings,
    load_catalog_inventory_payloads,
)
from api.errors import api_exception, raise_api_error
from domain.normalize_run import (
    ApiErrorDetail,
    ApiErrorReason,
    PipelineNormalizeRunJobResponse,
    PipelineNormalizeRunObject,
    PipelineNormalizeRunOption,
    PipelineNormalizeRunRequest,
    PipelineNormalizeRunResponse,
    PipelineNormalizeRunStatusResponse,
    json_object_from_mapping,
)
from managers.normalize_run_jobs import NormalizeRunJobManager
from pipeline.orchestrator import (
    _make_case_id,
    _now_utc_iso,
    _write_json,
    case_paths,
    run_case,
)
from repositories.normalize_run_jobs import NormalizeRunJobRepository
from services.coordinate_normalization_service import CoordinateNormalizationService
from services.normalize_run_pipeline_service import (
    NormalizeRunPipelineService,
    build_normalize_run_pipeline_service,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger(__name__)
_NORMALIZE_RUN_JOB_MANAGER = NormalizeRunJobManager(
    repository=NormalizeRunJobRepository(root=case_paths("normalize_run_jobs").root),
    cases_root=case_paths("").root,
)
_SIZE_VECTOR_LENGTH = 3
_QUATERNION_LENGTH = 4
_MIN_QUATERNION_NORM = 1e-12
_CATALOG_TYPE_FALLBACKS: dict[str, tuple[str, ...]] = {}


@lru_cache(maxsize=1)
def _normalize_run_pipeline_service() -> NormalizeRunPipelineService:
    return build_normalize_run_pipeline_service(
        job_manager=_NORMALIZE_RUN_JOB_MANAGER,
        coordinate_service=CoordinateNormalizationService(),
        pipeline_executor=_execute_normalize_run_pipeline,
    )


def _enrich_rotation_ccw(
    *,
    stylist_payload: dict[str, Any],
    absolute_layout_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not absolute_layout_payload:
        return stylist_payload

    absolute_objects = absolute_layout_payload.get("objects") or []
    if not isinstance(absolute_objects, list):
        return stylist_payload

    by_id: dict[str, dict[str, Any]] = {}
    by_bbox: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for absolute_object in absolute_objects:
        if not isinstance(absolute_object, dict):
            continue
        object_id = absolute_object.get("object_id")
        if not isinstance(object_id, str) or not object_id:
            continue
        rotation = absolute_object.get("rotation_ccw", absolute_object.get("rot"))
        rotation_number = _number(rotation)
        if rotation_number is None:
            continue
        rotation_ccw = int(rotation_number) % 360

        orientation = {
            "rotation_ccw": rotation_ccw,
            "front_world": deepcopy(absolute_object.get("front_world"))
            if isinstance(absolute_object.get("front_world"), dict)
            else None,
            "front_side_world": (
                str(absolute_object.get("front_side_world")).strip().lower()
                if isinstance(absolute_object.get("front_side_world"), str)
                and str(absolute_object.get("front_side_world")).strip()
                else None
            ),
            "axis_world": deepcopy(absolute_object.get("axis_world"))
            if isinstance(absolute_object.get("axis_world"), dict)
            else None,
        }
        by_id[object_id] = orientation

        bbox = _mapping(absolute_object.get("bbox"))
        try:
            bbox_key = (
                int(bbox.get("min_x", 0)),
                int(bbox.get("min_y", 0)),
                int(bbox.get("max_x", 0)),
                int(bbox.get("max_y", 0)),
            )
        except (TypeError, ValueError):
            continue
        by_bbox[bbox_key] = orientation

    objects = stylist_payload.get("objects") or []
    if not isinstance(objects, list):
        return stylist_payload

    enriched: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        orientation = _orientation_for_object(obj, by_id=by_id, by_bbox=by_bbox)
        next_obj = dict(obj)
        next_obj["rotation_ccw"] = (
            int(
                (orientation or {}).get(
                    "rotation_ccw",
                    next_obj.get("rotation_ccw", next_obj.get("rot", 0)),
                )
                or 0
            )
            % 360
        )
        next_obj["front_world"] = deepcopy((orientation or {}).get("front_world"))
        next_obj["front_side_world"] = (orientation or {}).get("front_side_world")
        next_obj["axis_world"] = deepcopy((orientation or {}).get("axis_world"))
        enriched.append(next_obj)

    out = dict(stylist_payload)
    out["objects"] = enriched
    return out


def _orientation_for_object(
    obj: dict[str, Any],
    *,
    by_id: dict[str, dict[str, Any]],
    by_bbox: dict[tuple[int, int, int, int], dict[str, Any]],
) -> dict[str, Any] | None:
    instance_id = obj.get("instance_id") or obj.get("id")
    if isinstance(instance_id, str) and instance_id in by_id:
        return by_id[instance_id]

    bbox = _mapping(obj.get("bbox"))
    try:
        bbox_key = (
            int(bbox.get("min_x", 0)),
            int(bbox.get("min_y", 0)),
            int(bbox.get("max_x", 0)),
            int(bbox.get("max_y", 0)),
        )
    except (TypeError, ValueError):
        return None
    return by_bbox.get(bbox_key)


def _status_payload(paths: Any) -> dict[str, Any]:
    if not paths.status.exists():
        return {}
    try:
        payload = json.loads(paths.status.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_pipeline_error(
    *,
    paths: Any,
    error: BaseException | str,
) -> dict[str, Any]:
    existing_payload = _status_payload(paths)
    actions = existing_payload.get("actions")
    action_history = (
        [item for item in actions if isinstance(item, dict)]
        if isinstance(actions, list)
        else []
    )
    message = str(error)
    error_type = type(error).__name__ if isinstance(error, BaseException) else "Error"
    failed_stage = str(existing_payload.get("stage") or "unknown")
    updated_at_utc = _now_utc_iso()
    action_history.append(
        {
            "stage": "error",
            "message": message,
            "updated_at_utc": updated_at_utc,
            "progress_current": existing_payload.get("progress_current"),
            "progress_total": existing_payload.get("progress_total"),
            "error": message,
        }
    )
    _write_json(
        paths.status,
        {
            "case_id": paths.case_id,
            "stage": "error",
            "failed_stage": failed_stage,
            "updated_at_utc": updated_at_utc,
            "error": message,
            "error_type": error_type,
            "actions": action_history,
        },
    )
    return {
        "case_id": paths.case_id,
        "failed_stage": failed_stage,
        "error_type": error_type,
        "message": message,
        "status_path": str(paths.status),
        "case_dir": str(paths.root),
    }


_NORMALIZE_RUN_CONTROL_FIELDS = {
    "source_unit",
    "tenant_id",
    "user_id",
    "description",
    "special_notes",
    "style",
    "split_largest_room",
    "allow_generated_accessories",
}


def _normalize_run_floorplan_payload(
    req: PipelineNormalizeRunRequest,
) -> dict[str, Any]:
    return req.model_dump(
        exclude=_NORMALIZE_RUN_CONTROL_FIELDS,
        exclude_none=True,
    )


def _coerce_normalize_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    room_payload = payload.get("room")
    if isinstance(room_payload, dict):
        out = {
            str(key): deepcopy(value)
            for key, value in payload.items()
            if key not in {"room", "openings", "objects"}
        }
        out["id"] = (
            _string_or_none(payload.get("id"))
            or _string_or_none(room_payload.get("key"))
            or "single-room-design"
        )
        out["name"] = (
            _string_or_none(payload.get("name"))
            or _string_or_none(room_payload.get("name"))
            or "Single Room Design"
        )
        out["rooms"] = [deepcopy(room_payload)]

        objects: list[Any] = []
        existing_objects = payload.get("objects")
        if isinstance(existing_objects, list):
            objects.extend(deepcopy(existing_objects))
        openings = payload.get("openings")
        if isinstance(openings, list):
            objects.extend(deepcopy(openings))
        if objects:
            out["objects"] = objects
        return out

    if isinstance(payload.get("rooms"), list):
        return payload
    if any(key in payload for key in ("polygons", "polygon", "polygon_ccw")):
        return {
            "id": _string_or_none(payload.get("id")) or "single-room-design",
            "name": _string_or_none(payload.get("name")) or "Single Room Design",
            "rooms": [dict(payload)],
        }
    return payload


def _safe_case_segment(value: str | None, fallback: str) -> str:
    raw = value or fallback
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw)
    safe = safe.strip("_-")
    return safe[:48] or fallback


def _json_object_from_path(path: Any) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _enriched_case_result(case_id: str, final_output: Any) -> dict[str, Any]:
    paths = case_paths(case_id)
    styled_payload = final_output if isinstance(final_output, dict) else None
    if styled_payload is None:
        styled_payload = _json_object_from_path(paths.stylist)
    if styled_payload is None:
        raise RuntimeError(f"Pipeline case {case_id} did not produce a styled result.")

    return _enrich_rotation_ccw(
        stylist_payload=styled_payload,
        absolute_layout_payload=_json_object_from_path(paths.absolute_layout),
    )


def _enriched_case_options(case_id: str, final_output: Any) -> list[dict[str, Any]]:
    variants_payload = _json_object_from_path(case_paths(case_id).layout_variants)
    variants = (
        variants_payload.get("variants") if isinstance(variants_payload, dict) else None
    )
    out: list[dict[str, Any]] = []
    if isinstance(variants, list):
        for index, variant in enumerate(variants, start=1):
            if not isinstance(variant, dict):
                continue
            styled_payload = variant.get("styled_result")
            if not isinstance(styled_payload, dict):
                continue
            absolute_payload = variant.get("absolute_layout")
            out.append(
                {
                    "option_id": _string_or_none(variant.get("variant_id"))
                    or f"variant_{index}",
                    "label": _string_or_none(variant.get("label")) or f"Option {index}",
                    "layout_score": _number(variant.get("layout_score")),
                    "hard_valid": variant.get("hard_valid")
                    if isinstance(variant.get("hard_valid"), bool)
                    else None,
                    "complete": variant.get("complete")
                    if isinstance(variant.get("complete"), bool)
                    else None,
                    "coverage_ratio": _number(variant.get("coverage_ratio")),
                    "styled_payload": _enrich_rotation_ccw(
                        stylist_payload=styled_payload,
                        absolute_layout_payload=absolute_payload
                        if isinstance(absolute_payload, dict)
                        else None,
                    ),
                }
            )
    if out:
        return out

    return [
        {
            "option_id": "variant_1",
            "label": "Option 1",
            "layout_score": None,
            "hard_valid": None,
            "complete": None,
            "coverage_ratio": None,
            "styled_payload": _enriched_case_result(case_id, final_output),
        }
    ]


def _case_selection_summary(case_id: str) -> dict[str, Any] | None:
    variants_payload = _json_object_from_path(case_paths(case_id).layout_variants)
    if not isinstance(variants_payload, dict):
        return None
    summary = variants_payload.get("selection_summary")
    return summary if isinstance(summary, dict) else None


def _collect_object_types(payloads: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        objects = payload.get("objects")
        if not isinstance(objects, list):
            continue
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            object_type = _string_or_none(obj.get("object_type"))
            if object_type is None:
                object_type = _string_or_none(obj.get("type"))
            normalized = _catalog_key(object_type)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            out.append(object_type or normalized)
            if normalized.endswith("_lamp") and "lamp" not in seen:
                seen.add("lamp")
                out.append("lamp")
            for fallback_type in _CATALOG_TYPE_FALLBACKS.get(normalized, ()):
                if fallback_type in seen:
                    continue
                seen.add(fallback_type)
                out.append(fallback_type)
    return out


def _collect_catalog_item_ids(payloads: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        objects = payload.get("objects")
        if not isinstance(objects, list):
            continue
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            for value in (
                obj.get("catalogItemId"),
                obj.get("catalog_id"),
                obj.get("inventory_id"),
                obj.get("source_id"),
            ):
                clean = _string_or_none(value)
                if clean is None:
                    continue
                normalized = _catalog_key(clean)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                out.append(clean)
    return out


def _load_catalog_index(
    *,
    object_types: list[str],
    catalog_item_ids: list[str],
) -> dict[str, Any]:
    if not object_types and not catalog_item_ids:
        return {"by_id": {}, "by_type": {}}
    try:
        payloads = load_catalog_inventory_payloads(
            item_ids=catalog_item_ids,
            types=object_types,
            default_rotation_presence=None,
        )
    except CatalogApiError as exc:
        logger.exception("Catalog lookup failed for /pipeline/normalize-run.")
        return {"by_id": {}, "by_type": {}, "error": str(exc)}

    by_id: dict[str, dict[str, Any]] = {}
    by_type: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        attributes = _mapping(payload.get("attributes"))
        for value in (
            payload.get("id"),
            payload.get("inventory_id"),
            payload.get("catalog_id"),
            attributes.get("inventory_id"),
            attributes.get("catalog_id"),
        ):
            key = _catalog_key(value)
            if key:
                _ = by_id.setdefault(key, payload)
        for value in (
            payload.get("object_type"),
            payload.get("type"),
            payload.get("asset_type"),
            attributes.get("semantic_object_type"),
            attributes.get("category"),
            attributes.get("object_role"),
            attributes.get("objectRole"),
            attributes.get("slug"),
            attributes.get("sku_slug"),
        ):
            key = _catalog_key(value)
            if key:
                by_type.setdefault(key, []).append(payload)
    return {"by_id": by_id, "by_type": by_type}


def _match_catalog_payload(
    obj: dict[str, Any],
    catalog_index: dict[str, Any],
) -> dict[str, Any] | None:
    by_id = _mapping(catalog_index.get("by_id"))
    by_type = _mapping(catalog_index.get("by_type"))
    for value in (
        obj.get("catalogItemId"),
        obj.get("catalog_id"),
        obj.get("inventory_id"),
        obj.get("source_id"),
    ):
        key = _catalog_key(value)
        match = by_id.get(key) if key else None
        if isinstance(match, dict):
            return match

    type_key = _catalog_key(obj.get("object_type") or obj.get("type"))
    candidates = by_type.get(type_key) if type_key else None
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        return first if isinstance(first, dict) else None
    if type_key:
        for fallback_key in _CATALOG_TYPE_FALLBACKS.get(type_key, ()):
            fallback_candidates = by_type.get(fallback_key)
            if isinstance(fallback_candidates, list) and fallback_candidates:
                first = fallback_candidates[0]
                return first if isinstance(first, dict) else None
    if type_key and type_key.endswith("_lamp"):
        lamp_candidates = by_type.get("lamp")
        if isinstance(lamp_candidates, list) and lamp_candidates:
            first = lamp_candidates[0]
            return first if isinstance(first, dict) else None
    return None


def _normalize_run_room_objects(
    *,
    styled_payload: dict[str, Any],
    catalog_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[float], list[list[float] | None]]:
    objects = styled_payload.get("objects")
    if not isinstance(objects, list):
        return [], [], []

    out: list[dict[str, Any]] = []
    rotations_ccw: list[float] = []
    default_rotations: list[list[float] | None] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        bbox = _bbox_from_object(obj)
        if bbox is None:
            continue
        catalog_payload = _match_catalog_payload(obj, catalog_index)
        catalog_item_id = _catalog_item_id(catalog_payload, obj)
        if catalog_payload is None and catalog_item_id is None:
            continue
        size_mm = _catalog_size_mm(catalog_payload)
        if size_mm is None:
            size_mm = [
                max(1.0, bbox["max_x"] - bbox["min_x"]),
                300.0,
                max(1.0, bbox["max_y"] - bbox["min_y"]),
            ]
        model_url = _catalog_model_url(catalog_payload, obj)
        if model_url is None:
            message = (
                "Skipping normalize-run object without modelUrl: "
                + "catalog_item_id=%s object_type=%s"
            )
            logger.warning(
                message,
                catalog_item_id,
                obj.get("object_type") or obj.get("type"),
            )
            continue

        rotation_ccw = _number(obj.get("rotation_ccw"))
        if rotation_ccw is None:
            rotation_ccw = _number(obj.get("rot")) or 0.0
        output_obj: dict[str, Any] = {
            "name": _catalog_name(catalog_payload, obj),
            "size": size_mm,
            "type": _catalog_shape_type(catalog_payload),
            "color": _catalog_color(catalog_payload, obj),
            "modelUrl": model_url,
            "position": {
                "x": (bbox["min_x"] + bbox["max_x"]) / 2.0,
                "y": size_mm[1] / 2.0,
                "z": (bbox["min_y"] + bbox["max_y"]) / 2.0,
            },
            "rotation_ccw": rotation_ccw,
            "objectRole": _catalog_object_role(catalog_payload),
            "catalogItemId": catalog_item_id,
        }
        out.append(output_obj)
        rotations_ccw.append(rotation_ccw)
        default_rotations.append(_catalog_default_rotation(catalog_payload))
    return out, rotations_ccw, default_rotations


def _finalize_normalize_run_objects(
    *,
    restored_objects: list[Any],
    rotations_ccw: list[float],
    default_rotations: list[list[float] | None],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, restored in enumerate(restored_objects):
        if not isinstance(restored, dict):
            continue
        rotation_ccw = rotations_ccw[index] if index < len(rotations_ccw) else 0.0
        default_rotation = (
            default_rotations[index] if index < len(default_rotations) else None
        )
        out.append(
            {
                "name": restored.get("name"),
                "size": restored.get("size"),
                "type": restored.get("type"),
                "color": restored.get("color"),
                "modelUrl": restored.get("modelUrl"),
                "position": restored.get("position"),
                "rotation": _quaternion_dict(
                    _combine_yaw_and_default_rotation(rotation_ccw, default_rotation)
                ),
                "objectRole": restored.get("objectRole"),
                "catalogItemId": restored.get("catalogItemId"),
            }
        )
    return out


def _normalize_run_restored_objects(
    *,
    coordinate_service: CoordinateNormalizationService,
    styled_payload: dict[str, Any],
    catalog_index: dict[str, Any],
    transform: dict[str, Any],
    room_id: str,
) -> list[dict[str, Any]]:
    local_objects, rotations_ccw, default_rotations = _normalize_run_room_objects(
        styled_payload=styled_payload,
        catalog_index=catalog_index,
    )
    if not local_objects:
        return []
    try:
        restored = coordinate_service.restore_output(
            local_objects,
            transform,
            coordinate_space="room_local",
            room_id=room_id,
            rotation_input="degrees",
        )
    except ValueError as exc:
        raise api_exception(
            422,
            ApiErrorReason.NORMALIZE_RUN_RESTORE_FAILED,
            str(exc),
            context={"room_id": room_id},
        ) from exc
    restored_payload = restored.get("restored_payload")
    restored_objects = restored_payload if isinstance(restored_payload, list) else []
    return _finalize_normalize_run_objects(
        restored_objects=restored_objects,
        rotations_ccw=rotations_ccw,
        default_rotations=default_rotations,
    )


def _bbox_from_object(obj: dict[str, Any]) -> dict[str, float] | None:
    bbox = _mapping(obj.get("bbox"))
    values = {
        "min_x": _number(bbox.get("min_x")),
        "min_y": _number(bbox.get("min_y")),
        "max_x": _number(bbox.get("max_x")),
        "max_y": _number(bbox.get("max_y")),
    }
    if all(value is not None for value in values.values()):
        return {key: float(value or 0.0) for key, value in values.items()}

    polygon = obj.get("polygon_ccw")
    if not isinstance(polygon, list):
        return None
    points: list[tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, dict):
            continue
        x = _number(point.get("x"))
        y = _number(point.get("y"))
        if x is not None and y is not None:
            points.append((x, y))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
    }


def _catalog_size_mm(catalog_payload: dict[str, Any] | None) -> list[float] | None:
    if catalog_payload is None:
        return None
    attributes = _mapping(catalog_payload.get("attributes"))
    size_mm = attributes.get("size_mm_xyz")
    if isinstance(size_mm, list) and len(size_mm) == _SIZE_VECTOR_LENGTH:
        values = [_number(item) for item in size_mm]
        if all(value is not None and value > 0 for value in values):
            return [float(value or 0.0) for value in values]

    length = _number(catalog_payload.get("length_mm") or attributes.get("length_mm"))
    height = _number(catalog_payload.get("height_mm") or attributes.get("height_mm"))
    width = _number(catalog_payload.get("width_mm") or attributes.get("width_mm"))
    if (
        length is not None
        and height is not None
        and width is not None
        and length > 0
        and height > 0
        and width > 0
    ):
        return [float(length), float(height), float(width)]
    return None


def _catalog_default_rotation(
    catalog_payload: dict[str, Any] | None,
) -> list[float] | None:
    if catalog_payload is None:
        return None
    attributes = _mapping(catalog_payload.get("attributes"))
    return _quaternion_from_value(
        attributes.get("defaultRotation") or attributes.get("default_rotation")
    )


def _catalog_name(
    catalog_payload: dict[str, Any] | None,
    obj: dict[str, Any],
) -> str | None:
    if catalog_payload is not None:
        for value in (
            catalog_payload.get("name"),
            catalog_payload.get("inventory_name"),
        ):
            clean = _string_or_none(value)
            if clean is not None:
                return clean
    for value in (obj.get("inventory_name"), obj.get("name"), obj.get("object_type")):
        clean = _string_or_none(value)
        if clean is not None:
            return clean
    return None


def _catalog_shape_type(catalog_payload: dict[str, Any] | None) -> str:
    attributes = _mapping(catalog_payload.get("attributes")) if catalog_payload else {}
    return _string_or_none(attributes.get("shape_type")) or "model"


def _catalog_color(
    catalog_payload: dict[str, Any] | None,
    obj: dict[str, Any],
) -> str | None:
    attributes = _mapping(catalog_payload.get("attributes")) if catalog_payload else {}
    return (
        _string_or_none(attributes.get("color_hex"))
        or _string_or_none(obj.get("color"))
        or _string_or_none(obj.get("color_hex"))
    )


def _catalog_model_url(
    catalog_payload: dict[str, Any] | None,
    obj: dict[str, Any],
) -> str | None:
    attributes = _mapping(catalog_payload.get("attributes")) if catalog_payload else {}
    candidates = (
        attributes.get("modelUrl"),
        attributes.get("model_url"),
        attributes.get("model3d"),
        attributes.get("model_3d"),
        attributes.get("default_model"),
        attributes.get("files"),
        attributes.get("model_variants"),
        attributes.get("modelVariants"),
        catalog_payload.get("modelUrl") if catalog_payload else None,
        catalog_payload.get("model_url") if catalog_payload else None,
        catalog_payload.get("files") if catalog_payload else None,
        obj.get("modelUrl"),
        obj.get("model_url"),
    )
    for candidate in candidates:
        url = _model_url_from_value(candidate)
        if url is not None:
            return _public_asset_url(url)
    return None


def _model_url_from_value(value: Any) -> str | None:
    clean = _string_or_none(value)
    if clean is not None:
        return clean

    if isinstance(value, dict):
        for key in (
            "url",
            "modelUrl",
            "model_url",
            "storage_key",
            "storageKey",
            "src",
            "href",
        ):
            clean = _string_or_none(value.get(key))
            if clean is not None:
                return clean
        for nested in value.values():
            clean = _model_url_from_value(nested)
            if clean is not None:
                return clean

    if isinstance(value, list):
        for item in value:
            item_map = _mapping(item)
            role = _catalog_key(item_map.get("role") or item_map.get("file_kind"))
            if role and role not in {"model", "model_3d", "3d_model", "model_gltf"}:
                continue
            clean = _model_url_from_value(item)
            if clean is not None:
                return clean

    return None


def _public_asset_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    settings = load_catalog_api_settings()
    return settings.asset_base_url.rstrip("/") + "/" + value.lstrip("/")


def _catalog_object_role(catalog_payload: dict[str, Any] | None) -> str | None:
    attributes = _mapping(catalog_payload.get("attributes")) if catalog_payload else {}
    return _string_or_none(attributes.get("objectRole")) or _string_or_none(
        attributes.get("object_role")
    )


def _catalog_item_id(
    catalog_payload: dict[str, Any] | None,
    obj: dict[str, Any],
) -> str | None:
    if catalog_payload is not None:
        for value in (
            catalog_payload.get("catalog_id"),
            catalog_payload.get("id"),
            catalog_payload.get("inventory_id"),
        ):
            clean = _string_or_none(value)
            if clean is not None:
                return clean
    return _string_or_none(
        obj.get("catalogItemId") or obj.get("catalog_id") or obj.get("inventory_id")
    )


def _combine_yaw_and_default_rotation(
    rotation_ccw: float,
    default_rotation: list[float] | None,
) -> list[float]:
    yaw_rotation = _yaw_degrees_to_quaternion(rotation_ccw)
    if default_rotation is None:
        return yaw_rotation
    return _normalize_quaternion(_multiply_quaternions(yaw_rotation, default_rotation))


def _yaw_degrees_to_quaternion(degrees: float) -> list[float]:
    half_angle = math.radians(degrees) / 2.0
    return [0.0, math.sin(half_angle), 0.0, math.cos(half_angle)]


def _multiply_quaternions(left: list[float], right: list[float]) -> list[float]:
    left_x, left_y, left_z, left_w = left
    right_x, right_y, right_z, right_w = right
    return [
        left_w * right_x + left_x * right_w + left_y * right_z - left_z * right_y,
        left_w * right_y - left_x * right_z + left_y * right_w + left_z * right_x,
        left_w * right_z + left_x * right_y - left_y * right_x + left_z * right_w,
        left_w * right_w - left_x * right_x - left_y * right_y - left_z * right_z,
    ]


def _quaternion_from_value(value: Any) -> list[float] | None:
    if isinstance(value, dict):
        components = [
            _number(value.get("x")),
            _number(value.get("y")),
            _number(value.get("z")),
            _number(value.get("w")),
        ]
    elif isinstance(value, list) and len(value) == _QUATERNION_LENGTH:
        components = [_number(item) for item in value]
    else:
        return None
    if any(component is None for component in components):
        return None
    return _normalize_quaternion([float(component or 0.0) for component in components])


def _normalize_quaternion(value: list[float]) -> list[float]:
    norm = math.sqrt(sum(component * component for component in value))
    if norm <= _MIN_QUATERNION_NORM:
        return [0.0, 0.0, 0.0, 1.0]
    return [round(component / norm, 12) for component in value]


def _quaternion_dict(value: list[float]) -> dict[str, float]:
    normalized = _normalize_quaternion(value)
    return {
        "x": normalized[0],
        "y": normalized[1],
        "z": normalized[2],
        "w": normalized[3],
    }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean or None


def _catalog_key(value: Any) -> str:
    clean = _string_or_none(value)
    if clean is None:
        return ""
    return clean.lower().replace("-", "_").replace(" ", "_")


def get_normalize_run_job_manager() -> NormalizeRunJobManager:
    return _NORMALIZE_RUN_JOB_MANAGER


def get_normalize_run_pipeline_service() -> NormalizeRunPipelineService:
    return _normalize_run_pipeline_service()


NormalizeRunJobManagerDep = Annotated[
    NormalizeRunJobManager,
    Depends(get_normalize_run_job_manager),
]

NormalizeRunPipelineServiceDep = Annotated[
    NormalizeRunPipelineService,
    Depends(get_normalize_run_pipeline_service),
]


@router.post(
    "/normalize-run",
    response_model=PipelineNormalizeRunJobResponse,
    responses={500: {"model": ApiErrorDetail}},
    summary="Start a normalize-run job and return a polling id",
)
def normalize_run_pipeline(
    req: PipelineNormalizeRunRequest,
    background_tasks: BackgroundTasks,
    service: NormalizeRunPipelineServiceDep,
) -> PipelineNormalizeRunJobResponse:
    job = service.create_job(req.user_id)
    background_tasks.add_task(service.run_job, job.id, req)
    return job


@router.get(
    "/normalize-run/{job_id}/status",
    response_model=PipelineNormalizeRunStatusResponse,
    responses={
        400: {"model": ApiErrorDetail},
        404: {"model": ApiErrorDetail},
    },
    summary="Get normalize-run job status",
)
def normalize_run_pipeline_status(
    job_id: str,
    service: NormalizeRunPipelineServiceDep,
) -> PipelineNormalizeRunStatusResponse:
    if not service.is_valid_job_id(job_id):
        raise_api_error(
            400,
            ApiErrorReason.NORMALIZE_RUN_INVALID_JOB_ID,
            "Normalize-run job id contains unsupported characters.",
            context={"id": job_id},
        )
    status_response = service.status_response(job_id)
    if status_response is None:
        raise_api_error(
            404,
            ApiErrorReason.NORMALIZE_RUN_JOB_NOT_FOUND,
            "Normalize-run job was not found.",
            context={"id": job_id},
        )
    return status_response


@router.get(
    "/normalize-run/{job_id}/result",
    response_model=PipelineNormalizeRunResponse,
    responses={
        400: {"model": ApiErrorDetail},
        404: {"model": ApiErrorDetail},
        409: {"model": ApiErrorDetail},
        500: {"model": ApiErrorDetail},
        502: {"model": ApiErrorDetail},
    },
    summary="Get a completed normalize-run result",
)
def normalize_run_pipeline_result(
    job_id: str,
    service: NormalizeRunPipelineServiceDep,
) -> PipelineNormalizeRunResponse:
    if not service.is_valid_job_id(job_id):
        raise_api_error(
            400,
            ApiErrorReason.NORMALIZE_RUN_INVALID_JOB_ID,
            "Normalize-run job id contains unsupported characters.",
            context={"id": job_id},
        )
    status_payload = service.status_response(job_id)
    if status_payload is None:
        raise_api_error(
            404,
            ApiErrorReason.NORMALIZE_RUN_JOB_NOT_FOUND,
            "Normalize-run job was not found.",
            context={"id": job_id},
        )
    if status_payload.status == "error":
        error = status_payload.error or ApiErrorDetail(
            reason=ApiErrorReason.NORMALIZE_RUN_JOB_FAILED,
            message="Normalize-run job failed.",
            context={"id": job_id},
        )
        raise HTTPException(status_code=502, detail=error.model_dump(mode="json"))
    if status_payload.status != "ready":
        raise_api_error(
            409,
            ApiErrorReason.NORMALIZE_RUN_JOB_NOT_READY,
            "Normalize-run job is not ready yet.",
            context={
                "id": job_id,
                "status": status_payload.status,
                "statusUrl": status_payload.statusUrl,
            },
        )

    result = service.read_result(job_id)
    if result is None:
        raise_api_error(
            500,
            ApiErrorReason.NORMALIZE_RUN_RESULT_MISSING,
            "Normalize-run job is ready but result payload is missing.",
            context={"id": job_id},
        )
    return result


def _execute_normalize_run_pipeline(
    req: PipelineNormalizeRunRequest,
    *,
    job_id: str | None = None,
    job_manager: NormalizeRunJobManager | None = None,
    coordinate_service: CoordinateNormalizationService | None = None,
) -> PipelineNormalizeRunResponse:
    coordinate_service = coordinate_service or CoordinateNormalizationService()
    floorplan_payload = _normalize_run_floorplan_payload(req)
    single_room_payload = isinstance(floorplan_payload.get("room"), dict) or (
        not isinstance(floorplan_payload.get("rooms"), list)
        and any(
            key in floorplan_payload for key in ("polygons", "polygon", "polygon_ccw")
        )
    )
    try:
        normalized = coordinate_service.normalize_input(
            _coerce_normalize_run_payload(floorplan_payload),
            source_unit=req.source_unit,
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            description=req.description,
            special_notes=req.special_notes,
            style=req.style,
            split_largest_room=req.split_largest_room and not single_room_payload,
        )
    except ValueError as exc:
        raise api_exception(
            422,
            ApiErrorReason.NORMALIZE_RUN_INVALID_PAYLOAD,
            str(exc),
        ) from exc

    system_inputs = normalized.get("system_inputs")
    if not isinstance(system_inputs, list) or not system_inputs:
        raise_api_error(
            422,
            ApiErrorReason.NORMALIZE_RUN_NO_PIPELINE_INPUTS,
            "No room pipeline inputs were produced from the payload.",
        )

    if job_id is not None and job_manager is not None:
        job_manager.update(
            job_id,
            status="running",
            stage="preparing_rooms",
            message=f"Prepared {len(system_inputs)} room pipeline input(s).",
            progress_current=0,
            progress_total=len(system_inputs),
        )

    base_case_id = job_id or _make_case_id(req.user_id or "normalize_run")
    room_options: list[tuple[str, list[dict[str, Any]]]] = []
    selection_summary: dict[str, Any] | None = None
    for index, item in enumerate(system_inputs, start=1):
        if not isinstance(item, dict):
            continue
        room_id = _string_or_none(item.get("room_id")) or f"room_{index}"
        pipeline_request = _mapping(item.get("pipeline_run_request"))
        input_payload = _mapping(pipeline_request.get("input_payload"))
        if not input_payload:
            continue

        input_payload = deepcopy(input_payload)
        user_input = dict(_mapping(input_payload.get("user_input")))
        user_input["allow_generated_accessories"] = req.allow_generated_accessories
        user_input[
            "disable_generated_accessories"
        ] = not req.allow_generated_accessories
        input_payload["user_input"] = user_input
        room_case_id = (
            f"{base_case_id}_{index:02d}_{_safe_case_segment(room_id, 'room')}"
        )
        if job_id is not None and job_manager is not None:
            job_manager.update(
                job_id,
                status="running",
                stage="running_pipeline",
                message=f"Running pipeline for room {index}/{len(system_inputs)}.",
                progress_current=index - 1,
                progress_total=len(system_inputs),
                case_ids=[room_case_id],
                current_case_id=room_case_id,
            )

        try:
            result = run_case(
                input_payload=input_payload,
                user_id=_string_or_none(pipeline_request.get("user_id"))
                or req.user_id
                or "normalize_run",
                description=_string_or_none(pipeline_request.get("description"))
                or req.description,
                special_notes=_string_or_none(pipeline_request.get("special_notes"))
                or req.special_notes,
                case_id=room_case_id,
            )
        except (RuntimeError, ValueError) as exc:
            paths = case_paths(room_case_id)
            logger.exception(
                "normalize-run pipeline failed: case_id=%s room_id=%s",
                room_case_id,
                room_id,
            )
            raise api_exception(
                502,
                ApiErrorReason.NORMALIZE_RUN_PIPELINE_FAILED,
                "Normalize-run pipeline failed.",
                context=json_object_from_mapping(
                    _record_pipeline_error(paths=paths, error=exc)
                ),
            ) from exc

        if result.get("error"):
            paths = case_paths(room_case_id)
            raise_api_error(
                502,
                ApiErrorReason.NORMALIZE_RUN_PIPELINE_FAILED,
                "Normalize-run pipeline returned an error.",
                context=json_object_from_mapping(
                    _record_pipeline_error(paths=paths, error=str(result["error"]))
                ),
            )

        try:
            if job_id is not None and job_manager is not None:
                job_manager.update(
                    job_id,
                    status="running",
                    stage="enriching_room",
                    message=f"Enriching room {index}/{len(system_inputs)} output.",
                    progress_current=index,
                    progress_total=len(system_inputs),
                    current_case_id=room_case_id,
                )
            enriched_options = _enriched_case_options(
                room_case_id,
                result.get("final_output"),
            )
        except RuntimeError as exc:
            paths = case_paths(room_case_id)
            logger.exception(
                "normalize-run response enrichment failed: case_id=%s room_id=%s",
                room_case_id,
                room_id,
            )
            raise api_exception(
                502,
                ApiErrorReason.NORMALIZE_RUN_RESPONSE_ENRICHMENT_FAILED,
                "Normalize-run response enrichment failed.",
                context=json_object_from_mapping(
                    _record_pipeline_error(paths=paths, error=exc)
                ),
            ) from exc
        if selection_summary is None:
            selection_summary = _case_selection_summary(room_case_id)
        room_options.append((room_id, enriched_options))

    if not room_options:
        raise_api_error(
            422,
            ApiErrorReason.NORMALIZE_RUN_NO_RUNNABLE_ROOMS,
            "No runnable room pipeline inputs were produced from the payload.",
        )

    if job_id is not None and job_manager is not None:
        job_manager.update(
            job_id,
            status="running",
            stage="loading_catalog",
            message="Loading catalog model data for normalized objects.",
            progress_current=len(room_options),
            progress_total=len(system_inputs),
        )
    styled_payloads = [
        styled_payload
        for _, options in room_options
        for option in options
        if isinstance((styled_payload := option.get("styled_payload")), dict)
    ]
    catalog_index = _load_catalog_index(
        object_types=_collect_object_types(styled_payloads),
        catalog_item_ids=_collect_catalog_item_ids(styled_payloads),
    )
    frontend_openings = [
        opening.model_dump(mode="json", exclude_none=True) for opening in req.openings
    ]
    if job_id is not None and job_manager is not None:
        job_manager.update(
            job_id,
            status="running",
            stage="restoring_output",
            message="Restoring normalized objects into frontend coordinates.",
            progress_current=len(room_options),
            progress_total=len(system_inputs),
        )
    response_options = _restore_normalize_run_options(
        coordinate_service=coordinate_service,
        room_options=room_options,
        catalog_index=catalog_index,
        transform=_mapping(normalized.get("transform")),
        openings=frontend_openings,
    )
    selected_objects = response_options[0]["objects"] if response_options else []
    selected_option_id = (
        _string_or_none(response_options[0].get("optionId"))
        if response_options
        else None
    )
    return PipelineNormalizeRunResponse(
        objects=[
            PipelineNormalizeRunObject.model_validate(item) for item in selected_objects
        ],
        openings=deepcopy(req.openings),
        selectedOptionId=selected_option_id,
        options=[
            PipelineNormalizeRunOption.model_validate(item) for item in response_options
        ],
        selectionSummary=json_object_from_mapping(selection_summary)
        if selection_summary is not None
        else None,
    )


def _restore_normalize_run_options(
    *,
    coordinate_service: CoordinateNormalizationService,
    room_options: list[tuple[str, list[dict[str, Any]]]],
    catalog_index: dict[str, Any],
    transform: dict[str, Any],
    openings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    option_count = max((len(options) for _, options in room_options), default=0)
    response_options: list[dict[str, Any]] = []
    for option_index in range(option_count):
        option_objects: list[dict[str, Any]] = []
        option_meta: dict[str, Any] | None = None
        for room_id, options in room_options:
            if not options:
                continue
            option = options[min(option_index, len(options) - 1)]
            if option_meta is None:
                option_meta = option
            styled_payload = option.get("styled_payload")
            if not isinstance(styled_payload, dict):
                continue
            option_objects.extend(
                _normalize_run_restored_objects(
                    coordinate_service=coordinate_service,
                    styled_payload=styled_payload,
                    catalog_index=catalog_index,
                    transform=transform,
                    room_id=room_id,
                )
            )
        if not option_objects:
            continue

        option_id = (
            _string_or_none((option_meta or {}).get("option_id"))
            or f"variant_{option_index + 1}"
        )
        layout_score = _number((option_meta or {}).get("layout_score"))
        response_options.append(
            {
                "optionId": option_id,
                "label": _string_or_none((option_meta or {}).get("label"))
                or f"Option {option_index + 1}",
                "layoutScore": int(layout_score) if layout_score is not None else None,
                "hardValid": (option_meta or {}).get("hard_valid")
                if isinstance((option_meta or {}).get("hard_valid"), bool)
                else None,
                "complete": (option_meta or {}).get("complete")
                if isinstance((option_meta or {}).get("complete"), bool)
                else None,
                "coverageRatio": _number((option_meta or {}).get("coverage_ratio")),
                "objects": option_objects,
                "openings": deepcopy(openings),
            }
        )
    return response_options
