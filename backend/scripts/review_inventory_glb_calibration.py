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


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def load_inventory_assets(*, tenant_id: str, limit: int | None) -> list[Asset]:
    repo = PostgresAssetRepository()
    assets = list(
        repo.list_assets(
            AssetFilter(tenant_id=TenantId(tenant_id), type="FURNITURE")
        )
    )
    assets.sort(key=lambda asset: str(asset.id))
    if limit is not None:
        return assets[: max(0, int(limit))]
    return assets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List inventory GLB variants whose preview calibration still looks risky and may need per-asset overrides."
        )
    )
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--style-keys", nargs="*", default=None)
    parser.add_argument("--confidence-threshold", type=float, default=0.58)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--show-all", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    assets = load_inventory_assets(tenant_id=args.tenant_id, limit=args.limit)
    if not assets:
      raise ValueError(f'No furniture assets found for tenant "{args.tenant_id}".')

    style_keys = (
        {canonicalize_style_key(style) for style in args.style_keys if style.strip()}
        if args.style_keys
        else None
    )

    total_rows = 0
    for asset in assets:
        variants_raw = dict(asset.attributes or {}).get("model_variants")
        if not isinstance(variants_raw, dict):
            continue
        for key, raw_metadata in variants_raw.items():
            if not isinstance(raw_metadata, dict):
                continue
            normalized_style = canonicalize_style_key(str(key))
            if style_keys and normalized_style not in style_keys:
                continue
            calibration = raw_metadata.get("preview_calibration")
            override = raw_metadata.get("preview_override")
            if not isinstance(calibration, dict):
                if args.show_all:
                    print(f"{asset.id} [{key}] calibration=missing override={'yes' if isinstance(override, dict) else 'no'}")
                    total_rows += 1
                continue

            status = str(calibration.get("status") or "unknown")
            confidence = float(calibration.get("confidence") or 0)
            should_show = (
                args.show_all
                or status != "calibrated"
                or confidence < args.confidence_threshold
                or isinstance(override, dict)
            )
            if not should_show:
                continue

            rotation_label = str(calibration.get("rotation_label") or "n/a")
            print(
                f"{asset.id} [{key}] status={status} conf={confidence:.3f} "
                f"override={'yes' if isinstance(override, dict) else 'no'} "
                f"rotation={rotation_label}"
            )
            total_rows += 1

    print(f"Listed {total_rows} candidate variant(s).")


if __name__ == "__main__":
    main()
