from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_optional_current_user
from config import config_file, load_config
from db.models import UserAccount
from pipeline.orchestrator import (
    run_case,
    case_paths,
    _make_case_id,
    _write_json,
    _now_utc_iso,
)
from pipeline.snapshot_prompt_compiler import (
    compile_snapshot_prompt,
    compile_snapshot_prompt_from_path,
)
from pipeline.snapshot_image_renderer import (
    SnapshotEditOperation,
    render_snapshot_image,
    render_snapshot_image_from_path,
)
from pipeline.image_flow_logging import log_image_flow_event
from services.user_content_service import UserContentService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRunRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    input_payload: dict[str, Any]
    description: str | None = None
    special_notes: str | None = None


class PipelineRunResponse(BaseModel):
    case_id: str
    case_dir: str
    status_path: str
    status: str


class PipelineStatusResponse(BaseModel):
    case_id: str
    stage: str
    updated_at_utc: str
    error: str | None = None
    message: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)


class PipelineResultResponse(BaseModel):
    case_id: str
    result: dict[str, Any]


class ArtifactResponse(BaseModel):
    case_id: str
    name: str
    payload: dict[str, Any]


class ClusterListResponse(BaseModel):
    case_id: str
    clusters: list[str]


class SnapshotPromptCompileRequest(BaseModel):
    snapshot_payload: dict[str, Any] | None = None
    snapshot_path: str | None = None


class SnapshotPromptCompileResponse(BaseModel):
    compilation: dict[str, Any]


class SnapshotImagePresetSelection(BaseModel):
    style: str | None = None
    lighting: str | None = None
    scenery: str | None = None


class SnapshotImageEditOperationRequest(BaseModel):
    object_id: str
    object_name: str | None = None
    replacement_image_data_url: str | None = None
    target_color: str | None = None


class SnapshotImageRenderRequest(BaseModel):
    snapshot_payload: dict[str, Any] | None = None
    snapshot_path: str | None = None
    snapshot_image_data_url: str | None = None
    layout_reference_image_data_url: str | None = None
    annotated_reference_image_data_url: str | None = None
    scene_reference_image_data_url: str | None = None
    scene_reference_mode: Literal[
        "none",
        "target_layout_with_scene_reference",
        "scene_reference_camera_transfer",
    ] = "none"
    user_prompt: str | None = None
    render_mode: Literal["generate", "edit"] = "generate"
    preset_selection: SnapshotImagePresetSelection = Field(
        default_factory=lambda: SnapshotImagePresetSelection()
    )
    root_layout_id: str | None = None
    edit_operations: list[SnapshotImageEditOperationRequest] = Field(
        default_factory=list
    )
    edit_source_image_data_url: str | None = None


class SnapshotImageRenderResponse(BaseModel):
    render: dict[str, Any]
    saved_render: dict[str, Any] | None = None


class SnapshotImagePresetOptionResponse(BaseModel):
    label: str
    prompt_suffix: str | None = None
    reference_image: str | None = None


class SnapshotImagePresetsResponse(BaseModel):
    styles: dict[str, SnapshotImagePresetOptionResponse]
    lights: dict[str, SnapshotImagePresetOptionResponse]
    sceneries: dict[str, SnapshotImagePresetOptionResponse]


def get_user_content_service() -> UserContentService:
    return UserContentService()


