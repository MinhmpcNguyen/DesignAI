from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))

from db import PostgresAssetRepository
from db.models import Asset, AssetFilter, TenantId

ASPECT_MISMATCH_TRIGGER = 1.6
ASPECT_IMPROVEMENT_TRIGGER = 1.35
TARGET_NON_SQUARE_TRIGGER = 1.18
DEFAULT_CONFIDENCE_THRESHOLD = 0.58
DEFAULT_SHELF_DEPTH_SCALE = 1.12
MIN_ROTATION_TARGET_SPAN_MM = 900
SECTIONAL_SOFA_ROTATION_OFFSET = 180.0

SHELF_FAMILY_TOKENS = (
    "shelf",
    "bookshelf",
    "book_shelf",
    "bookcase",
    "cabinet",
    "etagere",
)

WALL_FAMILY_TOKENS = (
    "wall_",
    "mirror",
    "blind",
    "curtain",
    "whiteboard",
    "projector_screen",
    "towel_rack",
    "wall_sconce",
    "wall_art",
    "air_conditioner",
    "window",
    "tv_",
)

ROTATION_FAMILY_TOKENS = (
    "sofa",
    "sectional",
    "bed",
    "mattress",
    "headboard",
    "tv_console",
    "console_table",
    "sideboard",
    "cabinet",
    "shelf",
    "dresser",
    "wardrobe",
    "vanity",
    "nightstand",
    "pedestal",
    "table",
    "desk",
    "bench",
    "cart",
    "island",
    "recliner",
    "ottoman",
)


@dataclass(frozen=True)
class PreviewCalibrationData:
    status: str
    confidence: float
    base_width_m: float
    base_height_m: float
    base_depth_m: float
    target_width_mm: float
    target_height_mm: float
    target_depth_mm: float


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def asset_family(asset_id: str) -> str:
    return re.sub(r"_\d+$", "", asset_id.strip().lower())


def load_inventory_assets(*, tenant_id: str) -> list[Asset]:
    repo = PostgresAssetRepository()
    assets = list(
        repo.list_assets(
            AssetFilter(tenant_id=TenantId(tenant_id), type="FURNITURE")
        )
    )
    assets.sort(key=lambda asset: str(asset.id))
    return assets


def read_positive_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if numeric > 0 else None
    return None


def read_calibration(metadata: dict[str, object]) -> PreviewCalibrationData | None:
    raw = metadata.get("preview_calibration")
    if not isinstance(raw, dict):
        return None

    base_size = raw.get("base_size_m")
    target_dims = raw.get("target_dimensions_mm")
    if not isinstance(base_size, dict) or not isinstance(target_dims, dict):
        return None

    base_width_m = read_positive_float(base_size.get("width"))
    base_height_m = read_positive_float(base_size.get("height"))
    base_depth_m = read_positive_float(base_size.get("depth"))
    target_width_mm = read_positive_float(target_dims.get("width"))
    target_height_mm = read_positive_float(target_dims.get("height"))
    target_depth_mm = read_positive_float(target_dims.get("depth"))
    if (
        base_width_m is None
        or base_height_m is None
        or base_depth_m is None
        or target_width_mm is None
        or target_height_mm is None
        or target_depth_mm is None
    ):
        return None

    status = str(raw.get("status") or "unknown").strip().lower()
    confidence = float(raw.get("confidence") or 0)
    return PreviewCalibrationData(
        status=status,
        confidence=confidence,
        base_width_m=base_width_m,
        base_height_m=base_height_m,
        base_depth_m=base_depth_m,
        target_width_mm=target_width_mm,
        target_height_mm=target_height_mm,
        target_depth_mm=target_depth_mm,
    )


def compute_aspect_mismatch(first: float, second: float) -> float:
    if first <= 0 or second <= 0:
        return float("inf")
    aspect = first / second
    inverse = second / first
    return max(aspect, inverse)


def compute_target_alignment(base_primary: float, base_secondary: float, target_primary: float, target_secondary: float) -> float:
    if (
        base_primary <= 0
        or base_secondary <= 0
        or target_primary <= 0
        or target_secondary <= 0
    ):
        return float("inf")
    base_aspect = base_primary / base_secondary
    target_aspect = target_primary / target_secondary
    return max(base_aspect / target_aspect, target_aspect / base_aspect)


def is_wall_family(family: str) -> bool:
    return any(token in family for token in WALL_FAMILY_TOKENS)


def is_shelf_family(family: str) -> bool:
    return any(token in family for token in SHELF_FAMILY_TOKENS)


def is_rotation_candidate_family(family: str) -> bool:
    return any(token in family for token in ROTATION_FAMILY_TOKENS)


