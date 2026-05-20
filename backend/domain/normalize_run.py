from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from domain.types import JsonObject, JsonValue

NormalizeRunJobStatus = Literal["queued", "running", "ready", "error"]


class ApiErrorReason(StrEnum):
    NORMALIZE_RUN_INVALID_JOB_ID = "normalize_run_invalid_job_id"
    NORMALIZE_RUN_JOB_NOT_FOUND = "normalize_run_job_not_found"
    NORMALIZE_RUN_JOB_NOT_READY = "normalize_run_job_not_ready"
    NORMALIZE_RUN_JOB_FAILED = "normalize_run_job_failed"
    NORMALIZE_RUN_RESULT_MISSING = "normalize_run_result_missing"
    NORMALIZE_RUN_INVALID_PAYLOAD = "normalize_run_invalid_payload"
    NORMALIZE_RUN_NO_PIPELINE_INPUTS = "normalize_run_no_pipeline_inputs"
    NORMALIZE_RUN_NO_RUNNABLE_ROOMS = "normalize_run_no_runnable_rooms"
    NORMALIZE_RUN_PIPELINE_FAILED = "normalize_run_pipeline_failed"
    NORMALIZE_RUN_RESPONSE_ENRICHMENT_FAILED = (
        "normalize_run_response_enrichment_failed"
    )
    NORMALIZE_RUN_RESTORE_FAILED = "normalize_run_restore_failed"


class ApiErrorDetail(BaseModel):
    reason: ApiErrorReason
    message: str
    context: JsonObject = Field(default_factory=dict)


class FrontendRoomPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    key: str | None = None
    name: str | None = None
    polygons: list[list[float]] | None = None
    description: str | None = None


class FrontendWallPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    id: str | None = None


class FrontendOpeningPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    id: str | None = None
    objectRole: str | None = None


class PipelineNormalizeRunRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "room": {
                    "key": "-3:2.5",
                    "name": "Living, Dining, Kitchen",
                    "polygons": [
                        [-2.0, -0.8],
                        [-2.0, 1.5],
                        [3.5, 1.5],
                        [3.5, 5.0],
                        [-8.0, 5.0],
                        [-8.0, -0.8],
                    ],
                    "description": "Open shared living area.",
                },
                "walls": [],
                "openings": [],
                "source_unit": "auto",
                "tenant_id": "demo_tenant",
                "user_id": "demo_user",
                "style": "modern",
                "allow_generated_accessories": False,
            }
        },
    )

    room: FrontendRoomPayload = Field(
        ...,
        description=(
            "Single-room frontend payload with polygons, material, and description."
        ),
    )
    walls: list[FrontendWallPayload] = Field(
        default_factory=list,
        description="Wall segments in the same coordinate space as room.polygons.",
    )
    openings: list[FrontendOpeningPayload] = Field(
        default_factory=list,
        description="Door/window objects with frontend position, rotation, and size.",
    )
    source_unit: Literal[
        "auto",
        "m",
        "meter",
        "meters",
        "mm",
        "millimeter",
        "millimeters",
    ] = Field(default="auto", description="Unit of frontend coordinates.")
    tenant_id: str | None = Field(
        default="demo_tenant",
        description="Tenant used for catalog and room-knowledge lookups.",
    )
    user_id: str | None = Field(
        default="coordinate_normalizer_preview",
        description="User namespace for generated pipeline case files.",
    )
    description: str | None = Field(
        default=None,
        description="Optional design description forwarded to the pipeline.",
    )
    special_notes: str | None = Field(
        default=None,
        description="Optional extra instructions forwarded to the pipeline.",
    )
    style: str | None = Field(
        default="modern",
        description="Design style hint used during normalization.",
    )
    split_largest_room: bool = Field(
        default=True,
        description=(
            "Split the largest room into living/kitchen zones for multi-room payloads."
        ),
    )
    allow_generated_accessories: bool = Field(
        default=False,
        description="Allow the stylist to add generated accessory/decor objects.",
    )


class PipelineNormalizeRunPosition(BaseModel):
    x: float
    y: float
    z: float


class PipelineNormalizeRunRotation(BaseModel):
    x: float
    y: float
    z: float
    w: float


