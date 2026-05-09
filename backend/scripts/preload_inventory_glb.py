from __future__ import annotations

import argparse
import multiprocessing
import re
import shutil
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
    import objaverse
    import torch
    from huggingface_hub import hf_hub_download
    from torch.nn import functional as F
    from transformers import AutoTokenizer, CLIPTextModelWithProjection
except ImportError as exc:  # pragma: no cover - handled at runtime
    objaverse = None
    torch = None
    hf_hub_download = None
    F = None
    AutoTokenizer = None
    CLIPTextModelWithProjection = None
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

if TYPE_CHECKING:
    from db import PostgresAssetRepository
    from db.models import Asset

EMBEDDINGS_DATASET = "OpenShape/openshape-objaverse-embeddings"
EMBEDDINGS_FILE = "objaverse.pt"
TEXT_MODEL_NAME = "laion/CLIP-ViT-bigG-14-laion2B-39B-b160k"
DEFAULT_CHUNK_SIZE = 4096
DEFAULT_MODELS_PUBLIC_DIR = Path("frontend/public/assets/inventory_models")
DEFAULT_MODELS_URL_PREFIX = "/assets/inventory_models"
REFILL_OBJECT_ID_PATTERN = re.compile(
    r"__(?:reintroduced|accessory_refill)(?:_\d+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RetrievalQuery:
    asset: Asset
    style: str
    style_key: str
    material: str | None
    style_tags: tuple[str, ...]

    @property
    def asset_id(self) -> str:
        return str(self.asset.id)


def ensure_retrieval_dependencies() -> None:
    if _IMPORT_ERROR is None:
        return
    raise RuntimeError(
        "Missing optional dependencies for GLB retrieval. "
        "Install: objaverse, torch, transformers, huggingface-hub."
    ) from _IMPORT_ERROR


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def strip_reintroduced_suffix(value: str) -> str:
    stripped = REFILL_OBJECT_ID_PATTERN.sub("", value).strip()
    return stripped or value.strip()


def safe_filename_segment(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return normalized or "asset"


def unique_style_keys(style_tags: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for tag in style_tags:
        style_key = canonicalize_style_key(tag)
        if not style_key or style_key in seen:
            continue
        seen.add(style_key)
        ordered.append(style_key)
    return ordered


def get_device(device_name: str) -> torch.device:
    ensure_retrieval_dependencies()
    if device_name != "auto":
        return torch.device(device_name)

    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def get_model_dtype(device: torch.device) -> torch.dtype:
    if device.type in {"cuda", "mps"}:
        return torch.float16
    return torch.float32


def preprocess_object_name(asset_id: str) -> str:
    normalized_id = strip_reintroduced_suffix(asset_id)
    without_digits = re.sub(r"\d", "", normalized_id)
    words = re.sub(r"[_-]+", " ", without_digits)
    collapsed = " ".join(words.split())
    return collapsed or normalized_id


def build_query_text(query: RetrievalQuery) -> str:
    object_name = preprocess_object_name(query.asset_id)
    style_context = (
        f" Catalog style tags: {', '.join(query.style_tags)}."
        if query.style_tags
        else ""
    )
    material_fragment = f" with {query.material} material" if query.material else ""
    return (
        f"A high-poly {object_name}{material_fragment} in {query.style} style, high quality."
        f"{style_context}"
    )


def load_text_encoder(
    device: torch.device,
) -> tuple[CLIPTextModelWithProjection, AutoTokenizer]:
    ensure_retrieval_dependencies()
    dtype = get_model_dtype(device)
    tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME, use_fast=True)
    model = CLIPTextModelWithProjection.from_pretrained(
        TEXT_MODEL_NAME,
        low_cpu_mem_usage=True,
        torch_dtype=dtype,
        use_safetensors=False,
    )
    model.to(device)
    model.eval()
    return model, tokenizer


def encode_queries(
    texts: Sequence[str],
    model: CLIPTextModelWithProjection,
    tokenizer: AutoTokenizer,
) -> torch.Tensor:
    device = next(model.parameters()).device
    tokens = tokenizer(
        list(texts),
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=77,
    )
    tokens = tokens.to(device)
    with torch.inference_mode():
        text_embeds = model(**tokens).text_embeds
    return text_embeds.float().cpu()


def load_embedding_store(local_dir: Path) -> tuple[Sequence[str], torch.Tensor]:
    ensure_retrieval_dependencies()
    embedding_path = hf_hub_download(
        EMBEDDINGS_DATASET,
        EMBEDDINGS_FILE,
        token=True,
        repo_type="dataset",
        local_dir=str(local_dir),
    )

    try:
        payload = torch.load(embedding_path, map_location="cpu", mmap=True)
    except TypeError:
        payload = torch.load(embedding_path, map_location="cpu")

    return payload["us"], payload["feats"]


def retrieve_top_matches(
    query_embedding: torch.Tensor,
    feats: torch.Tensor,
    uids: Sequence[str],
    *,
    top_k: int,
    sim_threshold: float,
    chunk_size: int,
) -> list[tuple[str, float]]:
    normalized_query = F.normalize(query_embedding, dim=-1).squeeze(0)

    best_sims = torch.empty(0, dtype=torch.float32)
    best_indices = torch.empty(0, dtype=torch.long)
    offset = 0

    for chunk in torch.split(feats, chunk_size):
        normalized_chunk = F.normalize(chunk.float(), dim=-1)
        chunk_sims = normalized_query @ normalized_chunk.T

        if sim_threshold > 0.0:
            keep_mask = chunk_sims > sim_threshold
            if not bool(keep_mask.any()):
                offset += len(chunk)
                continue
            candidate_indices = torch.nonzero(keep_mask, as_tuple=False).squeeze(1)
            candidate_sims = chunk_sims[candidate_indices]
        else:
            candidate_indices = torch.arange(len(chunk), dtype=torch.long)
            candidate_sims = chunk_sims

        candidate_indices = candidate_indices + offset

        if best_sims.numel() == 0:
            merged_sims = candidate_sims
            merged_indices = candidate_indices
        else:
            merged_sims = torch.cat((best_sims, candidate_sims))
            merged_indices = torch.cat((best_indices, candidate_indices))

        keep_count = min(top_k, merged_sims.numel())
        best_sims, top_positions = torch.topk(merged_sims, k=keep_count)
        best_indices = merged_indices[top_positions]
        offset += len(chunk)

    return [
        (str(uids[tensor_index]), float(similarity))
        for tensor_index, similarity in zip(
            best_indices.tolist(), best_sims.tolist(), strict=True
        )
    ]


def clear_device_cache(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.empty_cache()
        return

    if device.type == "mps" and hasattr(torch, "mps"):
        empty_cache = getattr(torch.mps, "empty_cache", None)
        if callable(empty_cache):
            empty_cache()


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
        repo.list_assets(AssetFilter(tenant_id=TenantId(tenant_id), type="FURNITURE"))
    )

    normalized_ids = {
        strip_reintroduced_suffix(asset_id).strip()
        for asset_id in (asset_ids or [])
        if asset_id.strip()
    }
    if normalized_ids:
        assets = [
            asset
            for asset in assets
            if strip_reintroduced_suffix(str(asset.id)) in normalized_ids
        ]

    assets.sort(key=lambda asset: str(asset.id))
    if limit is not None and limit > 0:
        return assets[:limit]
    return assets


def build_retrieval_queries(
    assets: Sequence[Asset],
    *,
    style: str | None,
    all_styles: bool,
) -> list[RetrievalQuery]:
    queries: list[RetrievalQuery] = []
    for asset in assets:
        style_tags = tuple(
            str(tag).strip() for tag in asset.style_tags if str(tag).strip()
        )
        if all_styles:
            style_keys = unique_style_keys(style_tags)
            style_values = style_keys
        else:
            resolved_style = (style or "").strip()
            if not resolved_style:
                continue
            style_values = [resolved_style]

        if not style_values:
            continue

        for style_value in style_values:
            style_key = canonicalize_style_key(style_value)
            queries.append(
                RetrievalQuery(
                    asset=asset,
                    style=style_value,
                    style_key=style_key,
                    material=asset.material.strip()
                    if isinstance(asset.material, str) and asset.material.strip()
                    else None,
                    style_tags=style_tags,
                )
            )
    return queries


def get_existing_variant_metadata(
    asset: Asset,
    *,
    style_key: str,
) -> dict[str, object] | None:
    attributes = dict(asset.attributes or {})
    variants_raw = attributes.get("model_variants")
    if not isinstance(variants_raw, dict):
        return None

    for key, value in variants_raw.items():
        if canonicalize_style_key(str(key)) != style_key:
            continue
        if isinstance(value, dict):
            return dict(value)
    return None


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


def build_tenant_model_url_prefix(*, tenant_id: str, models_url_prefix: str) -> str:
    prefix = "/" + models_url_prefix.strip("/").replace("\\", "/")
    return f"{prefix}/{safe_filename_segment(tenant_id)}/"


def collect_model_file_paths(
    *,
    metadata: dict[str, object],
    models_public_dir: Path,
    models_url_prefix: str,
) -> set[Path]:
    paths: set[Path] = set()
    local_path = metadata.get("local_path")
    if isinstance(local_path, str) and local_path.strip():
        paths.add(Path(local_path))

    url = metadata.get("url")
    if isinstance(url, str):
        resolved = model_url_to_path(
            url=url,
            models_public_dir=models_public_dir,
            models_url_prefix=models_url_prefix,
        )
        if resolved is not None:
            paths.add(resolved)
    return {path for path in paths if path.suffix.lower() == ".glb"}


def reset_existing_models(
    *,
    repo: PostgresAssetRepository,
    assets: Sequence[Asset],
    tenant_id: str,
    style: str | None,
    all_styles: bool,
    models_public_dir: Path,
    models_url_prefix: str,
) -> tuple[int, int]:
    tenant_url_prefix = build_tenant_model_url_prefix(
        tenant_id=tenant_id,
        models_url_prefix=models_url_prefix,
    )
    target_style_key = canonicalize_style_key(style) if style else None
    updated_assets = 0
    deleted_files = 0

    for asset in assets:
        attributes = dict(asset.attributes or {})
        variants_raw = attributes.get("model_variants")
        variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
        kept_variants: dict[str, object] = {}
        removed_urls: set[str] = set()
        removed_paths: set[Path] = set()

        for key, value in variants.items():
            normalized_key = canonicalize_style_key(str(key))
            should_remove = all_styles or normalized_key == target_style_key
            if should_remove and isinstance(value, dict):
                url = value.get("url")
                if isinstance(url, str) and url.strip():
                    removed_urls.add(url)
                removed_paths.update(
                    collect_model_file_paths(
                        metadata=value,
                        models_public_dir=models_public_dir,
                        models_url_prefix=models_url_prefix,
                    )
                )
                continue
            kept_variants[key] = value

        if kept_variants:
            attributes["model_variants"] = kept_variants
        else:
            attributes.pop("model_variants", None)

        top_level_model = attributes.get("model_3d")
        top_level_url: str | None = None
        if isinstance(top_level_model, dict):
            top_level_raw_url = top_level_model.get("url")
            if isinstance(top_level_raw_url, str) and top_level_raw_url.strip():
                top_level_url = top_level_raw_url
        elif (
            isinstance(attributes.get("model_url"), str)
            and str(attributes["model_url"]).strip()
        ):
            top_level_url = str(attributes["model_url"]).strip()

        should_clear_top_level = False
        if top_level_url is not None:
            should_clear_top_level = (
                top_level_url.startswith(tenant_url_prefix)
                if all_styles
                else top_level_url in removed_urls
            )
        if should_clear_top_level:
            if isinstance(top_level_model, dict):
                removed_paths.update(
                    collect_model_file_paths(
                        metadata=top_level_model,
                        models_public_dir=models_public_dir,
                        models_url_prefix=models_url_prefix,
                    )
                )
            attributes.pop("model_3d", None)
            attributes.pop("model_url", None)

        attributes_changed = attributes != dict(asset.attributes or {})
        for path in removed_paths:
            if path.exists():
                path.unlink()
                deleted_files += 1

        if attributes_changed:
            updated_asset = asset.model_copy(update={"attributes": attributes})
            repo.upsert_asset(updated_asset)
            updated_assets += 1

    return updated_assets, deleted_files


def download_asset_file(
    *,
    uid: str,
    destination_path: Path,
    overwrite: bool,
    download_processes: int,
) -> None:
    ensure_retrieval_dependencies()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists() and not overwrite:
        return

    # This helper always downloads a single UID, so extra workers only add
    # multiprocessing overhead without increasing throughput.
    downloaded_files = objaverse.load_objects(
        uids=[uid],
        download_processes=1,
    )
    source_path_str = next(iter(downloaded_files.values()), None)
    if not source_path_str:
        raise FileNotFoundError(f"Objaverse download returned no file for uid={uid}.")

    source_path = Path(source_path_str)
    if not source_path.exists():
        raise FileNotFoundError(
            f"Downloaded file does not exist for uid={uid}: {source_path}"
        )

    if destination_path.exists():
        destination_path.unlink()
    shutil.copy2(source_path, destination_path)


def build_public_model_url(
    *,
    tenant_id: str,
    asset_id: str,
    style_key: str,
    models_url_prefix: str,
) -> str:
    prefix = "/" + models_url_prefix.strip("/").replace("\\", "/")
    filename = f"{safe_filename_segment(asset_id)}.glb"
    return f"{prefix}/{safe_filename_segment(tenant_id)}/{safe_filename_segment(style_key)}/{filename}"


def build_destination_path(
    *,
    tenant_id: str,
    asset_id: str,
    style_key: str,
    models_public_dir: Path,
) -> Path:
    return (
        models_public_dir
        / safe_filename_segment(tenant_id)
        / safe_filename_segment(style_key)
        / f"{safe_filename_segment(asset_id)}.glb"
    )


def build_model_metadata(
    *,
    query: RetrievalQuery,
    query_text: str,
    uid: str,
    similarity: float,
    public_url: str,
    destination_path: Path,
    candidate_results: Sequence[tuple[str, float]],
) -> dict[str, object]:
    return {
        "url": public_url,
        "fit": "contain",
        "source": "objaverse",
        "objaverse_uid": uid,
        "similarity": similarity,
        "query_text": query_text,
        "style": query.style,
        "style_key": query.style_key,
        "catalog_style_tags": list(query.style_tags),
        "material": query.material,
        "local_path": str(destination_path),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "top_candidates": [
            {"uid": candidate_uid, "similarity": candidate_similarity}
            for candidate_uid, candidate_similarity in candidate_results
        ],
    }


def persist_model_metadata(
    *,
    repo: PostgresAssetRepository,
    asset: Asset,
    style_key: str,
    metadata: dict[str, object],
) -> None:
    attributes = dict(asset.attributes or {})
    variants_raw = attributes.get("model_variants")
    variants = dict(variants_raw) if isinstance(variants_raw, dict) else {}
    variants[style_key] = metadata
    attributes["model_variants"] = variants
    attributes["model_3d"] = metadata
    attributes["model_url"] = metadata.get("url")
    updated_asset = asset.model_copy(update={"attributes": attributes})
    repo.upsert_asset(updated_asset)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pre-retrieve Objaverse GLB models for inventory assets and store model metadata in the DB."
        )
    )
    parser.add_argument(
        "--tenant-id",
        default="demo_tenant",
        help="Tenant id whose inventory assets should be processed.",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="User style prompt used to retrieve the GLB variants.",
    )
    parser.add_argument(
        "--all-styles",
        action="store_true",
        help="Preload every style_tag variant found on each inventory asset.",
    )
    parser.add_argument(
        "--asset-ids",
        nargs="*",
        default=None,
        help="Optional subset of asset ids to process.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of assets to process after filtering.",
    )
    parser.add_argument(
        "--embeddings-dir",
        type=Path,
        default=Path("OpenShape-Embeddings"),
        help="Directory used to cache the downloaded Objaverse embeddings.",
    )
    parser.add_argument(
        "--models-public-dir",
        type=Path,
        default=DEFAULT_MODELS_PUBLIC_DIR,
        help="Directory where retrieved GLB files should be stored for the UI to serve.",
    )
    parser.add_argument(
        "--models-url-prefix",
        default=DEFAULT_MODELS_URL_PREFIX,
        help="Public URL prefix that maps to the models-public-dir directory.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=1,
        help="Number of retrieved candidates per asset.",
    )
    parser.add_argument(
        "--sim-threshold",
        type=float,
        default=0.1,
        help="Minimum similarity score to keep a retrieved candidate.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Embedding chunk size used during similarity search.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps"),
        default="auto",
        help="Device used for the text encoder.",
    )
    parser.add_argument(
        "--download-processes",
        type=int,
        default=min(4, multiprocessing.cpu_count()),
        help="Number of worker processes used when downloading GLB assets.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download the GLB and overwrite stored metadata even if it already exists.",
    )
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Delete existing stored GLB files and clear DB metadata before retrieving again.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Run retrieval without downloading files. Existing files can still be re-linked in DB.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    ensure_retrieval_dependencies()

    device = get_device(args.device)
    print(f"Device: {device}")

    if not args.all_styles and (args.style is None or not str(args.style).strip()):
        raise ValueError(
            "Provide --style, or use --all-styles to preload all inventory style_tags."
        )

    assets = load_inventory_assets(
        tenant_id=args.tenant_id,
        asset_ids=args.asset_ids,
        limit=args.limit,
    )
    if not assets:
        raise ValueError("No inventory assets found for the requested filters.")

    from db import PostgresAssetRepository

    repo = PostgresAssetRepository()
    if args.reset_existing:
        print("Resetting existing inventory GLB metadata and files...")
        reset_assets, reset_files = reset_existing_models(
            repo=repo,
            assets=assets,
            tenant_id=args.tenant_id,
            style=args.style,
            all_styles=bool(args.all_styles),
            models_public_dir=args.models_public_dir,
            models_url_prefix=args.models_url_prefix,
        )
        print(f"Reset complete. assets={reset_assets} deleted_files={reset_files}")
        assets = load_inventory_assets(
            tenant_id=args.tenant_id,
            asset_ids=args.asset_ids,
            limit=args.limit,
        )

    queries = build_retrieval_queries(
        assets,
        style=args.style,
        all_styles=bool(args.all_styles),
    )
    if not queries:
        raise ValueError(
            "No retrieval queries were generated from the selected inventory assets."
        )
    query_texts = [build_query_text(query) for query in queries]

    print(f"Loading text encoder for {len(queries)} inventory asset(s)...")
    text_model, tokenizer = load_text_encoder(device)
    query_embeddings = encode_queries(query_texts, text_model, tokenizer)
    del text_model
    del tokenizer
    clear_device_cache(device)

    print("Loading Objaverse embeddings...")
    uids, feats = load_embedding_store(args.embeddings_dir)
    print(f"Loaded {len(uids)} Objaverse asset embeddings.")

    processed_count = 0
    skipped_count = 0

    for query, query_text, query_embedding in zip(
        queries,
        query_texts,
        query_embeddings,
        strict=True,
    ):
        destination_path = build_destination_path(
            tenant_id=args.tenant_id,
            asset_id=query.asset_id,
            style_key=query.style_key,
            models_public_dir=args.models_public_dir,
        )
        public_url = build_public_model_url(
            tenant_id=args.tenant_id,
            asset_id=query.asset_id,
            style_key=query.style_key,
            models_url_prefix=args.models_url_prefix,
        )

        if not args.overwrite:
            existing_metadata = get_existing_variant_metadata(
                query.asset,
                style_key=query.style_key,
            )
            if existing_metadata:
                existing_url = existing_metadata.get("url")
                if isinstance(existing_url, str):
                    existing_path = model_url_to_path(
                        url=existing_url,
                        models_public_dir=args.models_public_dir,
                        models_url_prefix=args.models_url_prefix,
                    )
                    if existing_path and existing_path.exists():
                        print(
                            f"Skipping {query.asset_id}: existing GLB variant found for style '{query.style_key}'."
                        )
                        skipped_count += 1
                        continue

        results = retrieve_top_matches(
            query_embedding.unsqueeze(0),
            feats,
            uids,
            top_k=args.top_k,
            sim_threshold=args.sim_threshold,
            chunk_size=args.chunk_size,
        )
        if not results:
            print(f"No match found for {query.asset_id}.")
            continue

        best_uid, best_similarity = results[0]
        print(
            f"{query.asset_id}: best uid={best_uid} sim={best_similarity:.4f} style={query.style_key}"
        )

        if not args.skip_download:
            download_asset_file(
                uid=best_uid,
                destination_path=destination_path,
                overwrite=args.overwrite,
                download_processes=args.download_processes,
            )
        elif not destination_path.exists():
            print(
                f"Skipping DB update for {query.asset_id}: --skip-download was set and {destination_path} does not exist."
            )
            continue

        metadata = build_model_metadata(
            query=query,
            query_text=query_text,
            uid=best_uid,
            similarity=best_similarity,
            public_url=public_url,
            destination_path=destination_path,
            candidate_results=results,
        )
        persist_model_metadata(
            repo=repo,
            asset=query.asset,
            style_key=query.style_key,
            metadata=metadata,
        )
        processed_count += 1

    print(
        f"Finished preloading inventory GLBs. updated={processed_count} skipped={skipped_count} total={len(queries)}"
    )


if __name__ == "__main__":
    main()
