from __future__ import annotations

import argparse
import itertools
import math
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))

try:
    import numpy as np
    import trimesh
except ImportError as exc:  # pragma: no cover - handled at runtime
    np = None
    trimesh = None
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

if TYPE_CHECKING:
    import numpy.typing as npt

    from db import PostgresAssetRepository
    from db.models import Asset


DEFAULT_MODELS_PUBLIC_DIR = Path("frontend/public/assets/inventory_models")
DEFAULT_MODELS_URL_PREFIX = "/assets/inventory_models"
DIRECT_STYLE_KEY = "__direct__"
TRAILING_NUMERIC_ASSET_SUFFIX_PATTERN = r"(?:[_-]\d+)+$"


@dataclass(frozen=True)
class VariantTarget:
    style_key: str
    metadata_key: str
    path: Path
    metadata: dict[str, object]
    public_url: str
    use_top_level_only: bool = False


@dataclass(frozen=True)
class BoundsSummary:
    minimum: npt.NDArray[np.float64]
    maximum: npt.NDArray[np.float64]
    extents: npt.NDArray[np.float64]
    center: npt.NDArray[np.float64]
    dominant_max_dim: float
    mesh_count: int


@dataclass(frozen=True)
class CandidateEvaluation:
    label: str
    transform_matrix: tuple[tuple[float, float, float, float], ...]
    bounds: BoundsSummary
    dimension_penalty: float
    semantic_penalty: float
    total_penalty: float


@dataclass(frozen=True)
class CalibrationResult:
    best: CandidateEvaluation
    runner_up: CandidateEvaluation | None
    confidence: float
    status: str
    target_dimensions_mm: tuple[float, float, float] | None


def ensure_dependencies() -> None:
    if _IMPORT_ERROR is None:
        return
    raise RuntimeError(
        "Missing optional dependencies for GLB calibration. "
        "Install: trimesh, numpy."
    ) from _IMPORT_ERROR


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def canonicalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def infer_object_type(asset: Asset) -> str:
    attributes = dict(asset.attributes or {})
    raw_category = attributes.get("category")
    if isinstance(raw_category, str) and raw_category.strip():
        return raw_category.strip()

    asset_id = str(asset.id).strip()
    normalized = canonicalize_token(asset_id)
    category = re.sub(TRAILING_NUMERIC_ASSET_SUFFIX_PATTERN, "", normalized).strip("_")
    return category or asset_id


