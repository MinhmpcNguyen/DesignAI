from __future__ import annotations

import argparse
import itertools
import shutil
import sys
from collections.abc import Iterable, Sequence
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

    from db.models import Asset


DEFAULT_MODELS_PUBLIC_DIR = Path("frontend/public/assets/inventory_models")
DEFAULT_MODELS_URL_PREFIX = "/assets/inventory_models"
DEFAULT_BACKUP_TAG = "pre_normalize"
DIRECT_STYLE_KEY = "__direct__"


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
class NormalizationResult:
    rotation_label: str
    rotation_matrix: tuple[tuple[float, float, float, float], ...]
    before_bounds_m: tuple[float, float, float]
    after_bounds_m: tuple[float, float, float]
    target_dimensions_mm: tuple[float, float, float] | None
    mesh_count: int


def ensure_dependencies() -> None:
    if _IMPORT_ERROR is None:
        return
    raise RuntimeError(
        "Missing optional dependencies for GLB normalization. "
        "Install: trimesh, numpy."
    ) from _IMPORT_ERROR


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


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


def build_backup_path(path: Path, backup_tag: str) -> Path:
    normalized_tag = backup_tag.strip().strip(".") or DEFAULT_BACKUP_TAG
    return path.with_name(f"{path.stem}.{normalized_tag}{path.suffix}")


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


def as_float_array(values: Iterable[float]) -> npt.NDArray[np.float64]:
    ensure_dependencies()
    return np.asarray(list(values), dtype=np.float64)


