from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal, NewType, TypeAlias

from pydantic import BaseModel, Field, field_validator

JsonValue: TypeAlias = str | int | float | bool | None | list[object] | dict[str, object]

AssetId = NewType("AssetId", str)
AssetFileId = NewType("AssetFileId", str)
DesignKnowledgeId = NewType("DesignKnowledgeId", str)
TenantId = NewType("TenantId", str)
UserId = NewType("UserId", str)
SessionId = NewType("SessionId", str)
SavedLayoutId = NewType("SavedLayoutId", str)
GeneratedRenderId = NewType("GeneratedRenderId", str)

AssetType = Literal["FURNITURE", "TEMPLATE"]
FileKind = Literal["IMAGE", "SVG", "JSON", "PREVIEW", "TEXTURE", "MODEL"]
StorageProvider = Literal["s3", "minio", "gcs", "azure_blob", "local"]
RenderSource = Literal["snapshot_render", "object_prompt_reference", "object_image_upload"]


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


class AssetFile(BaseModel):
    id: AssetFileId
    asset_id: AssetId
    file_kind: FileKind
    provider: StorageProvider
    storage_key: str
    mime: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    bytes_size: int | None = None
    role: str | None = None
    meta: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("width_px", "height_px", "bytes_size")
    @classmethod
    def _non_negative_int(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("Numeric metadata must be >= 0.")
        return value


class AssetEmbedding(BaseModel):
    asset_id: AssetId
    content: str
    vector: list[float]
    model: str
    meta: dict[str, JsonValue] = Field(default_factory=dict)


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


class DesignKnowledgeEmbedding(BaseModel):
    knowledge_id: DesignKnowledgeId
    content: str
    vector: list[float]
    model: str
    meta: dict[str, JsonValue] = Field(default_factory=dict)


class DesignKnowledgeFilter(BaseModel):
    tenant_id: TenantId | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class UserAccount(BaseModel):
    id: UserId
    email: str
    display_name: str | None = None
    tenant_id: TenantId
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserAuthRecord(BaseModel):
    user: UserAccount
    password_salt: str
    password_hash: str


class AuthSession(BaseModel):
    id: SessionId
    user_id: UserId
    token_hash: str
    created_at: datetime | None = None
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class SavedLayout(BaseModel):
    id: SavedLayoutId
    user_id: UserId
    name: str
    floorplan_json: dict[str, JsonValue]
    design_json: dict[str, JsonValue] | None = None
    styled_result_json: dict[str, JsonValue] | None = None
    meta: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GeneratedRender(BaseModel):
    id: GeneratedRenderId
    user_id: UserId
    source: RenderSource
    model_name: str
    prompt: str
    negative_prompt: str | None = None
    storage_path: str | None = None
    image_bytes: bytes | None = None
    mime_type: str
    meta: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime | None = None
