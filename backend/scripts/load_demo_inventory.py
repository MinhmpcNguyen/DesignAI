from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))

from config.demo_inventory import (  # noqa: E402
    DEMO_INVENTORY_ENV_FLAG,
    DEMO_INVENTORY_TENANT_ID,
    is_demo_inventory_enabled,
)
from db.models import (  # noqa: E402
    Asset,
    AssetDimensions,
    AssetFile,
    AssetFileId,
    AssetId,
    AssetPrice,
    JsonValue,
    TenantId,
)
from db.pg_assets import PostgresAssetRepository  # noqa: E402
from db.postgres import create_connection  # noqa: E402
from db.runtime_init import ensure_runtime_schema  # noqa: E402

DEFAULT_INVENTORY_JSON = ROOT_DIR / "demo_inventory" / "demo_inventory.json"
DEMO_ASSET_ID_PREFIX = "demo_inventory_"
DEMO_FILE_ID_PREFIX = "demo_inventory_file_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load local demo_inventory GLB assets into an isolated DB tenant."
    )
    parser.add_argument(
        "--inventory-json",
        type=Path,
        default=DEFAULT_INVENTORY_JSON,
        help="Path to the demo inventory JSON file.",
    )
    parser.add_argument(
        "--tenant-id",
        default=DEMO_INVENTORY_TENANT_ID,
        help="Tenant id used for the isolated demo inventory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the records without writing to Postgres.",
    )
    parser.add_argument(
        "--skip-orientation-sidecars",
        action="store_true",
        help="Do not merge *.glb.orientation.json review files into model metadata.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    enabled = is_demo_inventory_enabled()
    if not enabled and not args.dry_run:
        raise SystemExit(
            f"Refusing to write demo inventory while {DEMO_INVENTORY_ENV_FLAG}=0. "
            f"Set {DEMO_INVENTORY_ENV_FLAG}=1 or run with --dry-run."
        )

    inventory_path = args.inventory_json.expanduser().resolve()
    records = load_demo_records(
        inventory_path=inventory_path,
        tenant_id=args.tenant_id,
        include_orientation_sidecars=not args.skip_orientation_sidecars,
    )

    if args.dry_run:
        print(
            f"Dry run: {len(records)} demo inventory asset(s), "
            f"tenant={args.tenant_id}, enabled={enabled}."
        )
        for record in records:
            dims = record.asset.dimensions
            print(
                f"- {record.asset.id}: {record.asset.name} "
                f"[{record.asset.attributes.get('category')}] "
                f"{dims.width_mm if dims else None}x"
                f"{dims.length_mm if dims else None}x"
                f"{dims.height_mm if dims else None} mm"
            )
        return 0

    ensure_runtime_schema()
    repo = PostgresAssetRepository()
    for record in records:
        repo.upsert_asset(record.asset)
        replace_asset_files(record.asset.id)
        repo.create_asset_file(record.asset_file)

    print(
        f"Loaded {len(records)} demo inventory asset(s) into tenant {args.tenant_id}."
    )
    return 0


@dataclass(frozen=True)
class DemoInventoryRecord:
    asset: Asset
    asset_file: AssetFile


def load_demo_records(
    *,
    inventory_path: Path,
    tenant_id: str,
    include_orientation_sidecars: bool = True,
) -> list[DemoInventoryRecord]:
    if not inventory_path.exists():
        raise FileNotFoundError(f"Demo inventory JSON not found: {inventory_path}")

    raw_payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, list):
        raise ValueError("Demo inventory JSON must be a list of objects.")

    records: list[DemoInventoryRecord] = []
    model_dir = inventory_path.parent
    for raw_item in raw_payload:
        if not isinstance(raw_item, Mapping):
            continue
        records.append(
            build_demo_record(
                item=raw_item,
                model_dir=model_dir,
                tenant_id=tenant_id,
                include_orientation_sidecars=include_orientation_sidecars,
            )
        )
    return records


