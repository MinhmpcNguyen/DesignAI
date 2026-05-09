from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class Room(BaseModel):
    room_id: str
    name: str = "Main"
    polygon_mm: list[Point]
    floor_color_hex: str | None = None


class Wall(BaseModel):
    wall_id: str
    p1_mm: Point
    p2_mm: Point
    thickness_mm: float = 200.0
    room_id: str | None = None
    color_hex: str | None = None


class Door(BaseModel):
    door_id: str
    wall_id: str | None = None
    start_mm: Point
    end_mm: Point
    leaf_width_mm: float | None = None
    hinge_side: Literal["left", "right"] | None = None
    open_angle_deg: float | None = None
    open_direction: Literal["in", "out"] | None = None


class Window(BaseModel):
    window_id: str
    wall_id: str | None = None
    start_mm: Point
    end_mm: Point
    sill_height_mm: float | None = None
    height_mm: float | None = None


class Openings(BaseModel):
    doors: list[Door] = Field(default_factory=list)
    windows: list[Window] = Field(default_factory=list)


class FloorplanGeometry(BaseModel):
    room: Room
    walls: list[Wall] = Field(default_factory=list)
    openings: Openings = Field(default_factory=Openings)


class Footprint(BaseModel):
    w: float
    d: float


class Position(BaseModel):
    x: float
    y: float


class DirectionVector(BaseModel):
    dx: float
    dy: float


class Placement(BaseModel):
    placement_id: str
    asset_id: str
    category: str
    position_mm: Position
    rotation_deg: float = 0.0
    front_world: DirectionVector | None = None
    front_side_world: Literal["top", "bottom", "left", "right"] | None = None
    front_side_local: Literal["top", "bottom", "left", "right"] | None = None
    footprint_mm: Footprint
    height_mm: float = 0.0
    color_hex: str = "#CFCAC2"
    anchor: Literal["center"] = "center"
    collision_layer: str | None = None


class TopView(BaseModel):
    type: Literal["rect", "poly"]
    points: list[Point] | None = None


class InventoryItem(BaseModel):
    asset_id: str
    name: str
    category: str
    footprint_mm: Footprint
    height_mm: float
    top_view: TopView
    style_tags: list[str] = Field(default_factory=list)
    material_tags: list[str] = Field(default_factory=list)
    price: float | None = None
    color_hex: str | None = None


class TemplateItem(BaseModel):
    template_id: str
    name: str
    room_type: str | None = None
    supported_shapes: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)


class DesignPlanV1(BaseModel):
    floorplan_geometry: FloorplanGeometry
    placements: list[Placement]


class GenerateRequest(BaseModel):
    tenant_id: str | None = None
    user_input: dict[str, object] = Field(default_factory=dict)
    floorplan_geometry: FloorplanGeometry
    constraints: dict[str, object] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    design_plan: DesignPlanV1


class SuggestedFix(BaseModel):
    action_type: Literal["move", "rotate", "swap_asset", "remove_asset", "add_asset"]
    params: dict[str, object] = Field(default_factory=dict)


class Violation(BaseModel):
    severity: Literal["error", "warning", "needs_info"]
    code: str
    message: str
    placement_ids: list[str] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
    suggested_fixes: list[SuggestedFix] = Field(default_factory=list)


class CheckRequest(BaseModel):
    floorplan_geometry: FloorplanGeometry
    placements: list[Placement]
    constraints: dict[str, object] = Field(default_factory=dict)


class CheckResponse(BaseModel):
    violations: list[Violation] = Field(default_factory=list)


class BlueprintGenerateRequest(BaseModel):
    tenant_id: str | None = None
    user_input: dict[str, object] = Field(default_factory=dict)
    floorplan_geometry: FloorplanGeometry
    constraints: dict[str, object] = Field(default_factory=dict)
    rag_query: str | None = None
    max_iterations: int = 12


class BlueprintGenerateResponse(BaseModel):
    design_plan: DesignPlanV1
    status: str
    iterations: int
    logs: list[str] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    name: str
    tenant_id: str | None = None
    floorplan_geometry: FloorplanGeometry
    design_plan: DesignPlanV1 | None = None


class ProjectUpdateRequest(BaseModel):
    design_plan: DesignPlanV1


class ProjectSnapshotResponse(BaseModel):
    project_id: str
    version: int
    design_plan: DesignPlanV1


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    tenant_id: str | None
    floorplan_geometry: FloorplanGeometry
    design_plan: DesignPlanV1 | None
    created_at: datetime