def _enrich_rotation_ccw(
    *,
    stylist_payload: dict[str, Any],
    absolute_layout_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    UI needs normalized orientation metadata per object.
    Stylist output intentionally omits it; we stitch it from absolute_layout,
    which contains the final semantic rotation and front-facing direction.
    """
    if not isinstance(stylist_payload, dict):
        return stylist_payload
    if not absolute_layout_payload or not isinstance(absolute_layout_payload, dict):
        return stylist_payload

    abs_objects = absolute_layout_payload.get("objects") or []
    if not isinstance(abs_objects, list) or not abs_objects:
        return stylist_payload

    by_id: dict[str, dict[str, Any]] = {}
    by_bbox: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for ao in abs_objects:
        if not isinstance(ao, dict):
            continue
        oid = ao.get("object_id")
        rot = ao.get("rotation_ccw", ao.get("rot"))
        bbox = ao.get("bbox") or {}
        if not isinstance(oid, str) or not oid:
            continue
        try:
            rotation_ccw = int(rot) % 360
        except (TypeError, ValueError):
            continue
        orientation_payload = {
            "rotation_ccw": rotation_ccw,
            "front_world": deepcopy(ao.get("front_world"))
            if isinstance(ao.get("front_world"), dict)
            else None,
            "front_side_world": (
                str(ao.get("front_side_world")).strip().lower()
                if isinstance(ao.get("front_side_world"), str)
                and str(ao.get("front_side_world")).strip()
                else None
            ),
            "axis_world": deepcopy(ao.get("axis_world"))
            if isinstance(ao.get("axis_world"), dict)
            else None,
        }
        by_id[oid] = orientation_payload
        # Best-effort fallback matching: bbox equality.
        # This helps if stylist instance ids don't exactly match absolute layout ids.
        try:
            key = (
                int(bbox.get("min_x", 0)),
                int(bbox.get("min_y", 0)),
                int(bbox.get("max_x", 0)),
                int(bbox.get("max_y", 0)),
            )
            by_bbox[key] = orientation_payload
        except Exception:
            pass

    out = dict(stylist_payload)
    objects = out.get("objects") or []
    if not isinstance(objects, list) or not objects:
        return out

    enriched: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        inst = obj.get("instance_id") or obj.get("id")
        bbox = obj.get("bbox") or {}

        orientation_payload: dict[str, Any] | None = None
        if isinstance(inst, str) and inst in by_id:
            orientation_payload = by_id[inst]
        else:
            # bbox match (best-effort)
            try:
                key = (
                    int(bbox.get("min_x", 0)),
                    int(bbox.get("min_y", 0)),
                    int(bbox.get("max_x", 0)),
                    int(bbox.get("max_y", 0)),
                )
                if key in by_bbox:
                    orientation_payload = by_bbox[key]
            except Exception:
                orientation_payload = None

        next_obj = dict(obj)
        next_obj["rotation_ccw"] = (
            int(
                (orientation_payload or {}).get(
                    "rotation_ccw",
                    next_obj.get("rotation_ccw", next_obj.get("rot", 0)),
                )
                or 0
            )
            % 360
        )
        next_obj["front_world"] = deepcopy(
            (orientation_payload or {}).get("front_world")
        )
        next_obj["front_side_world"] = (orientation_payload or {}).get(
            "front_side_world"
        )
        next_obj["axis_world"] = deepcopy((orientation_payload or {}).get("axis_world"))
        enriched.append(next_obj)

    out["objects"] = enriched
    return out


def _run_in_thread(**kwargs: Any) -> None:
    try:
        run_case(**kwargs)
    except Exception as exc:  # noqa: BLE001
        paths = case_paths(kwargs["case_id"], kwargs["cases_root"])
        existing_payload: dict[str, Any] = {}
        if paths.status.exists():
            try:
                existing_payload = json.loads(paths.status.read_text())
            except Exception:
                existing_payload = {}
        actions = existing_payload.get("actions")
        action_history = (
            [item for item in actions if isinstance(item, dict)]
            if isinstance(actions, list)
            else []
        )
        updated_at_utc = _now_utc_iso()
        action_history.append(
            {
                "stage": "error",
                "message": str(exc),
                "updated_at_utc": updated_at_utc,
                "progress_current": existing_payload.get("progress_current"),
                "progress_total": existing_payload.get("progress_total"),
                "error": str(exc),
            }
        )
        _write_json(
            paths.status,
            {
                "case_id": paths.case_id,
                "stage": "error",
                "updated_at_utc": updated_at_utc,
                "error": str(exc),
                "actions": action_history,
            },
        )


@router.post("/run", response_model=PipelineRunResponse)
def run_pipeline(
    req: PipelineRunRequest, background: BackgroundTasks
) -> PipelineRunResponse:
    case_id = _make_case_id(req.user_id)
    paths = case_paths(case_id)
    paths.root.mkdir(parents=True, exist_ok=True)

    _write_json(
        paths.status,
        {
            "case_id": case_id,
            "stage": "queued",
            "updated_at_utc": _now_utc_iso(),
        },
    )

    background.add_task(
        _run_in_thread,
        input_payload=req.input_payload,
        user_id=req.user_id,
        description=req.description,
        special_notes=req.special_notes,
        cases_root=str(paths.root.parent),
        case_id=case_id,
    )

    return PipelineRunResponse(
        case_id=case_id,
        case_dir=str(paths.root),
        status_path=str(paths.status),
        status="queued",
    )


@router.post("/compile-snapshot-prompt", response_model=SnapshotPromptCompileResponse)
def compile_snapshot_prompt_route(
    req: SnapshotPromptCompileRequest,
) -> SnapshotPromptCompileResponse:
    if req.snapshot_payload is None and not req.snapshot_path:
        raise HTTPException(
            status_code=400,
            detail="Provide either snapshot_payload or snapshot_path.",
        )

    try:
        if req.snapshot_payload is not None:
            compilation = compile_snapshot_prompt(req.snapshot_payload)
        else:
            compilation = compile_snapshot_prompt_from_path(req.snapshot_path or "")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SnapshotPromptCompileResponse(compilation=compilation)


@router.post("/render-snapshot-image", response_model=SnapshotImageRenderResponse)
def render_snapshot_image_route(
    req: SnapshotImageRenderRequest,
    current_user: UserAccount | None = Depends(get_optional_current_user),
    user_content_service: UserContentService = Depends(get_user_content_service),
) -> SnapshotImageRenderResponse:
    trace_id = uuid4().hex
    log_image_flow_event(
        "snapshot_image.api_input",
        {
            "trace_id": trace_id,
            "route": "/pipeline/render-snapshot-image",
            "authenticated": current_user is not None,
            "request": req.model_dump(),
        },
    )
    if req.snapshot_payload is None and not req.snapshot_path:
        log_image_flow_event(
            "snapshot_image.api_error",
            {
                "trace_id": trace_id,
                "status_code": 400,
                "error_message": "Provide either snapshot_payload or snapshot_path.",
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Provide either snapshot_payload or snapshot_path.",
        )

    try:
        edit_operations = [
            SnapshotEditOperation(
                object_id=item.object_id,
                object_name=item.object_name,
                replacement_image_data_url=item.replacement_image_data_url,
                target_color=item.target_color,
            )
            for item in req.edit_operations
        ]
        preset_selection = req.preset_selection.model_dump()
        if req.snapshot_payload is not None:
            if not req.snapshot_image_data_url:
                log_image_flow_event(
                    "snapshot_image.api_error",
                    {
                        "trace_id": trace_id,
                        "status_code": 400,
                        "error_message": (
                            "Provide snapshot_image_data_url when rendering from "
                            "snapshot_payload."
                        ),
                    },
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Provide snapshot_image_data_url when rendering from "
                        "snapshot_payload."
                    ),
                )
            render = render_snapshot_image(
                req.snapshot_payload,
                snapshot_image_data_url=req.snapshot_image_data_url,
                layout_reference_image_data_url=req.layout_reference_image_data_url,
                annotated_reference_image_data_url=(
                    req.annotated_reference_image_data_url
                ),
                scene_reference_image_data_url=req.scene_reference_image_data_url,
                scene_reference_mode=req.scene_reference_mode,
                user_prompt=req.user_prompt,
                render_mode=req.render_mode,
                preset_selection=preset_selection,
                edit_operations=edit_operations,
                edit_source_image_data_url=req.edit_source_image_data_url,
                trace_id=trace_id,
            )
        else:
            render = render_snapshot_image_from_path(
                req.snapshot_path or "",
                snapshot_image_data_url=req.snapshot_image_data_url,
                layout_reference_image_data_url=req.layout_reference_image_data_url,
                annotated_reference_image_data_url=(
                    req.annotated_reference_image_data_url
                ),
                scene_reference_image_data_url=req.scene_reference_image_data_url,
                scene_reference_mode=req.scene_reference_mode,
                user_prompt=req.user_prompt,
                render_mode=req.render_mode,
                preset_selection=preset_selection,
                edit_operations=edit_operations,
                edit_source_image_data_url=req.edit_source_image_data_url,
                trace_id=trace_id,
            )
    except FileNotFoundError as exc:
        log_image_flow_event(
            "snapshot_image.api_error",
            {
                "trace_id": trace_id,
                "status_code": 404,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        log_image_flow_event(
            "snapshot_image.api_error",
            {
                "trace_id": trace_id,
                "status_code": 400,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        log_image_flow_event(
            "snapshot_image.api_error",
            {
                "trace_id": trace_id,
                "status_code": 502,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    saved_render: dict[str, Any] | None = None
    if current_user is not None:
        try:
            metadata = render.get("metadata") if isinstance(render, dict) else None
            metadata_payload = metadata if isinstance(metadata, dict) else {}
            saved = user_content_service.save_snapshot_render_from_data_url(
                user=current_user,
                image_data_url=str(render["image"]["data_url"]),
                model_name=str(render["models"]["image_model_name"]),
                prompt=str(render["request"]["user_prompt"]),
                negative_prompt=None,
                meta={
                    "user_prompt": str(render["request"]["user_prompt"]),
                    "render_mode": str(
                        render["request"].get("render_mode", "generate")
                    ),
                    "preset_selection": render["request"].get("preset_selection"),
                    "edit_operations": render["request"].get("edit_operations"),
                    "aspect_ratio": str(render["image"]["aspect_ratio"]),
                    "source_image_mime_type": str(
                        render["request"]["source_image_mime_type"]
                    ),
                    "camera": metadata_payload.get("camera"),
                    "visible_objects": metadata_payload.get("visible_objects"),
                    "visible_object_ids": metadata_payload.get("visible_object_ids"),
                    "layout_reference_enabled": bool(
                        render["request"]["layout_reference_enabled"]
                    ),
                    "layout_reference_used": bool(
                        render["request"]["layout_reference_used"]
                    ),
                    "annotated_reference_used": bool(
                        render["request"]["annotated_reference_used"]
                    ),
                    "scene_reference_mode": str(
                        render["request"].get("scene_reference_mode", "none")
                    ),
                    "scene_reference_used": bool(
                        render["request"].get("scene_reference_used", False)
                    ),
                    "reference_only_camera_transfer_used": bool(
                        render["request"].get(
                            "reference_only_camera_transfer_used",
                            False,
                        )
                    ),
                    "root_layout_id": req.root_layout_id,
                },
            )
            saved_render = user_content_service.serialize_generated_render(
                saved,
                file_url=f"/account/renders/{saved.id}/file",
            )
            log_image_flow_event(
                "snapshot_image.saved_render.output",
                {
                    "trace_id": trace_id,
                    "render_id": str(saved.id),
                    "model_name": saved.model_name,
                    "mime_type": saved.mime_type,
                    "storage_path": saved.storage_path,
                    "meta": dict(saved.meta or {}),
                },
            )
        except Exception as exc:
            log_image_flow_event(
                "snapshot_image.saved_render.error",
                {
                    "trace_id": trace_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            saved_render = None

    return SnapshotImageRenderResponse(render=render, saved_render=saved_render)


@router.get("/render-presets", response_model=SnapshotImagePresetsResponse)
def get_render_presets() -> SnapshotImagePresetsResponse:
    presets = load_config(config_file).presets
    return SnapshotImagePresetsResponse(
        styles={
            key: SnapshotImagePresetOptionResponse(**value.model_dump())
            for key, value in presets.styles.items()
        },
        lights={
            key: SnapshotImagePresetOptionResponse(**value.model_dump())
            for key, value in presets.lights.items()
        },
        sceneries={
            key: SnapshotImagePresetOptionResponse(**value.model_dump())
            for key, value in presets.sceneries.items()
        },
    )


@router.get("/{case_id}/status", response_model=PipelineStatusResponse)
def get_status(case_id: str) -> PipelineStatusResponse:
    paths = case_paths(case_id)
    if not paths.status.exists():
        raise HTTPException(status_code=404, detail="case not found")
    payload = json.loads(paths.status.read_text())
    return PipelineStatusResponse(
        case_id=payload.get("case_id", case_id),
        stage=payload.get("stage", "unknown"),
        updated_at_utc=payload.get("updated_at_utc", ""),
        error=payload.get("error"),
        message=payload.get("message"),
        progress_current=payload.get("progress_current"),
        progress_total=payload.get("progress_total"),
        actions=payload.get("actions")
        if isinstance(payload.get("actions"), list)
        else [],
    )


@router.get("/{case_id}/result", response_model=PipelineResultResponse)
def get_result(case_id: str) -> PipelineResultResponse:
    paths = case_paths(case_id)
    if not paths.stylist.exists() and not paths.layout_variants.exists():
        raise HTTPException(status_code=404, detail="result not found")
    enriched: dict[str, Any] = {}
    if paths.stylist.exists():
        stylist_payload = json.loads(paths.stylist.read_text())
        absolute_payload: dict[str, Any] | None = None
        try:
            if paths.absolute_layout.exists():
                absolute_payload = json.loads(paths.absolute_layout.read_text())
        except Exception:
            absolute_payload = None

        enriched = _enrich_rotation_ccw(
            stylist_payload=stylist_payload,
            absolute_layout_payload=absolute_payload,
        )
    if paths.layout_variants.exists():
        variants_payload = json.loads(paths.layout_variants.read_text())
        if isinstance(variants_payload, dict):
            variants = variants_payload.get("variants")
            selected_variant_id = variants_payload.get("selected_variant_id")
            if isinstance(variants, list):
                enriched_variants: list[dict[str, Any]] = []
                for variant in variants:
                    if not isinstance(variant, dict):
                        continue
                    styled_variant = variant.get("styled_result")
                    absolute_variant = variant.get("absolute_layout")
                    next_variant = dict(variant)
                    if isinstance(styled_variant, dict):
                        next_variant["styled_result"] = _enrich_rotation_ccw(
                            stylist_payload=styled_variant,
                            absolute_layout_payload=absolute_variant
                            if isinstance(absolute_variant, dict)
                            else None,
                        )
                    enriched_variants.append(next_variant)
                if enriched_variants and not enriched:
                    first_variant = enriched_variants[0]
                    styled_result = first_variant.get("styled_result")
                    if isinstance(styled_result, dict):
                        enriched = dict(styled_result)
                enriched["variants"] = enriched_variants
            if isinstance(selected_variant_id, str) and selected_variant_id:
                enriched["selected_variant_id"] = selected_variant_id
    return PipelineResultResponse(case_id=case_id, result=enriched)


@router.get("/{case_id}/artifact/{name}", response_model=ArtifactResponse)
def get_artifact(case_id: str, name: str) -> ArtifactResponse:
    paths = case_paths(case_id)
    mapping = {
        "module_io_manifest": paths.module_io_manifest,
        "room_interpreter": paths.room_interpreter,
        "stylist_style_policy": paths.module_output("stylist_style_policy"),
        "cluster_forge": paths.cluster_forge,
        "tier_count": paths.tier_count,
        "tier_count_director": paths.module_output("tier_count_director"),
        "cluster_merged": paths.cluster_merged,
        "cluster_output_merger": paths.module_output("cluster_output_merger"),
        "cluster_relation_plan": paths.cluster_relation_plan,
        "seed_concept_relation_plan": paths.module_output("seed_concept_relation_plan"),
        "seed_concept_generator": paths.module_output("seed_concept_generator"),
        "cluster_placer": paths.cluster_placer,
        "phase2_controller": paths.module_output("phase2_controller"),
        "macro_cluster_solver": paths.module_output("macro_cluster_solver"),
        "macro_cluster_solver_dropped_inventory": paths.module_output(
            "macro_cluster_solver_dropped_inventory"
        ),
        "absolute_layout": paths.absolute_layout,
        "controlled_accessory_refill": paths.module_output(
            "controlled_accessory_refill"
        ),
        "stylist": paths.stylist,
        "cluster_outlines": paths.cluster_outlines_all,
        "cluster_outline_bundle": paths.module_output("cluster_outline_bundle"),
        "layout_variants": paths.layout_variants,
    }
    path = mapping.get(name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    payload = json.loads(path.read_text())
    return ArtifactResponse(case_id=case_id, name=name, payload=payload)


@router.get("/{case_id}/clusters", response_model=ClusterListResponse)
def list_clusters(case_id: str) -> ClusterListResponse:
    paths = case_paths(case_id)
    if not paths.clusters_dir.exists():
        raise HTTPException(status_code=404, detail="clusters not found")
    clusters = sorted(
        {
            p.name.replace("cluster_composer_", "").replace(".json", "")
            for p in paths.clusters_dir.glob("cluster_composer_*.json")
        }
    )
    return ClusterListResponse(case_id=case_id, clusters=clusters)


@router.get("/{case_id}/clusters/{cluster_id}", response_model=ArtifactResponse)
def get_cluster_composer(case_id: str, cluster_id: str) -> ArtifactResponse:
    paths = case_paths(case_id)
    path = paths.cluster_composer(cluster_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="cluster composer output not found")
    payload = json.loads(path.read_text())
    return ArtifactResponse(
        case_id=case_id, name=f"cluster_composer_{cluster_id}", payload=payload
    )


@router.get("/{case_id}/clusters/{cluster_id}/outline", response_model=ArtifactResponse)
def get_cluster_outline(case_id: str, cluster_id: str) -> ArtifactResponse:
    paths = case_paths(case_id)
    path = paths.cluster_outline(cluster_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="cluster outline not found")
    payload = json.loads(path.read_text())
    return ArtifactResponse(
        case_id=case_id, name=f"cluster_outline_{cluster_id}", payload=payload
    )
