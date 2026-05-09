from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from db.models import (
    Asset,
    AssetDimensions,
    AssetFilter,
    AssetId,
    AssetPrice,
    JsonValue,
    TenantId,
)
from db.pg_assets import PostgresAssetRepository

logger = logging.getLogger(__name__)

AUTO_LOAD_DEMO_DATA_ENV = "TKNT_AUTO_LOAD_DEMO_DATA"
ENABLE_DEMO_INVENTORY_ENV = "TKNT_ENABLE_DEMO_INVENTORY"
LEGACY_DEMO_INVENTORY_ENV = "TKNT_DEMO_INVENTORY_ENABLED"
SHARED_INVENTORY_TENANT_ENV = "TKNT_SHARED_INVENTORY_TENANT_ID"
DEFAULT_SHARED_INVENTORY_TENANT = "demo_tenant"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_demo_data_bootstrap_enabled() -> bool:
    raw_value = os.getenv(AUTO_LOAD_DEMO_DATA_ENV)
    if raw_value is None:
        return False
    return raw_value.strip().lower() in _TRUE_VALUES


def ensure_demo_inventory_loaded(
    *,
    tenant_id: str | None = None,
    inventory_path: Path | None = None,
) -> int:
    if not is_demo_data_bootstrap_enabled():
        return 0

    resolved_tenant = (
        tenant_id
        or os.getenv(SHARED_INVENTORY_TENANT_ENV)
        or DEFAULT_SHARED_INVENTORY_TENANT
    ).strip()
    if not resolved_tenant:
        resolved_tenant = DEFAULT_SHARED_INVENTORY_TENANT

    repo = PostgresAssetRepository()
    existing = repo.list_assets(
        AssetFilter(tenant_id=TenantId(resolved_tenant), type="FURNITURE")
    )
    if existing:
        return 0

    path = inventory_path or _default_inventory_path()
    if not path.is_file():
        logger.warning("Demo inventory bootstrap skipped; missing file: %s", path)
        return 0

    assets = _load_inventory_assets(path=path, tenant_id=resolved_tenant)
    for asset in assets:
        repo.upsert_asset(asset)
    return len(assets)


def _default_inventory_path() -> Path:
    return Path(__file__).resolve().parents[1] / "synthetic_data" / "inventory.json"


def _load_inventory_assets(*, path: Path, tenant_id: str) -> list[Asset]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Demo inventory JSON must be a list.")

    assets: list[Asset] = []
    for item in payload:
        if isinstance(item, Mapping):
            asset = _asset_from_inventory_item(item=item, tenant_id=tenant_id)
            if asset is not None:
                assets.append(asset)
    return assets


def _asset_from_inventory_item(
    *, item: Mapping[object, object], tenant_id: str
) -> Asset | None:
    raw_id = _optional_str(item.get("id"))
    if raw_id is None:
        return None

    attributes = _json_object(item.get("attributes"))
    item_type = _optional_str(item.get("type")) or "unknown"
    attributes.setdefault("category", item_type)
    attributes.setdefault("source", "synthetic_data")
    for numeric_key in ("footprint_area_m2", "length_mm", "width_mm", "height_mm"):
        value = _json_value(item.get(numeric_key))
        if value is not None:
            attributes[numeric_key] = value

    dimensions = AssetDimensions(
        length_mm=_optional_float(item.get("length_mm")),
        width_mm=_optional_float(item.get("width_mm")),
        height_mm=_optional_float(item.get("height_mm")),
    )
    price_amount = _optional_float(item.get("price_amount"))
    price_currency = _optional_str(item.get("price_currency")) or "VND"

    return Asset(
        id=AssetId(raw_id),
        tenant_id=TenantId(tenant_id),
        type="FURNITURE",
        name=_optional_str(item.get("name")) or raw_id,
        style_tags=_string_list(item.get("style_tags")),
        material=_optional_str(item.get("material")),
        brand=_optional_str(item.get("brand")),
        dimensions=dimensions,
        price=AssetPrice(amount=price_amount, currency=price_currency)
        if price_amount is not None
        else None,
        attributes=attributes,
    )


def _json_object(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, JsonValue] = {}
    for key, item in value.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        out[key_text] = _json_value(item)
    return out


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return _json_object(value)
    return str(value)


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 0 else None
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return number if number > 0 else None
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and text not in out:
            out.append(text)
    return out
