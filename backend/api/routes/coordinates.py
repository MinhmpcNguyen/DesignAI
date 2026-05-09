from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.coordinate_normalization_service import CoordinateNormalizationService

router = APIRouter(prefix="/coordinates", tags=["coordinates"])


class CoordinateNormalizeRequest(BaseModel):
    payload: dict[str, Any] = Field(..., description="Raw frontend floorplan payload.")
    source_unit: Literal[
        "auto",
        "m",
        "meter",
        "meters",
        "mm",
        "millimeter",
        "millimeters",
    ] = "auto"
    tenant_id: str | None = "demo_tenant"
    user_id: str | None = "coordinate_normalizer_preview"
    description: str | None = None
    special_notes: str | None = None
    style: str | None = "modern"
    split_largest_room: bool = True


class CoordinateNormalizeResponse(BaseModel):
    normalized_payload: dict[str, Any]
    transform: dict[str, Any]
    apartment: dict[str, Any]
    rooms: list[dict[str, Any]]
    system_inputs: list[dict[str, Any]] = Field(default_factory=list)
    room_split: dict[str, Any] = Field(default_factory=dict)


class CoordinateRestoreRequest(BaseModel):
    output_payload: Any = Field(
        ...,
        description="System output in apartment-normalized or room-local coordinates.",
    )
    transform: dict[str, Any] = Field(
        ...,
        description="Transform object returned by /coordinates/normalize-input.",
    )
    coordinate_space: Literal["apartment_normalized", "room_local"] = "room_local"
    room_id: str | None = None
    rotation_input: Literal["auto", "degrees", "radians", "quaternion"] = "auto"


class CoordinateRestoreResponse(BaseModel):
    restored_payload: Any
    transform_applied: dict[str, Any]


def get_coordinate_service() -> CoordinateNormalizationService:
    return CoordinateNormalizationService()


@router.post("/normalize-input", response_model=CoordinateNormalizeResponse)
def normalize_input(request: CoordinateNormalizeRequest) -> dict[str, Any]:
    try:
        return get_coordinate_service().normalize_input(
            request.payload,
            source_unit=request.source_unit,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            description=request.description,
            special_notes=request.special_notes,
            style=request.style,
            split_largest_room=request.split_largest_room,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/restore-output", response_model=CoordinateRestoreResponse)
def restore_output(request: CoordinateRestoreRequest) -> dict[str, Any]:
    try:
        return get_coordinate_service().restore_output(
            request.output_payload,
            request.transform,
            coordinate_space=request.coordinate_space,
            room_id=request.room_id,
            rotation_input=request.rotation_input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
