from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Point(BaseModel):
    x: int
    y: int


class BBox(BaseModel):
    min_x: int
    min_y: int
    max_x: int
    max_y: int


class PlaceOn(BaseModel):
    target_instance_id: str
    method: Literal["on_top", "hang_on", "lean_on", "floor"]


class OpeningColor(BaseModel):
    id: str
    color_hex: str

    @field_validator("color_hex")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise ValueError("color_hex must be #RRGGBB")
        return value


class RoomOpenings(BaseModel):
    doors: list[dict] = Field(default_factory=list)
    windows: list[dict] = Field(default_factory=list)


class RoomSurfaces(BaseModel):
    wall_color_hex: str
    floor_color_hex: str
    ceiling_color_hex: str

    @field_validator("wall_color_hex", "floor_color_hex", "ceiling_color_hex")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise ValueError("color_hex must be #RRGGBB")
        return value


class RoomOpeningColors(BaseModel):
    doors: list[OpeningColor] = Field(default_factory=list)
    windows: list[OpeningColor] = Field(default_factory=list)


class StyledObject(BaseModel):
    instance_id: str
    object_type: str
    source: Literal["existing", "inventory"]
    cluster_id: str | None = None
    polygon_ccw: list[Point] = Field(default_factory=list)
    bbox: BBox
    color_hex: str
    material: str | None = None
    place_on: PlaceOn | None = None

    @field_validator("color_hex")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise ValueError("color_hex must be #RRGGBB")
        return value


class RoomInfo(BaseModel):
    room_id: str
    room_type: str
    polygon_ccw: list[Point] = Field(default_factory=list)
    obstacles: list[dict] = Field(default_factory=list)
    openings: RoomOpenings | None = None
    surfaces: RoomSurfaces | None = None
    opening_colors: RoomOpeningColors | None = None


class StylistOutput(BaseModel):
    status: Literal["OK", "NEED_INFO", "UNSAT"]
    room: RoomInfo | None = None
    objects: list[StyledObject] = Field(default_factory=list)
    final_style_plan: dict[str, object] | None = None
    notes: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_room_for_ok(self) -> "StylistOutput":
        if self.status == "OK" and self.room is None:
            raise ValueError("room is required when status=OK")
        return self
