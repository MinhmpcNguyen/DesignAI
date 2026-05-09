from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))

from db import PostgresAssetRepository
from db.models import Asset, AssetFilter, TenantId

DEFAULT_DIRECT_STYLE_KEY = "__direct__"
SUPPORTED_FIT_STRATEGIES = {
    "box",
    "footprint-uniform-or-proxy",
    "footprint",
    "wall-plane",
    "wall-plane-uniform-or-proxy",
    "footprint-uniform",
    "wall-plane-uniform",
}


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def load_inventory_asset(*, tenant_id: str, asset_id: str) -> Asset:
    repo = PostgresAssetRepository()
    assets = list(
        repo.list_assets(
            AssetFilter(tenant_id=TenantId(tenant_id), type="FURNITURE")
        )
    )
    for asset in assets:
        if str(asset.id) == asset_id:
            return asset
    raise ValueError(f'No furniture asset "{asset_id}" was found for tenant "{tenant_id}".')


def find_variant_key(asset: Asset, style_key: str) -> str:
    attributes = dict(asset.attributes or {})
    variants_raw = attributes.get("model_variants")
    if isinstance(variants_raw, dict):
        for key in variants_raw:
            if canonicalize_style_key(str(key)) == style_key:
                return str(key)
    if style_key == DEFAULT_DIRECT_STYLE_KEY:
        return DEFAULT_DIRECT_STYLE_KEY
    available = (
        ", ".join(sorted(str(key) for key in variants_raw))
        if isinstance(variants_raw, dict) and variants_raw
        else "none"
    )
    raise ValueError(
        f'No stored GLB metadata matched style "{style_key}" for asset "{asset.id}". '
        f"Available variants: {available}."
    )


def build_preview_override(args: argparse.Namespace) -> dict[str, object]:
    if args.fit_strategy and args.fit_strategy not in SUPPORTED_FIT_STRATEGIES:
        raise ValueError(
            f'Unsupported fit strategy "{args.fit_strategy}". '
            f"Choose one of: {', '.join(sorted(SUPPORTED_FIT_STRATEGIES))}."
        )

    dimension_scale: dict[str, float] = {}
    if args.width_scale is not None:
        dimension_scale["width"] = float(args.width_scale)
    if args.height_scale is not None:
        dimension_scale["height"] = float(args.height_scale)
    if args.depth_scale is not None:
        dimension_scale["depth"] = float(args.depth_scale)

    override: dict[str, object] = {
        "enabled": not args.disable,
        "contexts": [context.strip().lower() for context in args.contexts if context.strip()],
        "rotation_deg_offset": float(args.rotation_deg_offset or 0),
    }
    if args.fit_strategy:
        override["fit_strategy"] = args.fit_strategy
    if args.scale_multiplier is not None:
        override["scale_multiplier"] = float(args.scale_multiplier)
    if dimension_scale:
        override["dimension_scale"] = dimension_scale
    if args.notes:
        override["notes"] = args.notes.strip()
    return override


def update_asset_metadata(
    *,
    asset: Asset,
    style_key: str,
    override: dict[str, object] | None,
) -> Asset:
    attributes = dict(asset.attributes or {})
    if style_key == DEFAULT_DIRECT_STYLE_KEY:
        model_metadata = attributes.get("model_3d")
        if not isinstance(model_metadata, dict):
            raise ValueError(
                f'Asset "{asset.id}" has no top-level model_3d metadata to update.'
            )
        next_model_metadata = dict(model_metadata)
        if override is None:
            next_model_metadata.pop("preview_override", None)
        else:
            next_model_metadata["preview_override"] = override
        attributes["model_3d"] = next_model_metadata
        if (
            isinstance(attributes.get("model_url"), str)
            and next_model_metadata.get("url") == attributes.get("model_url")
        ):
            attributes["model_url"] = next_model_metadata.get("url")
        return asset.model_copy(update={"attributes": attributes})

    variants_raw = attributes.get("model_variants")
    variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
    variant_key = find_variant_key(asset, style_key)
    variant_metadata_raw = variants.get(variant_key)
    if not isinstance(variant_metadata_raw, dict):
        raise ValueError(
            f'Asset "{asset.id}" style "{variant_key}" has no variant metadata to update.'
        )

    next_variant_metadata = dict(variant_metadata_raw)
    if override is None:
        next_variant_metadata.pop("preview_override", None)
    else:
        next_variant_metadata["preview_override"] = override
    variants[variant_key] = next_variant_metadata
    attributes["model_variants"] = variants

    current_model = attributes.get("model_3d")
    if isinstance(current_model, dict) and current_model.get("url") == next_variant_metadata.get("url"):
        if override is None:
            next_model_metadata = dict(current_model)
            next_model_metadata.pop("preview_override", None)
        else:
            next_model_metadata = dict(current_model)
            next_model_metadata["preview_override"] = override
        attributes["model_3d"] = next_model_metadata
        attributes["model_url"] = next_model_metadata.get("url")

    return asset.model_copy(update={"attributes": attributes})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set or clear a per-asset GLB preview override for a stored inventory model variant."
        )
    )
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument(
        "--style-key",
        required=True,
        help='Style variant key, or "__direct__" for top-level model_3d.',
    )
    parser.add_argument("--fit-strategy", default=None)
    parser.add_argument("--rotation-deg-offset", type=float, default=0.0)
    parser.add_argument("--scale-multiplier", type=float, default=None)
    parser.add_argument("--width-scale", type=float, default=None)
    parser.add_argument("--height-scale", type=float, default=None)
    parser.add_argument("--depth-scale", type=float, default=None)
    parser.add_argument("--contexts", nargs="*", default=["panel"])
    parser.add_argument("--notes", default=None)
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    style_key = canonicalize_style_key(args.style_key)
    asset = load_inventory_asset(tenant_id=args.tenant_id, asset_id=args.asset_id)
    override = None if args.clear else build_preview_override(args)
    updated_asset = update_asset_metadata(
        asset=asset,
        style_key=style_key,
        override=override,
    )

    if args.dry_run:
        print(f"Dry run for {asset.id} [{style_key}]")
        print(updated_asset.attributes)
        return

    repo = PostgresAssetRepository()
    repo.upsert_asset(updated_asset)
    action = "Cleared" if override is None else "Stored"
    print(f"{action} preview override for {asset.id} [{style_key}].")


if __name__ == "__main__":
    main()