def clamp_number(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def model_url_to_path(
    *,
    url: str,
    models_public_dir: Path,
    models_url_prefix: str,
) -> Path | None:
    normalized_prefix = "/" + models_url_prefix.strip("/").replace("\\", "/")
    normalized_url = url.strip()
    if not normalized_url.startswith(normalized_prefix):
        return None
    relative = normalized_url.removeprefix(normalized_prefix).lstrip("/")
    if not relative:
        return None
    return models_public_dir / Path(relative)


def load_inventory_assets(
    *,
    tenant_id: str,
    asset_ids: Sequence[str] | None,
    limit: int | None,
) -> list[Asset]:
    from db import PostgresAssetRepository
    from db.models import AssetFilter, TenantId

    repo = PostgresAssetRepository()
    assets = list(
        repo.list_assets(
            AssetFilter(tenant_id=TenantId(tenant_id), type="FURNITURE")
        )
    )
    normalized_asset_ids = {
        str(asset_id).strip()
        for asset_id in (asset_ids or [])
        if str(asset_id).strip()
    }
    if normalized_asset_ids:
        assets = [asset for asset in assets if str(asset.id) in normalized_asset_ids]
    assets.sort(key=lambda asset: str(asset.id))
    if limit is not None:
        assets = assets[: max(0, int(limit))]
    return assets


def iter_variant_targets(
    *,
    asset: Asset,
    models_public_dir: Path,
    models_url_prefix: str,
    style_keys: set[str] | None,
) -> list[VariantTarget]:
    attributes = dict(asset.attributes or {})
    targets: list[VariantTarget] = []

    variants_raw = attributes.get("model_variants")
    if isinstance(variants_raw, dict):
        for metadata_key, raw_metadata in variants_raw.items():
            if not isinstance(raw_metadata, dict):
                continue
            style_key = canonicalize_style_key(str(metadata_key))
            if style_keys and style_key not in style_keys:
                continue
            public_url = str(raw_metadata.get("url") or "").strip()
            if not public_url:
                continue
            path = model_url_to_path(
                url=public_url,
                models_public_dir=models_public_dir,
                models_url_prefix=models_url_prefix,
            )
            if path is None:
                continue
            targets.append(
                VariantTarget(
                    style_key=style_key,
                    metadata_key=str(metadata_key),
                    path=path,
                    metadata=dict(raw_metadata),
                    public_url=public_url,
                )
            )

    if targets:
        return targets

    top_level_raw = attributes.get("model_3d")
    if not isinstance(top_level_raw, dict):
        return []
    public_url = str(top_level_raw.get("url") or attributes.get("model_url") or "").strip()
    if not public_url:
        return []
    path = model_url_to_path(
        url=public_url,
        models_public_dir=models_public_dir,
        models_url_prefix=models_url_prefix,
    )
    if path is None:
        return []
    return [
        VariantTarget(
            style_key=DIRECT_STYLE_KEY,
            metadata_key=DIRECT_STYLE_KEY,
            path=path,
            metadata=dict(top_level_raw),
            public_url=public_url,
            use_top_level_only=True,
        )
    ]


def compute_bounds_from_meshes(meshes: Sequence[trimesh.Trimesh]) -> BoundsSummary:
    ensure_dependencies()
    entries: list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], float, float]] = []
    for mesh in meshes:
        if not isinstance(mesh, trimesh.Trimesh):
            continue
        if mesh.vertices.size == 0:
            continue
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        if bounds.shape != (2, 3):
            continue
        minimum = bounds[0]
        maximum = bounds[1]
        extents = np.maximum(maximum - minimum, 1e-9)
        volume = float(np.prod(extents))
        max_dim = float(np.max(extents))
        entries.append((minimum, maximum, volume, max_dim))

    if not entries:
        minimum = np.zeros(3, dtype=np.float64)
        maximum = np.ones(3, dtype=np.float64) * 1e-6
        extents = maximum - minimum
        return BoundsSummary(
            minimum=minimum,
            maximum=maximum,
            extents=extents,
            center=(minimum + maximum) / 2.0,
            dominant_max_dim=float(np.max(extents)),
            mesh_count=0,
        )

    entries.sort(key=lambda item: item[2], reverse=True)
    dominant_volume = max(entries[0][2], 1e-9)
    dominant_max_dim = max(entries[0][3], 1e-6)
    seeded_entries = [
        entry
        for index, entry in enumerate(entries)
        if index < 12 or entry[2] >= dominant_volume * 0.01
    ]
    weighted_center = np.zeros(3, dtype=np.float64)
    total_weight = 0.0
    for minimum, maximum, volume, _ in seeded_entries:
        weighted_center += ((minimum + maximum) / 2.0) * volume
        total_weight += volume
    if total_weight > 0:
        weighted_center /= total_weight

    distance_limit = max(dominant_max_dim * 3.0, 0.25)
    kept_entries = [
        entry
        for index, entry in enumerate(seeded_entries)
        if index == 0
        or float(np.linalg.norm(((entry[0] + entry[1]) / 2.0) - weighted_center))
        <= distance_limit
    ]
    final_entries = kept_entries or seeded_entries

    minimum = np.min(np.stack([entry[0] for entry in final_entries]), axis=0)
    maximum = np.max(np.stack([entry[1] for entry in final_entries]), axis=0)
    extents = np.maximum(maximum - minimum, 1e-9)
    return BoundsSummary(
        minimum=minimum,
        maximum=maximum,
        extents=extents,
        center=(minimum + maximum) / 2.0,
        dominant_max_dim=dominant_max_dim,
        mesh_count=len(final_entries),
    )


