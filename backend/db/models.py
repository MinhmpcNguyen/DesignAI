from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, NewType, TypeAlias

from pydantic import BaseModel, Field, field_validator

JsonValue: TypeAlias = (
    str | int | float | bool | None | list[object] | dict[str, object]
)

AssetId = NewType("AssetId", str)
DesignKnowledgeId = NewType("DesignKnowledgeId", str)
TenantId = NewType("TenantId", str)

AssetType = Literal["FURNITURE", "TEMPLATE"]


class AssetDimensions(BaseModel):
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None

    @field_validator("length_mm", "width_mm", "height_mm")
    @classmethod
    def _positive_or_none(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("Dimensions must be positive.")
        return value


class AssetPrice(BaseModel):
    amount: float
    currency: str = "VND"

    @field_validator("amount")
    @classmethod
    def _positive_amount(cls, value: float) -> float:
        if value < 0:
            raise ValueError("Price must be >= 0.")
        return value


class Asset(BaseModel):
    id: AssetId
    tenant_id: TenantId
    type: AssetType
    name: str
    style_tags: list[str] = Field(default_factory=list)
    material: str | None = None
    brand: str | None = None
    dimensions: AssetDimensions | None = None
    price: AssetPrice | None = None
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class AssetFilter(BaseModel):
    tenant_id: TenantId
    type: AssetType | None = None
    style_tags: list[str] = Field(default_factory=list)
    material: str | None = None
    brand: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    attributes: Mapping[str, JsonValue] = Field(default_factory=dict)


class DesignKnowledge(BaseModel):
    id: DesignKnowledgeId
    tenant_id: TenantId | None = None
    title: str
    content: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    meta: dict[str, JsonValue] = Field(default_factory=dict)


class DesignKnowledgeFilter(BaseModel):
    tenant_id: TenantId | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
