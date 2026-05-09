from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.deps import get_optional_current_user
from config.demo_inventory import (
    is_demo_inventory_tenant,
    is_enabled_demo_inventory_tenant,
)
from db.models import AssetFile, UserAccount
from db.pg_assets import PostgresAssetRepository
from services.auth_service import get_shared_inventory_tenant_id
from services.user_content_service import UserContentService

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryItem(BaseModel):
    id: str
    name: str
    type: str
    style_tags: list[str] = Field(default_factory=list)
    material: str | None = None
    brand: str | None = None
    dimensions: dict[str, float | None] | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class InventoryListResponse(BaseModel):
    tenant_id: str
    items: list[InventoryItem]


class InventoryTypesResponse(BaseModel):
    tenant_id: str
    types: list[str]


class InventorySearchResponse(BaseModel):
    tenant_id: str
    query: str
    items: list[InventoryItem]


def get_user_content_service() -> UserContentService:
    return UserContentService()


def get_asset_repository() -> PostgresAssetRepository:
    return PostgresAssetRepository()


@router.get("/items", response_model=InventoryListResponse)
def list_items(
    tenant_id: str | None = Query(default=None),
    types: list[str] | None = Query(default=None),
    style_tags: list[str] | None = Query(default=None),
    current_user: UserAccount | None = Depends(get_optional_current_user),
    service: UserContentService = Depends(get_user_content_service),
) -> InventoryListResponse:
    shared_tenant = tenant_id or get_shared_inventory_tenant_id()
    items = _load_inventory_items(
        shared_tenant_id=shared_tenant,
        current_user=current_user,
        types=types,
        style_tags=style_tags,
        service=service,
    )
    resolved_tenant_id = (
        str(current_user.tenant_id) if current_user is not None else shared_tenant
    )
    return InventoryListResponse(tenant_id=resolved_tenant_id, items=items)


@router.get("/types", response_model=InventoryTypesResponse)
def list_types(
    tenant_id: str | None = Query(default=None),
    current_user: UserAccount | None = Depends(get_optional_current_user),
    service: UserContentService = Depends(get_user_content_service),
) -> InventoryTypesResponse:
    shared_tenant = tenant_id or get_shared_inventory_tenant_id()
    items = _load_inventory_items(
        shared_tenant_id=shared_tenant,
        current_user=current_user,
        service=service,
    )
    types_set = {item.type for item in items}
    resolved_tenant_id = (
        str(current_user.tenant_id) if current_user is not None else shared_tenant
    )
    return InventoryTypesResponse(tenant_id=resolved_tenant_id, types=sorted(types_set))


@router.get("/search", response_model=InventorySearchResponse)
def search_items(
    q: str = Query(..., min_length=1),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    current_user: UserAccount | None = Depends(get_optional_current_user),
    service: UserContentService = Depends(get_user_content_service),
) -> InventorySearchResponse:
    shared_tenant = tenant_id or get_shared_inventory_tenant_id()
    items = _load_inventory_items(
        shared_tenant_id=shared_tenant,
        current_user=current_user,
        service=service,
    )
    query_text = q.lower()
    results: list[InventoryItem] = []
    for item in items:
        haystack = " ".join(
            [
                item.name,
                item.type,
                item.brand or "",
                item.material or "",
                " ".join(item.style_tags or []),
            ]
        ).lower()
        if query_text in haystack:
            results.append(item)
        if len(results) >= limit:
            break
    resolved_tenant_id = (
        str(current_user.tenant_id) if current_user is not None else shared_tenant
    )
    return InventorySearchResponse(
        tenant_id=resolved_tenant_id,
        query=q,
        items=results,
    )


@router.get("/files/{asset_file_id}")
def get_inventory_file(
    asset_file_id: str,
    current_user: UserAccount | None = Depends(get_optional_current_user),
    service: UserContentService = Depends(get_user_content_service),
    asset_repository: PostgresAssetRepository = Depends(get_asset_repository),
) -> FileResponse:
    asset_file = asset_repository.get_asset_file(asset_file_id)
    if asset_file is None:
        raise HTTPException(status_code=404, detail="Asset file not found.")
    asset = asset_repository.get_asset(asset_file.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if is_demo_inventory_tenant(
        str(asset.tenant_id)
    ) and not is_enabled_demo_inventory_tenant(str(asset.tenant_id)):
        raise HTTPException(status_code=404, detail="Asset file not found.")
    if not service.can_access_asset(user=current_user, asset=asset):
        raise HTTPException(status_code=403, detail="Access denied.")

    file_path = Path(asset_file.storage_key).expanduser().resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset file is missing on disk.")

    media_type, _ = mimetypes.guess_type(file_path.name)
    if file_path.suffix.lower() == ".glb":
        media_type = "model/gltf-binary"
    return FileResponse(
        file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
    )


def _load_inventory_items(
    *,
    shared_tenant_id: str,
    current_user: UserAccount | None,
    types: list[str] | None = None,
    style_tags: list[str] | None = None,
    service: UserContentService,
) -> list[InventoryItem]:
    if is_demo_inventory_tenant(
        shared_tenant_id
    ) and not is_enabled_demo_inventory_tenant(shared_tenant_id):
        return []
    try:
        persisted_assets = service.list_inventory_assets_for_user(
            user=current_user,
            shared_tenant_id=shared_tenant_id,
            style_tags=style_tags,
        )
        type_set = {
            value for value in (types or []) if isinstance(value, str) and value
        }
        results: list[InventoryItem] = []
        for persisted in persisted_assets:
            payload = service.serialize_inventory_asset(
                persisted=persisted,
                file_url_builder=_build_file_url,
            )
            category = str(payload.get("type") or payload.get("name") or "")
            if type_set and category not in type_set:
                continue
            results.append(InventoryItem(**payload))
        return results
    except Exception:
        return _load_inventory_items_from_json(
            shared_tenant_id=shared_tenant_id,
            types=types,
            style_tags=style_tags,
        )


def _load_inventory_items_from_json(
    *,
    shared_tenant_id: str,
    types: list[str] | None = None,
    style_tags: list[str] | None = None,
) -> list[InventoryItem]:
    base = Path(__file__).resolve().parents[2]
    path = base / "synthetic_data" / "inventory.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    type_set = {value for value in (types or []) if isinstance(value, str) and value}
    style_set = {
        value for value in (style_tags or []) if isinstance(value, str) and value
    }
    results: list[InventoryItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("tenant_id") not in (shared_tenant_id, None, "demo_tenant"):
            continue
        category = str(item.get("type") or item.get("name") or "")
        if type_set and category not in type_set:
            continue
        item_styles = set(item.get("style_tags") or [])
        if style_set and not (style_set & item_styles):
            continue
        dimensions = {
            "length_mm": item.get("length_mm"),
            "width_mm": item.get("width_mm"),
            "height_mm": item.get("height_mm"),
        }
        attributes = dict(item.get("attributes") or {})
        attributes["ownership_scope"] = "shared"
        results.append(
            InventoryItem(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or category),
                type=category,
                style_tags=list(item.get("style_tags") or []),
                material=item.get("material"),
                brand=item.get("brand"),
                dimensions=dimensions,
                attributes=attributes,
            )
        )
    return results


def _build_file_url(asset_file: AssetFile) -> str:
    return f"/inventory/files/{asset_file.id}"