def normalize_extent_signature(
    extents: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    safe = np.maximum(extents.astype(np.float64), 1e-9)
    return safe / float(np.max(safe))


def compute_bounds_from_meshes(
    meshes: Sequence[trimesh.Trimesh],
) -> BoundsSummary:
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


def choose_rotation_matrix(
    *,
    base_extents: npt.NDArray[np.float64],
    target_dimensions_mm: tuple[float, float, float] | None,
) -> tuple[str, npt.NDArray[np.float64]]:
    ensure_dependencies()
    if target_dimensions_mm is None:
        return "identity", np.eye(3, dtype=np.float64)

    target_signature = normalize_extent_signature(
        as_float_array(target_dimensions_mm)
    )
    best_label = "identity"
    best_matrix = np.eye(3, dtype=np.float64)
    best_score = float("inf")

    for label, matrix in ROTATION_CANDIDATES:
        rotated_extents = np.abs(matrix) @ base_extents
        candidate_signature = normalize_extent_signature(rotated_extents)
        score = float(np.sum(np.abs(candidate_signature - target_signature)))
        if score < best_score:
            best_score = score
            best_label = label
            best_matrix = matrix

    return best_label, best_matrix


def to_transform_matrix(
    rotation: npt.NDArray[np.float64],
    translation: npt.NDArray[np.float64] | None = None,
) -> npt.NDArray[np.float64]:
    ensure_dependencies()
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    if translation is not None:
        transform[:3, 3] = translation
    return transform


def target_dimensions_mm(asset: Asset) -> tuple[float, float, float] | None:
    dimensions = asset.dimensions
    if dimensions is None:
        return None
    if (
        dimensions.length_mm is None
        or dimensions.width_mm is None
        or dimensions.height_mm is None
    ):
        return None
    return (
        float(dimensions.length_mm),
        float(dimensions.height_mm),
        float(dimensions.width_mm),
    )


def normalize_scene(
    *,
    scene: trimesh.Scene,
    target_dims_mm: tuple[float, float, float] | None,
    allow_axis_rotation: bool,
) -> NormalizationResult:
    ensure_dependencies()
    before = compute_scene_bounds(scene)
    if allow_axis_rotation:
        rotation_label, rotation_matrix = choose_rotation_matrix(
            base_extents=before.extents,
            target_dimensions_mm=target_dims_mm,
        )
    else:
        rotation_label = "identity"
        rotation_matrix = np.eye(3, dtype=np.float64)
    scene.apply_transform(to_transform_matrix(rotation_matrix))

    after_rotation = compute_scene_bounds(scene)
    translation = np.asarray(
        [
            -float(after_rotation.center[0]),
            -float(after_rotation.minimum[1]),
            -float(after_rotation.center[2]),
        ],
        dtype=np.float64,
    )
    scene.apply_transform(to_transform_matrix(np.eye(3, dtype=np.float64), translation))
    after = compute_scene_bounds(scene)

    return NormalizationResult(
        rotation_label=rotation_label,
        rotation_matrix=tuple(
            tuple(float(value) for value in row)
            for row in to_transform_matrix(rotation_matrix)
        ),
        before_bounds_m=tuple(float(value) for value in before.extents),
        after_bounds_m=tuple(float(value) for value in after.extents),
        target_dimensions_mm=target_dims_mm,
        mesh_count=after.mesh_count,
    )


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


def export_scene(scene: trimesh.Scene, path: Path) -> None:
    exported = scene.export(file_type="glb")
    if not isinstance(exported, (bytes, bytearray)):
        raise TypeError(f"Failed to export GLB bytes for {path}.")
    path.write_bytes(bytes(exported))


def build_normalization_metadata(
    *,
    previous_metadata: dict[str, object],
    result: NormalizationResult,
    backup_path: Path | None,
    allow_axis_rotation: bool,
) -> dict[str, object]:
    updated = dict(previous_metadata)
    updated["preview_normalized"] = True
    updated["preview_normalization"] = {
        "rotation_label": result.rotation_label,
        "rotation_matrix": [list(row) for row in result.rotation_matrix],
        "before_bounds_m": list(result.before_bounds_m),
        "after_bounds_m": list(result.after_bounds_m),
        "target_dimensions_mm": (
            list(result.target_dimensions_mm)
            if result.target_dimensions_mm is not None
            else None
        ),
        "allow_axis_rotation": allow_axis_rotation,
        "mesh_count": result.mesh_count,
        "backup_path": str(backup_path) if backup_path is not None else None,
        "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return updated


def persist_variant_metadata(
    *,
    asset: Asset,
    repo: object,
    variant: VariantTarget,
    updated_metadata: dict[str, object],
) -> None:
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


def persist_restored_metadata(
    *,
    asset: Asset,
    repo: object,
    variant: VariantTarget,
    backup_path: Path,
) -> None:
    attributes = dict(asset.attributes or {})
    current_metadata = dict(variant.metadata)
    current_metadata.pop("preview_normalized", None)
    current_metadata.pop("preview_normalization", None)
    current_metadata["preview_restored_at_utc"] = datetime.now(timezone.utc).isoformat()
    current_metadata["preview_restore_backup_path"] = str(backup_path)

    if variant.use_top_level_only:
        attributes["model_3d"] = current_metadata
        attributes["model_url"] = current_metadata.get("url")
    else:
        variants_raw = attributes.get("model_variants")
        variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
        variants[variant.metadata_key] = current_metadata
        attributes["model_variants"] = variants

        current_model = attributes.get("model_3d")
        if isinstance(current_model, dict) and current_model.get("url") == variant.public_url:
            attributes["model_3d"] = current_metadata
            attributes["model_url"] = current_metadata.get("url")

    updated_asset = asset.model_copy(update={"attributes": attributes})
    repo.upsert_asset(updated_asset)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize existing inventory GLB files in place by baking an axis-aligned "
            "rotation, centering them, and placing the model on the floor."
        )
    )
    parser.add_argument(
        "--tenant-id",
        default="demo_tenant",
        help="Tenant id whose inventory assets should be normalized.",
    )
    parser.add_argument(
        "--asset-ids",
        nargs="*",
        default=None,
        help="Optional subset of asset ids to normalize.",
    )
    parser.add_argument(
        "--style-keys",
        nargs="*",
        default=None,
        help="Optional subset of style keys to normalize. Defaults to every stored variant.",
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
        "--backup-tag",
        default=DEFAULT_BACKUP_TAG,
        help="Tag inserted before the .glb suffix for backups.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-normalize even when preview_normalized metadata already exists.",
    )
    parser.add_argument(
        "--allow-axis-rotation",
        action="store_true",
        help="Also rotate GLBs to best-match inventory axis dimensions. Disabled by default because it can flip object facing.",
    )
    parser.add_argument(
        "--restore-backups",
        action="store_true",
        help="Restore each GLB from its backup file and clear preview_normalized metadata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect targets and planned changes without writing files or DB rows.",
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

    normalized_count = 0
    skipped_count = 0
    failed_count = 0

    for asset in assets:
        variants = iter_variant_targets(
            asset=asset,
            models_public_dir=args.models_public_dir,
            models_url_prefix=args.models_url_prefix,
            style_keys=style_keys,
        )
        if not variants:
            print(f"Skipping {asset.id}: no stored GLB metadata found.")
            skipped_count += 1
            continue

        for variant in variants:
            normalization_metadata = variant.metadata.get("preview_normalization")
            backup_path = build_backup_path(variant.path, args.backup_tag)
            if args.restore_backups:
                if not backup_path.exists():
                    print(
                        f"Skipping {asset.id} [{variant.style_key}]: backup file not found at {backup_path}."
                    )
                    skipped_count += 1
                    continue
                print(
                    f"Restore {asset.id} [{variant.style_key}] from {backup_path.name}"
                )
                if args.dry_run:
                    normalized_count += 1
                    continue
                shutil.copy2(backup_path, variant.path)
                persist_restored_metadata(
                    asset=asset,
                    repo=repo,
                    variant=variant,
                    backup_path=backup_path,
                )
                normalized_count += 1
                continue

            if (
                not args.overwrite
                and variant.metadata.get("preview_normalized") is True
                and isinstance(normalization_metadata, dict)
            ):
                print(
                    f"Skipping {asset.id} [{variant.style_key}]: preview_normalized metadata already present."
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
                target_dims = target_dimensions_mm(asset)
                result = normalize_scene(
                    scene=scene,
                    target_dims_mm=target_dims,
                    allow_axis_rotation=bool(args.allow_axis_rotation),
                )
                print(
                    f"Normalize {asset.id} [{variant.style_key}] "
                    f"pre={tuple(round(v, 4) for v in result.before_bounds_m)} "
                    f"post={tuple(round(v, 4) for v in result.after_bounds_m)} "
                    f"rotation={result.rotation_label}"
                )

                if args.dry_run:
                    normalized_count += 1
                    continue

                if not backup_path.exists():
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(variant.path, backup_path)

                export_scene(scene, variant.path)
                updated_metadata = build_normalization_metadata(
                    previous_metadata=variant.metadata,
                    result=result,
                    backup_path=backup_path,
                    allow_axis_rotation=bool(args.allow_axis_rotation),
                )
                persist_variant_metadata(
                    asset=asset,
                    repo=repo,
                    variant=variant,
                    updated_metadata=updated_metadata,
                )
                normalized_count += 1
            except Exception as exc:  # pragma: no cover - runtime surface area
                failed_count += 1
                print(
                    f"Failed {asset.id} [{variant.style_key}] at {variant.path}: {exc}"
                )

    print(
        "Done. "
        f"normalized={normalized_count} skipped={skipped_count} failed={failed_count}"
    )


if __name__ == "__main__":
    main()