def extract_scene_meshes(scene: trimesh.Scene) -> list[trimesh.Trimesh]:
    dumped = scene.dump(concatenate=False)
    if isinstance(dumped, list):
        return [mesh for mesh in dumped if isinstance(mesh, trimesh.Trimesh)]
    if isinstance(dumped, trimesh.Trimesh):
        return [dumped]
    return []


def compute_scene_bounds(scene: trimesh.Scene) -> BoundsSummary:
    return compute_bounds_from_meshes(extract_scene_meshes(scene))


def build_rotation_candidates() -> list[tuple[str, npt.NDArray[np.float64]]]:
    ensure_dependencies()
    candidates: list[tuple[str, npt.NDArray[np.float64]]] = []
    identity = np.eye(3, dtype=np.float64)
    axes = np.eye(3, dtype=np.float64)
    for permutation in itertools.permutations(range(3)):
        permuted = axes[:, permutation]
        for signs in itertools.product((-1.0, 1.0), repeat=3):
            candidate = permuted * np.asarray(signs, dtype=np.float64)
            if np.linalg.det(candidate) < 0.9:
                continue
            if any(np.allclose(candidate, existing, atol=1e-8) for _, existing in candidates):
                continue
            if np.allclose(candidate, identity, atol=1e-8):
                label = "identity"
            else:
                label = f"perm={permutation},signs={tuple(int(sign) for sign in signs)}"
            candidates.append((label, candidate))
    return candidates


ROTATION_CANDIDATES = build_rotation_candidates() if _IMPORT_ERROR is None else []