class PipelineNormalizeRunObject(BaseModel):
    name: str | None = None
    size: list[float] | None = None
    type: str | None = None
    color: str | None = None
    modelUrl: str
    position: PipelineNormalizeRunPosition
    rotation: PipelineNormalizeRunRotation
    objectRole: str | None = None
    catalogItemId: str | None = None
    # Rendering layer used by the frontend to decide how to display the object.
    # Values: "floor_solid" | "floor_underlay" | "surface_child" |
    #         "wall_mounted" | "ceiling"
    # "surface_child" items (desk lamps, throw blankets, etc.) should be
    # rendered at an elevated Y position (on top of their support furniture)
    # and hidden in the 2D floor-plan view.
    collisionLayer: str | None = None
    # Placement relationship: which furniture the item is attached to and how.
    # {"target_instance_id": "nightstand", "method": "on_top"} means the item
    # sits on top of the nightstand.
    placeOn: JsonObject | None = None


class PipelineNormalizeRunOption(BaseModel):
    optionId: str
    label: str | None = None
    layoutScore: int | None = None
    hardValid: bool | None = None
    complete: bool | None = None
    coverageRatio: float | None = None
    disabledReason: str | None = None
    objects: list[PipelineNormalizeRunObject] = Field(default_factory=list)
    openings: list[FrontendOpeningPayload] = Field(default_factory=list)


class PipelineNormalizeRunDebugSplitWall(BaseModel):
    id: str
    startPoint: tuple[float, float]
    endPoint: tuple[float, float]
    height: float | None = None
    thickness: float | None = None
    source: str | None = None


class PipelineNormalizeRunDebugZone(BaseModel):
    roomId: str
    roomType: str
    areaM2: float | None = None
    polygon: list[tuple[float, float]] = Field(default_factory=list)


class PipelineNormalizeRunResponse(BaseModel):
    objects: list[PipelineNormalizeRunObject] = Field(default_factory=list)
    openings: list[FrontendOpeningPayload] = Field(default_factory=list)
    selectedOptionId: str | None = None
    options: list[PipelineNormalizeRunOption] = Field(default_factory=list)
    selectionSummary: JsonObject | None = None
    debugSplitWall: PipelineNormalizeRunDebugSplitWall | None = None
    debugZones: list[PipelineNormalizeRunDebugZone] = Field(default_factory=list)


class PipelineNormalizeRunJobResponse(BaseModel):
    id: str
    status: NormalizeRunJobStatus
    statusUrl: str
    resultUrl: str


class PipelineNormalizeRunStatusResponse(BaseModel):
    id: str
    status: NormalizeRunJobStatus
    stage: str | None = None
    message: str | None = None
    progressCurrent: int | None = None
    progressTotal: int | None = None
    createdAtUtc: str | None = None
    updatedAtUtc: str | None = None
    caseIds: list[str] = Field(default_factory=list)
    currentCaseId: str | None = None
    error: ApiErrorDetail | None = None
    statusUrl: str
    resultUrl: str


class NormalizeRunJobRecord(BaseModel):
    id: str
    status: NormalizeRunJobStatus
    stage: str | None = None
    message: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    created_at_utc: str
    updated_at_utc: str
    case_ids: list[str] = Field(default_factory=list)
    current_case_id: str | None = None
    result_path: str | None = None
    error: ApiErrorDetail | None = None


class PipelineCaseStatusPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    stage: str | None = None
    message: str | None = None
    updated_at_utc: str | None = None
    progress_current: int | float | None = None
    progress_total: int | float | None = None


def json_object_from_mapping(value: Mapping[str, object]) -> JsonObject:
    out: JsonObject = {}
    for key, item in value.items():
        try:
            out[key] = _json_value_from_object(item)
        except TypeError:
            continue
    return out


def _json_value_from_object(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        # Runtime list validation keeps this cast at the JSON boundary.
        items = cast(list[object], value)
        return [_json_value_from_object(item) for item in items]
    if isinstance(value, dict):
        # Runtime dict validation keeps this cast at the JSON boundary.
        mapping = cast(Mapping[object, object], value)
        out: JsonObject = {}
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings.")
            out[key] = _json_value_from_object(item)
        return out
    raise TypeError(f"Value is not JSON serializable: {type(value).__name__}")
