from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Point(BaseModel):
    x: int
    y: int


class FloatPoint(BaseModel):
    x: float
    y: float


class BBox(BaseModel):
    min_x: int
    min_y: int
    max_x: int
    max_y: int


class PrincipalAxis(BaseModel):
    angle_deg: int
    vector: FloatPoint
    confidence: float


class RoomModel(BaseModel):
    unit: Literal["mm"]
    room_id: str
    name: str
    room_type: str = "unknown"
    polygon_ccw: list[Point] = Field(default_factory=list)
    area_mm2: int = 0
    area_m2: float = 0.0
    perimeter_mm: int = 0
    centroid_mm: Point = Field(default_factory=lambda: Point(x=0, y=0))
    principal_axis: PrincipalAxis = Field(
        default_factory=lambda: PrincipalAxis(
            angle_deg=0,
            vector=FloatPoint(x=1.0, y=0.0),
            confidence=0.0,
        )
    )
    bbox_mm: BBox = Field(
        default_factory=lambda: BBox(min_x=0, min_y=0, max_x=0, max_y=0)
    )
    ceiling_height_mm: int = 2800


class DoorOpening(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    kind: Literal["door"] = "door"
    segment_mm: list[Point]
    original_segment_mm: list[Point] = Field(default_factory=list)
    wall_id: str = ""
    width_mm: int = 0
    wall_t_start_mm: int = 0
    wall_t_end_mm: int = 0
    snap_distance_mm: int = 0
    swing_radius_mm: int
    hinge_hint: Literal["UNKNOWN", "LEFT", "RIGHT"]

    @field_validator("segment_mm")
    @classmethod
    def _validate_segment(cls, value: list[Point]) -> list[Point]:
        if len(value) != 2:
            raise ValueError("segment_mm must have exactly 2 points")
        return value


class WindowOpening(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    kind: Literal["window"] = "window"
    segment_mm: list[Point]
    original_segment_mm: list[Point] = Field(default_factory=list)
    wall_id: str = ""
    width_mm: int = 0
    wall_t_start_mm: int = 0
    wall_t_end_mm: int = 0
    snap_distance_mm: int = 0
    clearance_mm: int

    @field_validator("segment_mm")
    @classmethod
    def _validate_segment(cls, value: list[Point]) -> list[Point]:
        if len(value) != 2:
            raise ValueError("segment_mm must have exactly 2 points")
        return value


class Openings(BaseModel):
    doors: list[DoorOpening] = Field(default_factory=list)
    windows: list[WindowOpening] = Field(default_factory=list)


class Obstacle(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: Literal[
        "door_swing",
        "entry_clearance",
        "fixed_element",
        "no_go",
        "opening_guard",
        "window_clearance",
    ]
    polygon_ccw: list[Point] = Field(default_factory=list)
    hard: bool
    source_id: str = ""


class UsableWallSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    wall_id: str
    segment_mm: list[Point]
    length_mm: int
    wall_t_start_mm: int
    wall_t_end_mm: int
    inward_normal: FloatPoint


class BlockedWall(BaseModel):
    model_config = ConfigDict(extra="allow")

    wall_id: str
    length_mm: int


class GenericRegion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str


class AffordanceMap(BaseModel):
    model_config = ConfigDict(extra="allow")

    usable_walls: list[UsableWallSegment] = Field(default_factory=list)
    blocked_walls: list[BlockedWall] = Field(default_factory=list)
    entry_landing_zones: list[Obstacle] = Field(default_factory=list)
    circulation_corridors: list[GenericRegion] = Field(default_factory=list)
    daylight_regions: list[GenericRegion] = Field(default_factory=list)
    privacy_regions: list[GenericRegion] = Field(default_factory=list)
    focal_surfaces: list[GenericRegion] = Field(default_factory=list)
    center_openness_regions: list[GenericRegion] = Field(default_factory=list)
    wall_anchor_candidates: list[GenericRegion] = Field(default_factory=list)
    floating_zone_candidates: list[GenericRegion] = Field(default_factory=list)
    soft_usage_hints: dict[str, object] = Field(default_factory=dict)


class Topology(BaseModel):
    model_config = ConfigDict(extra="allow")

    wall_graph: dict[str, object] = Field(default_factory=dict)
    entry_node: dict[str, object] | None = None
    window_nodes: list[dict[str, object]] = Field(default_factory=list)
    passage_graph: dict[str, object] = Field(default_factory=dict)
    room_subzones: list[dict[str, object]] = Field(default_factory=list)


class QualityMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)
    settings: dict[str, int | float] = Field(default_factory=dict)


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")

    room_type: str
    style: str
    height_mm: int
    window_direction: str
    grid_mm: int = 50
    llm_temperature: float = 0.1
    llm_retry_max: int = 1


class RoomInterpreterOutput(BaseModel):
    status: Literal["OK", "NEED_INFO", "CONFLICT"]
    room: RoomModel
    openings: Openings
    hard_obstacles: list[Obstacle] = Field(default_factory=list)
    affordance_map: AffordanceMap = Field(default_factory=AffordanceMap)
    topology: Topology = Field(default_factory=Topology)
    quality_meta: QualityMeta = Field(default_factory=QualityMeta)
    obstacles: list[Obstacle] = Field(default_factory=list)
    meta: Meta
    notes: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