def to_transform_matrix(
    rotation: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    ensure_dependencies()
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    return transform


def load_scene(path: Path) -> trimesh.Scene:
    ensure_dependencies()
    loaded = trimesh.load(path, force="scene", process=False)
    if isinstance(loaded, trimesh.Scene):
        return loaded
    if isinstance(loaded, trimesh.Trimesh):
        scene = trimesh.Scene()
        scene.add_geometry(loaded)
        return scene
    raise TypeError(f"Unsupported GLB payload at {path}: {type(loaded)!r}")


def target_dimensions_mm(asset: Asset) -> tuple[float, float, float] | None:
    dimensions = asset.dimensions
    if dimensions is None:
        return None
    if (
        dimensions.width_mm is None
        or dimensions.height_mm is None
        or dimensions.length_mm is None
    ):
        return None
    return (
        float(dimensions.width_mm),
        float(dimensions.height_mm),
        float(dimensions.length_mm),
    )


def dimension_penalty(
    candidate_dims_mm: tuple[float, float, float],
    target_dims_mm: tuple[float, float, float] | None,
) -> float:
    if target_dims_mm is None:
        return 0.0

    weights = (0.45, 0.25, 0.30)
    total = 0.0
    for candidate_dim, target_dim, weight in zip(
        candidate_dims_mm,
        target_dims_mm,
        weights,
        strict=True,
    ):
        safe_candidate = max(candidate_dim, 1.0)
        safe_target = max(target_dim, 1.0)
        total += abs(math.log(safe_candidate / safe_target)) * weight
    return total


def semantic_penalty(
    *,
    object_type: str,
    width_mm: float,
    height_mm: float,
    depth_mm: float,
) -> float:
    token = canonicalize_token(object_type)
    penalty = 0.0
    widest = max(width_mm, depth_mm, 1.0)

    if any(
        keyword in token
        for keyword in (
            "sofa",
            "sectional",
            "bed",
            "bench",
            "console",
            "tv_console",
            "media_shelf",
            "desk",
            "table",
            "sideboard",
        )
    ) and width_mm < depth_mm:
        penalty += 0.50

    if any(
        keyword in token
        for keyword in ("mirror", "wall_art", "clock", "art")
    ):
        if depth_mm > min(width_mm, height_mm) * 0.25:
            penalty += 0.50

    if any(
        keyword in token
        for keyword in ("bookshelf", "bookcase", "storage_cabinet", "wardrobe", "etagere")
    ):
        if height_mm < widest:
            penalty += 0.35
        if width_mm < depth_mm * 0.9:
            penalty += 0.20

    if "shelf" in token and height_mm < max(width_mm, depth_mm) * 0.65:
        penalty += 0.15

    if "lamp" in token and height_mm < widest:
        penalty += 0.25

    if any(keyword in token for keyword in ("chair", "armchair")):
        ratio = width_mm / max(depth_mm, 1.0)
        if ratio < 0.55 or ratio > 1.9:
            penalty += 0.15

    return penalty


def evaluate_candidate(
    *,
    scene: trimesh.Scene,
    label: str,
    rotation: npt.NDArray[np.float64],
    object_type: str,
    target_dims_mm: tuple[float, float, float] | None,
) -> CandidateEvaluation:
    scene_copy = scene.copy()
    transform_matrix = to_transform_matrix(rotation)
    scene_copy.apply_transform(transform_matrix)
    bounds = compute_scene_bounds(scene_copy)
    candidate_dims_mm = (
        float(bounds.extents[0] * 1000.0),
        float(bounds.extents[1] * 1000.0),
        float(bounds.extents[2] * 1000.0),
    )
    dim_penalty = dimension_penalty(candidate_dims_mm, target_dims_mm)
    shape_penalty = semantic_penalty(
        object_type=object_type,
        width_mm=candidate_dims_mm[0],
        height_mm=candidate_dims_mm[1],
        depth_mm=candidate_dims_mm[2],
    )
    identity_bias = 0.0 if label == "identity" else 0.02
    total_penalty = dim_penalty + shape_penalty + identity_bias
    return CandidateEvaluation(
        label=label,
        transform_matrix=tuple(
            tuple(float(cell) for cell in row)
            for row in transform_matrix
        ),
        bounds=bounds,
        dimension_penalty=dim_penalty,
        semantic_penalty=shape_penalty,
        total_penalty=total_penalty,
    )


def compute_confidence(
    best: CandidateEvaluation,
    runner_up: CandidateEvaluation | None,
) -> float:
    best_component = 1.0 - clamp_number(best.total_penalty / 1.6, 0.0, 1.0)
    gap = (
        runner_up.total_penalty - best.total_penalty
        if runner_up is not None
        else 0.45
    )
    gap_component = clamp_number(gap / 0.45, 0.0, 1.0) * 0.25
    return clamp_number(best_component * 0.75 + gap_component, 0.0, 0.99)


def calibrate_scene(
    *,
    scene: trimesh.Scene,
    object_type: str,
    target_dims_mm: tuple[float, float, float] | None,
    confidence_threshold: float,
) -> CalibrationResult:
    evaluations = [
        evaluate_candidate(
            scene=scene,
            label=label,
            rotation=rotation,
            object_type=object_type,
            target_dims_mm=target_dims_mm,
        )
        for label, rotation in ROTATION_CANDIDATES
    ]
    evaluations.sort(key=lambda item: item.total_penalty)
    best = evaluations[0]
    runner_up = evaluations[1] if len(evaluations) > 1 else None
    confidence = compute_confidence(best, runner_up)
    status = "calibrated" if confidence >= confidence_threshold else "needs_review"
    return CalibrationResult(
        best=best,
        runner_up=runner_up,
        confidence=confidence,
        status=status,
        target_dimensions_mm=target_dims_mm,
    )


def describe_axis_assignment(
    transform_matrix: tuple[tuple[float, float, float, float], ...]
) -> dict[str, str]:
    axis_names = ("x", "y", "z")

    def _row_to_axis(row: tuple[float, float, float, float]) -> str:
        absolute_values = [abs(row[index]) for index in range(3)]
        axis_index = absolute_values.index(max(absolute_values))
        sign = "+" if row[axis_index] >= 0 else "-"
        return f"{sign}{axis_names[axis_index]}"

    return {
        "width": _row_to_axis(transform_matrix[0]),
        "height": _row_to_axis(transform_matrix[1]),
        "depth": _row_to_axis(transform_matrix[2]),
    }


def build_calibration_payload(
    *,
    result: CalibrationResult,
) -> dict[str, object]:
    bounds = result.best.bounds
    pivot_offset = {
        "x": float(-bounds.center[0]),
        "y": float(-bounds.minimum[1]),
        "z": float(-bounds.center[2]),
    }
    top_candidates = [
        {
            "rotation_label": candidate.label,
            "total_penalty": round(candidate.total_penalty, 6),
            "dimension_penalty": round(candidate.dimension_penalty, 6),
            "semantic_penalty": round(candidate.semantic_penalty, 6),
            "base_size_m": {
                "width": round(float(candidate.bounds.extents[0]), 6),
                "height": round(float(candidate.bounds.extents[1]), 6),
                "depth": round(float(candidate.bounds.extents[2]), 6),
            },
        }
        for candidate in [result.best, result.runner_up]
        if candidate is not None
    ]
    return {
        "version": 1,
        "status": result.status,
        "confidence": round(result.confidence, 4),
        "bounds_mode": "filtered_meshes",
        "fit_policy": "inherit_runtime",
        "floor_anchor": "min_y",
        "rotation_label": result.best.label,
        "rotation_matrix": [list(row) for row in result.best.transform_matrix],
        "axis_assignment": describe_axis_assignment(result.best.transform_matrix),
        "base_size_m": {
            "width": round(float(bounds.extents[0]), 6),
            "height": round(float(bounds.extents[1]), 6),
            "depth": round(float(bounds.extents[2]), 6),
        },
        "pivot_offset_m": {
            key: round(value, 6) for key, value in pivot_offset.items()
        },
        "mesh_filter": {
            "remove_outliers": True,
            "min_volume_ratio": 0.01,
            "max_center_distance_ratio": 3.0,
        },
        "target_dimensions_mm": (
            {
                "width": round(result.target_dimensions_mm[0], 3),
                "height": round(result.target_dimensions_mm[1], 3),
                "depth": round(result.target_dimensions_mm[2], 3),
            }
            if result.target_dimensions_mm is not None
            else None
        ),
        "top_candidates": top_candidates,
        "calibrated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_updated_metadata(
    *,
    previous_metadata: dict[str, object],
    calibration_payload: dict[str, object],
) -> dict[str, object]:
    updated = dict(previous_metadata)
    updated["preview_calibration"] = calibration_payload
    updated["preview_calibrated"] = calibration_payload["status"] == "calibrated"
    updated["preview_calibration_status"] = calibration_payload["status"]
    return updated


def persist_variant_metadata(
    *,
    asset: Asset,
    repo: PostgresAssetRepository,
    variant: VariantTarget,
    updated_metadata: dict[str, object],
) -> Asset:
    attributes = dict(asset.attributes or {})
    if variant.use_top_level_only:
        attributes["model_3d"] = updated_metadata
        attributes["model_url"] = updated_metadata.get("url")
    else:
        variants_raw = attributes.get("model_variants")
        variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
        variants[variant.metadata_key] = updated_metadata
        attributes["model_variants"] = variants

        current_model = attributes.get("model_3d")
        if isinstance(current_model, dict) and current_model.get("url") == variant.public_url:
            attributes["model_3d"] = updated_metadata
            attributes["model_url"] = updated_metadata.get("url")

    updated_asset = asset.model_copy(update={"attributes": attributes})
    repo.upsert_asset(updated_asset)
    return updated_asset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Infer stable preview calibration metadata for each stored inventory GLB "
            "without modifying the GLB file itself."
        )
    )
    parser.add_argument(
        "--tenant-id",
        default="demo_tenant",
        help="Tenant id whose inventory assets should be calibrated.",
    )
    parser.add_argument(
        "--asset-ids",
        nargs="*",
        default=None,
        help="Optional subset of asset ids to calibrate.",
    )
    parser.add_argument(
        "--style-keys",
        nargs="*",
        default=None,
        help="Optional subset of style keys to calibrate. Defaults to every stored variant.",
    )
    parser.add_argument(
        "--models-public-dir",
        type=Path,
        default=DEFAULT_MODELS_PUBLIC_DIR,
        help="Directory that stores the downloaded inventory GLB files.",
    )
    parser.add_argument(
        "--models-url-prefix",
        default=DEFAULT_MODELS_URL_PREFIX,
        help="Public URL prefix used by the stored model metadata.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute preview_calibration even when it already exists.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.58,
        help="Minimum confidence to mark a calibration as fully calibrated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect targets and print inferred calibration without writing DB rows.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for the number of inventory assets to inspect.",
    )
    return parser.parse_args()