def build_demo_record(
    *,
    item: Mapping[str, object],
    model_dir: Path,
    tenant_id: str,
    include_orientation_sidecars: bool = True,
) -> DemoInventoryRecord:
    source_id = require_text(item, "id")
    name = read_text(item.get("name")) or source_id
    size = read_number_sequence(item.get("size"), expected_length=3)
    width_mm, height_mm, depth_mm = size
    model_path = model_dir / f"{source_id}.glb"
    if not model_path.exists():
        raise FileNotFoundError(f"GLB file not found for {source_id}: {model_path}")

    asset_id = AssetId(f"{DEMO_ASSET_ID_PREFIX}{source_id}")
    asset_file_id = AssetFileId(f"{DEMO_FILE_ID_PREFIX}{source_id}")
    category = infer_category(
        name=name,
        source_category=read_text(item.get("category")),
    )
    color_hex = read_text(item.get("color")) or "#7f7f7f"
    price_amount = read_price_amount(item.get("price"))
    rotation = read_object_record(item.get("rotation"))
    position = read_object_record(item.get("position"))
    model_metadata: dict[str, JsonValue] = {
        "url": f"/inventory/files/{asset_file_id}",
        "source": "demo_inventory",
        "fit": "contain",
        "local_path": str(model_path.resolve()),
    }
    if include_orientation_sidecars:
        model_metadata.update(load_orientation_sidecar_metadata(model_path))

    attributes: dict[str, JsonValue] = {
        "category": category,
        "room_type": "bedroom",
        "source": "demo_inventory",
        "source_dataset": "demo_inventory",
        "source_asset_id": source_id,
        "source_category": read_text(item.get("category")),
        "source_size_mm": {
            "width": width_mm,
            "height": height_mm,
            "depth": depth_mm,
        },
        "source_position_mm": position,
        "source_rotation_quaternion": rotation,
        "source_rotation_yaw_deg": quaternion_yaw_degrees(rotation),
        "shape": read_text(item.get("shape")),
        "placement_type": read_text(item.get("placementType")),
        "color_hex": color_hex,
        "material_tags": ["wood"],
        "model_3d": model_metadata,
    }

    asset = Asset(
        id=asset_id,
        tenant_id=TenantId(tenant_id),
        type="FURNITURE",
        name=name,
        style_tags=["rustic", "demo_bedroom"],
        material="wood",
        brand="Demo Inventory",
        dimensions=AssetDimensions(
            length_mm=depth_mm,
            width_mm=width_mm,
            height_mm=height_mm,
        ),
        price=AssetPrice(amount=price_amount, currency="VND")
        if price_amount is not None
        else None,
        attributes=attributes,
    )
    asset_file = AssetFile(
        id=asset_file_id,
        asset_id=asset_id,
        file_kind="MODEL",
        provider="local",
        storage_key=str(model_path.resolve()),
        mime="model/gltf-binary",
        bytes_size=model_path.stat().st_size,
        role="model",
        meta={
            "filename": model_path.name,
            "source": "demo_inventory",
            "source_asset_id": source_id,
        },
    )
    return DemoInventoryRecord(asset=asset, asset_file=asset_file)


def orientation_sidecar_path(model_path: Path) -> Path:
    return Path(f"{model_path}.orientation.json")


def load_orientation_sidecar_metadata(model_path: Path) -> dict[str, JsonValue]:
    sidecar_path = orientation_sidecar_path(model_path)
    if not sidecar_path.is_file():
        return {}

    try:
        raw_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid orientation sidecar JSON: {sidecar_path}") from exc

    payload = read_nested_json_object(raw_payload)
    if payload is None:
        raise ValueError(f"Orientation sidecar must contain an object: {sidecar_path}")

    metadata: dict[str, JsonValue] = {}
    preview_override = read_nested_json_object(payload.get("preview_override"))
    if preview_override is not None:
        metadata["preview_override"] = preview_override

    orientation_review = read_nested_json_object(payload.get("orientation_review"))
    if orientation_review is not None:
        metadata["orientation_review"] = orientation_review

    if metadata:
        metadata["orientation_sidecar"] = {
            "path": str(sidecar_path.resolve()),
            "file_name": sidecar_path.name,
        }
    return metadata


def replace_asset_files(asset_id: AssetId) -> None:
    query = "DELETE FROM asset_files WHERE asset_id = %(asset_id)s"
    with create_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"asset_id": asset_id})


def require_text(item: Mapping[str, object], key: str) -> str:
    value = read_text(item.get(key))
    if value is None:
        raise ValueError(f"Missing required text field: {key}")
    return value


def read_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def read_number_sequence(value: object, *, expected_length: int) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("Expected a numeric sequence.")
    numbers: list[float] = []
    for raw in value:
        if not isinstance(raw, (int, float)):
            raise ValueError(f"Expected a numeric value, got {raw!r}.")
        number = float(raw)
        if number <= 0:
            raise ValueError(f"Expected positive dimension, got {number}.")
        numbers.append(number)
    if len(numbers) != expected_length:
        raise ValueError(f"Expected {expected_length} values, got {len(numbers)}.")
    return tuple(numbers)


def read_object_record(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, JsonValue] = {}
    for key, raw in value.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        if isinstance(raw, (int, float, str, bool)) or raw is None:
            out[key_text] = raw
    return out


def read_nested_json_object(value: object) -> dict[str, JsonValue] | None:
    if not isinstance(value, Mapping):
        return None
    out: dict[str, JsonValue] = {}
    for key, raw in value.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        out[key_text] = sanitize_json_value(raw)
    return out


def sanitize_json_value(value: object) -> JsonValue:
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_json_value(item)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def read_price_amount(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError as exc:
            raise ValueError(f"Invalid price value: {value}") from exc
    return None


def infer_category(*, name: str, source_category: str | None) -> str:
    normalized = name.lower()
    if "giường" in normalized:
        return "bed"
    if "tủ quần áo" in normalized:
        return "wardrobe"
    if "tủ nhỏ" in normalized:
        return "nightstand"
    if "bàn" in normalized:
        return "desk"
    if "ghế" in normalized:
        return "chair"
    return source_category or "furniture"


def quaternion_yaw_degrees(rotation: Mapping[str, object]) -> float | None:
    x = read_number(rotation.get("x"))
    y = read_number(rotation.get("y"))
    z = read_number(rotation.get("z"))
    w = read_number(rotation.get("w"))
    if x is None or y is None or z is None or w is None:
        return None
    sin_y = 2.0 * (w * y + x * z)
    cos_y = 1.0 - 2.0 * (y * y + z * z)
    return round(math.degrees(math.atan2(sin_y, cos_y)), 4)


def read_number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