def build_override(
    *,
    asset_id: str,
    calibration: PreviewCalibrationData,
    shelf_depth_scale: float,
) -> dict[str, object] | None:
    family = asset_family(asset_id)
    if family == "sectional_sofa":
        return {
            "enabled": True,
            "contexts": ["panel"],
            "rotation_deg_offset": SECTIONAL_SOFA_ROTATION_OFFSET,
            "notes": "Flip sectional sofa facing in the panel so the chaise/back orientation matches the layout better.",
        }

    is_wall = is_wall_family(family)
    base_primary = calibration.base_width_m
    target_primary = calibration.target_width_mm
    if is_wall:
        base_secondary = calibration.base_height_m
        target_secondary = calibration.target_height_mm
    else:
        base_secondary = calibration.base_depth_m
        target_secondary = calibration.target_depth_mm

    current_alignment = compute_target_alignment(
        base_primary,
        base_secondary,
        target_primary,
        target_secondary,
    )
    rotated_alignment = compute_target_alignment(
        base_secondary,
        base_primary,
        target_primary,
        target_secondary,
    )
    target_shape = compute_aspect_mismatch(target_primary, target_secondary)

    notes: list[str] = []
    rotation_deg_offset = 0.0
    target_span_mm = max(calibration.target_width_mm, calibration.target_depth_mm)
    if (
        not is_wall
        and is_rotation_candidate_family(family)
        and target_span_mm >= MIN_ROTATION_TARGET_SPAN_MM
        and target_shape >= TARGET_NON_SQUARE_TRIGGER
        and current_alignment >= ASPECT_MISMATCH_TRIGGER
        and rotated_alignment < current_alignment / ASPECT_IMPROVEMENT_TRIGGER
    ):
        rotation_deg_offset = 90.0
        notes.append(
            "Rotate panel preview by 90deg because swapping width/depth aligns much better with the proxy box."
        )

    dimension_scale: dict[str, float] = {}
    if is_shelf_family(family) and shelf_depth_scale > 1:
        dimension_scale["depth"] = shelf_depth_scale
        notes.append(
            "Add a small depth boost for shelf/cabinet-like previews so the panel thickness reads closer to the proxy."
        )

    if rotation_deg_offset == 0 and not dimension_scale:
        return None

    override: dict[str, object] = {
        "enabled": True,
        "contexts": ["panel"],
        "rotation_deg_offset": rotation_deg_offset,
    }
    if dimension_scale:
        override["dimension_scale"] = dimension_scale
    if notes:
        override["notes"] = " ".join(notes)
    return override


def update_variant_override(
    *,
    asset: Asset,
    variant_key: str,
    override: dict[str, object],
) -> Asset:
    attributes = dict(asset.attributes or {})
    variants_raw = attributes.get("model_variants")
    variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
    metadata_raw = variants.get(variant_key)
    if not isinstance(metadata_raw, dict):
        raise ValueError(
            f'Asset "{asset.id}" style "{variant_key}" has no variant metadata to update.'
        )

    next_metadata = dict(metadata_raw)
    next_metadata["preview_override"] = override
    variants[variant_key] = next_metadata
    attributes["model_variants"] = variants

    current_model = attributes.get("model_3d")
    if isinstance(current_model, dict) and current_model.get("url") == next_metadata.get("url"):
        next_model = dict(current_model)
        next_model["preview_override"] = override
        attributes["model_3d"] = next_model
        attributes["model_url"] = next_model.get("url")

    return asset.model_copy(update={"attributes": attributes})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a conservative panel-only GLB review pass for low-confidence calibrations."
        )
    )
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--style-keys", nargs="*", default=None)
    parser.add_argument("--asset-ids", nargs="*", default=None)
    parser.add_argument("--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    parser.add_argument("--shelf-depth-scale", type=float, default=DEFAULT_SHELF_DEPTH_SCALE)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    repo = PostgresAssetRepository()
    assets = load_inventory_assets(tenant_id=args.tenant_id)
    style_keys = (
        {canonicalize_style_key(style) for style in args.style_keys if style.strip()}
        if args.style_keys
        else None
    )
    asset_ids = {asset_id.strip() for asset_id in args.asset_ids or [] if asset_id.strip()}

    applied_count = 0
    skipped_count = 0
    reviewed_count = 0

    for asset in assets:
        asset_id = str(asset.id)
        if asset_ids and asset_id not in asset_ids:
            continue

        attributes = dict(asset.attributes or {})
        variants_raw = attributes.get("model_variants")
        if not isinstance(variants_raw, dict):
            continue

        current_asset = asset
        for variant_key, metadata_raw in variants_raw.items():
            if not isinstance(metadata_raw, dict):
                continue
            normalized_style = canonicalize_style_key(str(variant_key))
            if style_keys and normalized_style not in style_keys:
                continue

            calibration = read_calibration(metadata_raw)
            if calibration is None:
                skipped_count += 1
                continue

            reviewed_count += 1
            override = build_override(
                asset_id=asset_id,
                calibration=calibration,
                shelf_depth_scale=float(args.shelf_depth_scale),
            )
            has_manual_family_override = asset_family(asset_id) == "sectional_sofa"
            if (
                calibration.status == "calibrated"
                and calibration.confidence >= float(args.confidence_threshold)
                and not has_manual_family_override
            ):
                skipped_count += 1
                continue

            existing_override = metadata_raw.get("preview_override")
            if isinstance(existing_override, dict) and not args.overwrite:
                skipped_count += 1
                continue

            if override is None:
                skipped_count += 1
                continue

            if args.dry_run:
                print(
                    f"DRY-RUN {asset_id} [{variant_key}] -> {override}"
                )
                applied_count += 1
                continue

            current_asset = update_variant_override(
                asset=current_asset,
                variant_key=str(variant_key),
                override=override,
            )
            repo.upsert_asset(current_asset)
            print(f'Applied preview override to {asset_id} [{variant_key}] -> {override}')
            applied_count += 1

    mode = "dry-run" if args.dry_run else "write"
    print(
        f"Completed panel review pass ({mode}). reviewed={reviewed_count} applied={applied_count} skipped={skipped_count}"
    )


if __name__ == "__main__":
    main()