def main() -> None:
    ensure_dependencies()
    load_dotenv()
    args = parse_args()

    from db import PostgresAssetRepository

    repo = PostgresAssetRepository()
    assets = load_inventory_assets(
        tenant_id=str(args.tenant_id),
        asset_ids=args.asset_ids,
        limit=args.limit,
    )
    if not assets:
        raise ValueError("No inventory assets found for the requested filters.")

    style_keys = (
        {canonicalize_style_key(style) for style in args.style_keys if str(style).strip()}
        if args.style_keys
        else None
    )

    calibrated_count = 0
    skipped_count = 0
    failed_count = 0

    for asset in assets:
        current_asset = asset
        variants = iter_variant_targets(
            asset=current_asset,
            models_public_dir=args.models_public_dir,
            models_url_prefix=args.models_url_prefix,
            style_keys=style_keys,
        )
        if not variants:
            print(f"Skipping {asset.id}: no stored GLB metadata found.")
            skipped_count += 1
            continue

        target_dims = target_dimensions_mm(asset)

        for variant in variants:
            existing_calibration = variant.metadata.get("preview_calibration")
            if not args.overwrite and isinstance(existing_calibration, dict):
                print(
                    f"Skipping {asset.id} [{variant.style_key}]: preview_calibration already present."
                )
                skipped_count += 1
                continue

            if not variant.path.exists():
                print(
                    f"Skipping {asset.id} [{variant.style_key}]: GLB file not found at {variant.path}."
                )
                skipped_count += 1
                continue

            try:
                scene = load_scene(variant.path)
                result = calibrate_scene(
                    scene=scene,
                    object_type=infer_object_type(asset),
                    target_dims_mm=target_dims,
                    confidence_threshold=float(args.confidence_threshold),
                )
                best_dims = tuple(round(float(value), 4) for value in result.best.bounds.extents)
                print(
                    f"Calibrate {asset.id} [{variant.style_key}] "
                    f"status={result.status} conf={result.confidence:.3f} "
                    f"size_m={best_dims} rotation={result.best.label}"
                )

                if args.dry_run:
                    calibrated_count += 1
                    continue

                calibration_payload = build_calibration_payload(result=result)
                updated_metadata = build_updated_metadata(
                    previous_metadata=variant.metadata,
                    calibration_payload=calibration_payload,
                )
                current_asset = persist_variant_metadata(
                    asset=current_asset,
                    repo=repo,
                    variant=variant,
                    updated_metadata=updated_metadata,
                )
                calibrated_count += 1
            except Exception as exc:  # pragma: no cover - runtime surface area
                failed_count += 1
                print(
                    f"Failed {asset.id} [{variant.style_key}] at {variant.path}: {exc}"
                )

    print(
        "Done. "
        f"calibrated={calibrated_count} skipped={skipped_count} failed={failed_count}"
    )


if __name__ == "__main__":
    main()
