from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))

from db import PostgresAssetRepository
from db.models import Asset, AssetFilter, AssetId, TenantId

JsonObject = dict[str, object]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MODELS_PUBLIC_DIR = Path("frontend/public/assets/inventory_models")
DEFAULT_MODELS_URL_PREFIX = "/assets/inventory_models"
DEFAULT_DIRECT_STYLE_KEY = "__direct__"
DEFAULT_CONTEXTS = ["panel"]
MODEL_FRONT_AXIS_BY_OFFSET = {
    0: "-z",
    90: "+x",
    180: "+z",
    270: "-x",
}


@dataclass(frozen=True)
class GlbVariantTarget:
    style_key: str
    metadata_key: str
    path: Path
    metadata: JsonObject
    public_url: str
    use_top_level_only: bool = False


def canonicalize_style_key(style: str) -> str:
    return " ".join(style.strip().lower().split())


def read_json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def read_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def read_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number else None
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def read_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    strings: list[str] = []
    for item in value:
        text = read_string(item)
        if text is not None:
            strings.append(text)
    return strings


def normalize_cardinal_offset(value: float) -> int:
    normalized = int(round(value / 90.0) * 90) % 360
    if normalized not in MODEL_FRONT_AXIS_BY_OFFSET:
        raise ValueError("Rotation offset must be one of 0, 90, 180, or 270 degrees.")
    return normalized


def normalize_quarter_turn_tilt(value: float) -> int:
    normalized = int(round(value / 90.0) * 90) % 360
    if normalized == 270:
        return -90
    if normalized in {0, 90, 180}:
        return normalized
    raise ValueError("Tilt correction must be one of -90, 0, 90, or 180 degrees.")


def path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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

    candidate = (models_public_dir / Path(relative)).resolve()
    if not path_within(candidate, models_public_dir):
        return None
    return candidate


def dimension_payload(asset: Asset) -> JsonObject | None:
    dimensions = asset.dimensions
    if dimensions is None:
        return None
    return {
        "width_mm": dimensions.width_mm,
        "height_mm": dimensions.height_mm,
        "depth_mm": dimensions.length_mm,
    }


def metadata_rotation_deg(metadata: JsonObject) -> float:
    for key in (
        "rotation_deg",
        "rotationDeg",
        "preview_rotation_deg",
        "previewRotationDeg",
        "yaw_deg",
        "yawDeg",
    ):
        value = read_number(metadata.get(key))
        if value is not None:
            return value
    return 0.0


def preview_override_offset(metadata: JsonObject) -> float | None:
    override = read_json_object(
        metadata.get("preview_override") or metadata.get("previewOverride")
    )
    if override is None:
        return None
    return read_number(
        override.get("rotation_deg_offset") or override.get("rotationDegOffset")
    )


def preview_override_tilt_deg(metadata: JsonObject, axis: str) -> float | None:
    override = read_json_object(
        metadata.get("preview_override") or metadata.get("previewOverride")
    )
    if override is None:
        return None
    if axis == "x":
        return read_number(
            override.get("rotation_deg_x") or override.get("rotationDegX")
        )
    if axis == "z":
        return read_number(
            override.get("rotation_deg_z") or override.get("rotationDegZ")
        )
    raise ValueError(f"Unsupported tilt axis: {axis}")


class InventoryGlbOrientationInspector:
    def __init__(
        self,
        *,
        tenant_id: str,
        models_public_dir: Path,
        models_url_prefix: str,
        asset_ids: Sequence[str] | None,
        style_keys: Sequence[str] | None,
        limit: int | None,
    ) -> None:
        self._tenant_id = tenant_id
        self._models_public_dir = models_public_dir
        self._models_url_prefix = models_url_prefix
        self._asset_ids = {asset_id.strip() for asset_id in asset_ids or [] if asset_id.strip()}
        self._style_keys = (
            {canonicalize_style_key(style) for style in style_keys if style.strip()}
            if style_keys
            else None
        )
        self._limit = limit
        self._repo = PostgresAssetRepository()

    def list_targets(self) -> list[JsonObject]:
        targets: list[JsonObject] = []
        for asset in self._load_assets():
            for variant in self._iter_variant_targets(asset):
                targets.append(self._serialize_target(asset, variant))
        targets.sort(
            key=lambda row: (
                str(row.get("display_label") or "").lower(),
                str(row.get("style_key") or ""),
                str(row.get("asset_id") or ""),
            )
        )
        return targets

    def resolve_model_path(self, *, asset_id: str, style_key: str) -> Path:
        asset, variant = self._find_variant(asset_id=asset_id, style_key=style_key)
        if not variant.path.exists():
            raise FileNotFoundError(
                f'Model file for "{asset.id}" [{variant.style_key}] was not found at {variant.path}.'
            )
        return variant.path

    def save_orientation(self, payload: JsonObject) -> JsonObject:
        asset_id = read_string(payload.get("asset_id"))
        style_key = read_string(payload.get("style_key"))
        if asset_id is None or style_key is None:
            raise ValueError("asset_id and style_key are required.")

        rotation_offset = read_number(payload.get("rotation_deg_offset"))
        if rotation_offset is None:
            raise ValueError("rotation_deg_offset is required.")
        normalized_offset = normalize_cardinal_offset(rotation_offset)
        rotation_x_deg = normalize_quarter_turn_tilt(
            read_number(payload.get("rotation_deg_x")) or 0.0
        )
        rotation_z_deg = normalize_quarter_turn_tilt(
            read_number(payload.get("rotation_deg_z")) or 0.0
        )

        contexts = [
            context.strip().lower()
            for context in read_string_list(payload.get("contexts"))
            if context.strip()
        ]
        if not contexts:
            contexts = list(DEFAULT_CONTEXTS)

        notes = read_string(payload.get("notes"))
        asset, variant = self._find_variant(asset_id=asset_id, style_key=style_key)
        updated_metadata = self._build_updated_metadata(
            metadata=variant.metadata,
            rotation_offset=normalized_offset,
            rotation_x_deg=rotation_x_deg,
            rotation_z_deg=rotation_z_deg,
            contexts=contexts,
            notes=notes,
        )

        updated_asset = self._persist_variant_metadata(
            asset=asset,
            variant=variant,
            updated_metadata=updated_metadata,
        )
        self._repo.upsert_asset(updated_asset)

        return {
            "ok": True,
            "asset_id": str(asset.id),
            "style_key": variant.style_key,
            "rotation_deg_offset": normalized_offset,
            "rotation_deg_x": rotation_x_deg,
            "rotation_deg_z": rotation_z_deg,
            "front_axis": MODEL_FRONT_AXIS_BY_OFFSET[normalized_offset],
            "contexts": contexts,
        }

    def delete_variant(self, payload: JsonObject) -> JsonObject:
        asset_id = read_string(payload.get("asset_id"))
        style_key = read_string(payload.get("style_key"))
        if asset_id is None or style_key is None:
            raise ValueError("asset_id and style_key are required.")

        asset, variant = self._find_variant(asset_id=asset_id, style_key=style_key)
        attributes = dict(asset.attributes or {})
        removed_paths = self._collect_model_paths(variant.metadata)

        if variant.use_top_level_only:
            attributes.pop("model_3d", None)
            attributes.pop("model_url", None)
        else:
            variants_raw = read_json_object(attributes.get("model_variants")) or {}
            variants_raw.pop(variant.metadata_key, None)
            if variants_raw:
                attributes["model_variants"] = variants_raw
            else:
                attributes.pop("model_variants", None)

            top_level_model = read_json_object(attributes.get("model_3d"))
            top_level_url = (
                read_string(top_level_model.get("url"))
                if top_level_model is not None
                else read_string(attributes.get("model_url"))
            )
            if top_level_url == variant.public_url:
                if top_level_model is not None:
                    removed_paths.update(self._collect_model_paths(top_level_model))
                attributes.pop("model_3d", None)
                attributes.pop("model_url", None)

        updated_asset = asset.model_copy(update={"attributes": attributes})
        self._repo.upsert_asset(updated_asset)

        deleted_paths: list[str] = []
        if read_bool(payload.get("delete_file")):
            for path in sorted(removed_paths, key=str):
                if not path.exists():
                    continue
                if path.suffix.lower() != ".glb" or not path_within(
                    path,
                    self._models_public_dir,
                ):
                    continue
                path.unlink()
                deleted_paths.append(str(path))

        return {
            "ok": True,
            "asset_id": str(asset.id),
            "style_key": variant.style_key,
            "deleted_paths": deleted_paths,
        }

    def _load_assets(self) -> list[Asset]:
        assets = list(
            self._repo.list_assets(
                AssetFilter(tenant_id=TenantId(self._tenant_id), type="FURNITURE")
            )
        )
        if self._asset_ids:
            assets = [asset for asset in assets if str(asset.id) in self._asset_ids]
        assets.sort(key=lambda asset: str(asset.id))
        if self._limit is not None:
            assets = assets[: max(0, self._limit)]
        return assets

    def _iter_variant_targets(self, asset: Asset) -> list[GlbVariantTarget]:
        attributes = dict(asset.attributes or {})
        targets: list[GlbVariantTarget] = []

        variants_raw = read_json_object(attributes.get("model_variants"))
        if variants_raw is not None:
            for metadata_key, raw_metadata in variants_raw.items():
                metadata = read_json_object(raw_metadata)
                if metadata is None:
                    continue
                style_key = canonicalize_style_key(metadata_key)
                if self._style_keys and style_key not in self._style_keys:
                    continue
                public_url = read_string(metadata.get("url"))
                if public_url is None:
                    continue
                path = model_url_to_path(
                    url=public_url,
                    models_public_dir=self._models_public_dir,
                    models_url_prefix=self._models_url_prefix,
                )
                if path is None:
                    continue
                targets.append(
                    GlbVariantTarget(
                        style_key=style_key,
                        metadata_key=metadata_key,
                        path=path,
                        metadata=metadata,
                        public_url=public_url,
                    )
                )

        if targets:
            return targets

        model_metadata = read_json_object(attributes.get("model_3d"))
        if model_metadata is None:
            return []
        public_url = read_string(model_metadata.get("url")) or read_string(
            attributes.get("model_url")
        )
        if public_url is None:
            return []
        path = model_url_to_path(
            url=public_url,
            models_public_dir=self._models_public_dir,
            models_url_prefix=self._models_url_prefix,
        )
        if path is None:
            return []
        return [
            GlbVariantTarget(
                style_key=DEFAULT_DIRECT_STYLE_KEY,
                metadata_key=DEFAULT_DIRECT_STYLE_KEY,
                path=path,
                metadata=model_metadata,
                public_url=public_url,
                use_top_level_only=True,
            )
        ]

    def _find_variant(self, *, asset_id: str, style_key: str) -> tuple[Asset, GlbVariantTarget]:
        asset = self._repo.get_asset(AssetId(asset_id))
        if asset is None or str(asset.tenant_id) != self._tenant_id or asset.type != "FURNITURE":
            raise ValueError(
                f'No furniture asset "{asset_id}" was found for tenant "{self._tenant_id}".'
            )

        normalized_style_key = canonicalize_style_key(style_key)
        for variant in self._iter_variant_targets(asset):
            if canonicalize_style_key(variant.style_key) == normalized_style_key:
                return asset, variant

        available = ", ".join(variant.style_key for variant in self._iter_variant_targets(asset))
        raise ValueError(
            f'No GLB variant "{style_key}" was found for asset "{asset_id}". '
            f"Available variants: {available or 'none'}."
        )

    def _serialize_target(self, asset: Asset, variant: GlbVariantTarget) -> JsonObject:
        metadata = variant.metadata
        category = read_string(dict(asset.attributes or {}).get("category"))
        display_label = f"{asset.name} - {variant.style_key} ({asset.id})"
        override = read_json_object(
            metadata.get("preview_override") or metadata.get("previewOverride")
        )
        calibration = read_json_object(
            metadata.get("preview_calibration") or metadata.get("previewCalibration")
        )
        orientation_review = read_json_object(
            metadata.get("orientation_review") or metadata.get("orientationReview")
        )
        offset = preview_override_offset(metadata)
        normalized_offset = normalize_cardinal_offset(offset) if offset is not None else 0
        rotation_x_deg = normalize_quarter_turn_tilt(
            preview_override_tilt_deg(metadata, "x") or 0.0
        )
        rotation_z_deg = normalize_quarter_turn_tilt(
            preview_override_tilt_deg(metadata, "z") or 0.0
        )
        model_url = (
            "/api/model?"
            f"asset_id={quote(str(asset.id), safe='')}"
            f"&style_key={quote(variant.style_key, safe='')}"
        )
        return {
            "asset_id": str(asset.id),
            "name": asset.name,
            "display_label": display_label,
            "style_key": variant.style_key,
            "metadata_key": variant.metadata_key,
            "category": category,
            "material": asset.material,
            "brand": asset.brand,
            "dimensions": dimension_payload(asset),
            "public_url": variant.public_url,
            "model_url": model_url,
            "file_exists": variant.path.exists(),
            "local_path": str(variant.path),
            "base_rotation_deg": metadata_rotation_deg(metadata),
            "rotation_deg_offset": normalized_offset,
            "rotation_deg_x": rotation_x_deg,
            "rotation_deg_z": rotation_z_deg,
            "front_axis": MODEL_FRONT_AXIS_BY_OFFSET[normalized_offset],
            "preview_override": override,
            "preview_calibration": calibration,
            "orientation_review": orientation_review,
        }

    def _build_updated_metadata(
        self,
        *,
        metadata: JsonObject,
        rotation_offset: int,
        rotation_x_deg: int,
        rotation_z_deg: int,
        contexts: list[str],
        notes: str | None,
    ) -> JsonObject:
        updated = dict(metadata)
        override = read_json_object(
            updated.get("preview_override") or updated.get("previewOverride")
        ) or {}
        override["enabled"] = True
        override["contexts"] = contexts
        override["rotation_deg_offset"] = float(rotation_offset)
        override["rotation_deg_x"] = float(rotation_x_deg)
        override["rotation_deg_z"] = float(rotation_z_deg)
        override["notes"] = notes or "Manual GLB orientation review."
        updated["preview_override"] = override
        updated["orientation_review"] = {
            "version": 1,
            "status": "reviewed",
            "front_axis": MODEL_FRONT_AXIS_BY_OFFSET[rotation_offset],
            "rotation_deg_offset": float(rotation_offset),
            "rotation_deg_x": float(rotation_x_deg),
            "rotation_deg_z": float(rotation_z_deg),
            "reference_front": "2D plan +Y / 3D scene -Z",
            "contexts": contexts,
            "notes": notes,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        return updated

    def _persist_variant_metadata(
        self,
        *,
        asset: Asset,
        variant: GlbVariantTarget,
        updated_metadata: JsonObject,
    ) -> Asset:
        attributes = dict(asset.attributes or {})
        if variant.use_top_level_only:
            attributes["model_3d"] = updated_metadata
            attributes["model_url"] = updated_metadata.get("url")
            return asset.model_copy(update={"attributes": attributes})

        variants_raw = read_json_object(attributes.get("model_variants")) or {}
        variants_raw[variant.metadata_key] = updated_metadata
        attributes["model_variants"] = variants_raw

        current_model = read_json_object(attributes.get("model_3d"))
        if current_model is not None and current_model.get("url") == updated_metadata.get("url"):
            attributes["model_3d"] = updated_metadata
            attributes["model_url"] = updated_metadata.get("url")

        return asset.model_copy(update={"attributes": attributes})

    def _collect_model_paths(self, metadata: JsonObject) -> set[Path]:
        paths: set[Path] = set()
        local_path = read_string(metadata.get("local_path"))
        if local_path is not None:
            candidate = Path(local_path).expanduser()
            if not candidate.is_absolute():
                candidate = ROOT_DIR / candidate
            paths.add(candidate.resolve())

        public_url = read_string(metadata.get("url"))
        if public_url is not None:
            resolved = model_url_to_path(
                url=public_url,
                models_public_dir=self._models_public_dir,
                models_url_prefix=self._models_url_prefix,
            )
            if resolved is not None:
                paths.add(resolved.resolve())

        return paths


class OrientationInspectorRequestHandler(BaseHTTPRequestHandler):
    inspector: InventoryGlbOrientationInspector
    vendor_dir: Path
    server_version = "InventoryGlbOrientationInspector/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in ("/", "/index.html"):
                self._send_bytes(
                    HTML_APP.encode("utf-8"),
                    content_type="text/html; charset=utf-8",
                )
                return
            if parsed.path == "/api/targets":
                self._send_json({"targets": self.inspector.list_targets()})
                return
            if parsed.path == "/api/model":
                params = parse_qs(parsed.query)
                asset_id = params.get("asset_id", [""])[0]
                style_key = params.get("style_key", [""])[0]
                model_path = self.inspector.resolve_model_path(
                    asset_id=asset_id,
                    style_key=style_key,
                )
                self._send_file(model_path, default_content_type="model/gltf-binary")
                return
            if parsed.path.startswith("/vendor/"):
                self._send_vendor_file(parsed.path.removeprefix("/vendor/"))
                return
            self._send_json(
                {"error": "Not found."},
                status=HTTPStatus.NOT_FOUND,
            )
        except Exception as exc:
            self._send_json(
                {"error": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path != "/api/orientation":
                self._send_json(
                    {"error": "Not found."},
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            payload = self._read_json_body()
            response = self.inspector.save_orientation(payload)
            self._send_json(response)
        except Exception as exc:
            self._send_json(
                {"error": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json_body(self) -> JsonObject:
        raw_length = self.headers.get("Content-Length")
        length = int(raw_length) if raw_length and raw_length.isdigit() else 0
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        decoded = json.loads(raw_body.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("JSON body must be an object.")
        return {str(key): value for key, value in decoded.items()}

    def _send_json(
        self,
        payload: JsonObject,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self._send_bytes(
            json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            content_type="application/json; charset=utf-8",
            status=status,
        )

    def _send_file(self, path: Path, *, default_content_type: str) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or default_content_type
        self._send_bytes(path.read_bytes(), content_type=content_type)

    def _send_vendor_file(self, relative_path: str) -> None:
        allowed_files = {
            "three.module.js": self.vendor_dir / "three.module.js",
            "OrbitControls.js": self.vendor_dir / "OrbitControls.js",
            "loaders/GLTFLoader.js": self.vendor_dir / "loaders" / "GLTFLoader.js",
        }
        vendor_path = allowed_files.get(relative_path)
        if vendor_path is None or not vendor_path.exists():
            self._send_json(
                {"error": "Vendor file not found."},
                status=HTTPStatus.NOT_FOUND,
            )
            return
        self._send_file(vendor_path, default_content_type="text/javascript")

    def _send_bytes(
        self,
        body: bytes,
        *,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


HTML_APP = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Inventory GLB Orientation Inspector</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111315;
      --panel: #1b2024;
      --panel-2: #242a2f;
      --text: #f1f3f5;
      --muted: #aab3bd;
      --line: #384149;
      --accent: #e0b15a;
      --accent-2: #74c0fc;
      --danger: #ff8787;
      --ok: #8ce99a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, select, textarea {
      font: inherit;
    }
    button {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      color: var(--text);
      min-height: 36px;
      padding: 7px 10px;
      cursor: pointer;
    }
    button:hover { border-color: var(--accent); }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #1c1609;
      font-weight: 700;
    }
    button.active {
      border-color: var(--accent-2);
      box-shadow: inset 0 0 0 1px var(--accent-2);
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0e1012;
      color: var(--text);
      padding: 8px 10px;
    }
    select {
      min-height: 38px;
    }
    textarea { resize: vertical; min-height: 60px; }
    label { color: var(--muted); font-size: 12px; }
    .app {
      display: grid;
      grid-template-columns: minmax(260px, 340px) minmax(420px, 1fr) minmax(280px, 360px);
      min-height: 100vh;
    }
    .sidebar, .details {
      border-right: 1px solid var(--line);
      background: var(--panel);
      min-height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .details { border-right: 0; border-left: 1px solid var(--line); }
    .head {
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }
    .head h1, .head h2 {
      margin: 0;
      font-size: 16px;
      letter-spacing: 0;
    }
    .head p {
      color: var(--muted);
      margin: 6px 0 0;
      font-size: 12px;
    }
    .search {
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
    }
    .search-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      margin-top: 10px;
    }
    .mini-button {
      min-width: 58px;
      padding-inline: 10px;
    }
    .list-status {
      min-height: 18px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .list-status.error { color: var(--danger); }
    .list-status.ok { color: var(--ok); }
    .list {
      overflow: auto;
      padding: 8px;
    }
    .alpha-header {
      color: var(--accent);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0;
      padding: 10px 8px 6px;
      text-transform: uppercase;
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      margin: 8px;
      padding: 12px;
      font-size: 12px;
    }
    .item {
      display: block;
      width: 100%;
      text-align: left;
      border-radius: 8px;
      padding: 10px;
      margin: 0 0 8px;
      background: #171b1f;
    }
    .item-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--text);
      font-weight: 700;
    }
    .item-meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 11px;
      min-height: 22px;
      padding: 2px 8px;
      white-space: nowrap;
    }
    .pill.ok { color: var(--ok); border-color: rgba(140, 233, 154, 0.45); }
    .pill.warn { color: var(--accent); border-color: rgba(224, 177, 90, 0.45); }
    .viewer {
      position: relative;
      min-height: 100vh;
      background: #121416;
    }
    #canvas {
      width: 100%;
      height: 100vh;
      display: block;
    }
    .overlay {
      position: absolute;
      left: 16px;
      bottom: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      pointer-events: none;
    }
    .overlay-box {
      max-width: 520px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 8px;
      background: rgba(12, 14, 16, 0.78);
      backdrop-filter: blur(10px);
      padding: 10px 12px;
      color: var(--muted);
      pointer-events: auto;
    }
    .overlay-box strong { color: var(--text); }
    .control-stack {
      padding: 16px;
      overflow: auto;
    }
    .section {
      border-bottom: 1px solid var(--line);
      padding: 0 0 16px;
      margin: 0 0 16px;
    }
    .section:last-child {
      border-bottom: 0;
      margin-bottom: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .kv {
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr);
      gap: 6px 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .kv strong {
      color: var(--text);
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .status {
      min-height: 20px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--ok); }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-size: 13px;
    }
    .check input { width: auto; }
    @media (max-width: 980px) {
      .app {
        grid-template-columns: 1fr;
      }
      .sidebar, .details {
        min-height: auto;
        max-height: 44vh;
        border: 0;
      }
      .details { border-top: 1px solid var(--line); }
      #canvas { height: 58vh; }
      .viewer { min-height: 58vh; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="head">
        <h1>GLB Orientation Inspector</h1>
        <p>Pick a stored inventory GLB, align its real front with the white plan-front arrow, then save.</p>
      </div>
      <div class="search">
        <label for="target-select">Objects A-Z</label>
        <select id="target-select">
          <option value="">Loading objects...</option>
        </select>
        <div class="search-grid">
          <input id="search" type="search" placeholder="Search asset, style, category">
          <button id="clear-search" class="mini-button">Clear</button>
        </div>
        <div id="list-status" class="list-status">Loading GLB targets...</div>
      </div>
      <div id="list" class="list"></div>
    </aside>

    <main class="viewer">
      <canvas id="canvas"></canvas>
      <div class="overlay">
        <div class="overlay-box">
          <strong>White arrow</strong> is the 2D plan front direction (+Y in plan, -Z in 3D).
          Rotate until the actual furniture front faces that arrow.
        </div>
        <div class="overlay-box">
          Keys: Q/E rotate, [/] previous/next, S save.
        </div>
      </div>
    </main>

    <aside class="details">
      <div class="head">
        <h2 id="selected-title">No model selected</h2>
        <p id="selected-subtitle">Load targets from the database to begin.</p>
      </div>
      <div class="control-stack">
        <section class="section">
          <div class="kv" id="metadata"></div>
        </section>
        <section class="section">
          <label>Choose which local model axis is the furniture front</label>
          <div class="grid" style="margin-top: 8px;">
            <button data-offset="0">Front is -Z</button>
            <button data-offset="90">Front is +X</button>
            <button data-offset="180">Front is +Z</button>
            <button data-offset="270">Front is -X</button>
          </div>
        </section>
        <section class="section">
          <label>Fine controls</label>
          <div class="row" style="margin-top: 8px;">
            <button id="rotate-left">Rotate -90</button>
            <button id="rotate-right">Rotate +90</button>
            <button id="reset-camera">Reset camera</button>
          </div>
        </section>
        <section class="section">
          <label class="check">
            <input id="apply-all" type="checkbox">
            Apply to all 3D contexts
          </label>
          <p style="color: var(--muted); margin: 8px 0 0; font-size: 12px;">
            Leave unchecked to match the current 3D panel behavior. Check it only when the GLB should be corrected everywhere that honors preview overrides.
          </p>
        </section>
        <section class="section">
          <label for="notes">Notes</label>
          <textarea id="notes" placeholder="Example: sofa back was facing plan front, so use 180deg."></textarea>
        </section>
        <button id="save" class="primary" style="width: 100%;">Save orientation to DB</button>
        <div id="status" class="status"></div>
      </div>
    </aside>
  </div>

  <script type="module">
    import * as THREE from '/vendor/three.module.js';
    import { OrbitControls } from '/vendor/OrbitControls.js';
    import { GLTFLoader } from '/vendor/loaders/GLTFLoader.js';

    const state = {
      targets: [],
      filtered: [],
      selectedIndex: -1,
      selected: null,
      draftOffset: 0,
      modelRoot: null,
      labels: [],
    };

    const canvas = document.getElementById('canvas');
    const listEl = document.getElementById('list');
    const listStatusEl = document.getElementById('list-status');
    const searchEl = document.getElementById('search');
    const targetSelectEl = document.getElementById('target-select');
    const clearSearchEl = document.getElementById('clear-search');
    const metadataEl = document.getElementById('metadata');
    const titleEl = document.getElementById('selected-title');
    const subtitleEl = document.getElementById('selected-subtitle');
    const notesEl = document.getElementById('notes');
    const statusEl = document.getElementById('status');
    const applyAllEl = document.getElementById('apply-all');
    const saveEl = document.getElementById('save');
    const loader = new GLTFLoader();
    let renderer = null;
    let scene = null;
    let camera = null;
    let controls = null;
    let world = null;
    let viewerReady = false;

    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setClearColor(0x121416, 1);
      renderer.shadowMap.enabled = true;

      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(42, 1, 0.05, 100);
      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.target.set(0, 0.6, 0);

      world = new THREE.Group();
      scene.add(world);

      scene.add(new THREE.HemisphereLight(0xf4f6f8, 0x2d3033, 1.5));
      const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
      keyLight.position.set(3.5, 5.5, 4);
      keyLight.castShadow = true;
      scene.add(keyLight);

      const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(5, 5),
        new THREE.MeshStandardMaterial({ color: 0x20262b, roughness: 0.86, metalness: 0.02 })
      );
      floor.rotation.x = -Math.PI / 2;
      floor.receiveShadow = true;
      world.add(floor);

      const grid = new THREE.GridHelper(5, 10, 0x6c757d, 0x343a40);
      grid.position.y = 0.002;
      world.add(grid);

      const footprint = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(2.2, 0.02, 1.4)),
        new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 })
      );
      footprint.position.y = 0.02;
      world.add(footprint);

      const frontArrow = new THREE.ArrowHelper(
        new THREE.Vector3(0, 0, -1),
        new THREE.Vector3(0, 0.08, 0.95),
        1.4,
        0xffffff,
        0.22,
        0.12
      );
      world.add(frontArrow);

      addSceneLabel('PLAN FRONT', new THREE.Vector3(0, 0.08, -0.78), '#ffffff');
      addSceneLabel('BACK', new THREE.Vector3(0, 0.08, 0.92), '#adb5bd');
      addSceneLabel('LEFT', new THREE.Vector3(-1.25, 0.08, 0), '#adb5bd');
      addSceneLabel('RIGHT', new THREE.Vector3(1.25, 0.08, 0), '#adb5bd');

      resetCamera();
      window.addEventListener('resize', resize);
      resize();
      viewerReady = true;
      animate();
    } catch (error) {
      setStatus(`3D viewer failed to start: ${error instanceof Error ? error.message : String(error)}`, 'error');
      setListStatus('Object list is still usable, but the 3D viewer failed to start.', 'error');
    }

    function resetCamera() {
      if (!camera || !controls) return;
      camera.position.set(2.8, 2.2, 3.1);
      controls.target.set(0, 0.55, 0);
      controls.update();
    }

    function addSceneLabel(text, position, color) {
      const canvasLabel = document.createElement('canvas');
      canvasLabel.width = 256;
      canvasLabel.height = 64;
      const context = canvasLabel.getContext('2d');
      context.clearRect(0, 0, canvasLabel.width, canvasLabel.height);
      context.font = '700 28px system-ui, sans-serif';
      context.textAlign = 'center';
      context.textBaseline = 'middle';
      context.fillStyle = color;
      context.fillText(text, 128, 32);
      const texture = new THREE.CanvasTexture(canvasLabel);
      const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
      const sprite = new THREE.Sprite(material);
      sprite.position.copy(position);
      sprite.scale.set(0.72, 0.18, 1);
      world?.add(sprite);
      state.labels.push(sprite);
      return sprite;
    }

    function resize() {
      if (!renderer || !camera) return;
      const rect = canvas.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / Math.max(rect.height, 1);
      camera.updateProjectionMatrix();
    }

    function animate() {
      requestAnimationFrame(animate);
      if (!renderer || !scene || !camera || !controls) return;
      controls.update();
      renderer.render(scene, camera);
    }

    async function loadTargets() {
      setStatus('Loading GLB targets from DB...', '');
      setListStatus('Loading GLB targets...', '');
      const response = await fetch('/api/targets');
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || 'Failed to load targets.');
      }
      state.targets = sortTargets(payload.targets || []);
      state.filtered = state.targets;
      renderTargetSelect();
      renderList();
      if (state.filtered.length > 0) {
        await selectTarget(0);
        setListStatus(`Loaded ${state.targets.length} GLB variant(s). Showing all objects A-Z.`, 'ok');
      } else {
        setStatus('No inventory GLB variants were found for this filter.', 'error');
        setListStatus('No inventory GLB variants were found.', 'error');
      }
    }

    function renderList() {
      listEl.innerHTML = '';
      if (state.filtered.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = searchEl.value.trim()
          ? `No GLB objects match "${searchEl.value.trim()}".`
          : 'No GLB objects to show.';
        listEl.appendChild(empty);
        return;
      }
      let lastLetter = '';
      state.filtered.forEach((target, index) => {
        const letter = firstLetter(target);
        if (letter !== lastLetter) {
          const header = document.createElement('div');
          header.className = 'alpha-header';
          header.textContent = letter;
          listEl.appendChild(header);
          lastLetter = letter;
        }
        const button = document.createElement('button');
        button.className = `item ${index === state.selectedIndex ? 'active' : ''}`;
        button.innerHTML = `
          <span class="item-title">
            <span>${escapeHtml(target.name || target.asset_id)}</span>
            <span class="pill ${target.orientation_review ? 'ok' : 'warn'}">${target.orientation_review ? 'reviewed' : 'unreviewed'}</span>
          </span>
          <span class="item-meta">${escapeHtml(target.asset_id)}</span>
          <span class="item-meta">style: ${escapeHtml(target.style_key || '')}</span>
          <span class="item-meta">front axis: ${escapeHtml(target.front_axis || '-z')} | offset: ${Number(target.rotation_deg_offset || 0)}deg</span>
        `;
        button.addEventListener('click', () => selectTarget(index));
        listEl.appendChild(button);
      });
    }

    function renderTargetSelect() {
      targetSelectEl.innerHTML = '';
      if (state.targets.length === 0) {
        targetSelectEl.appendChild(new Option('No GLB objects found', ''));
        targetSelectEl.disabled = true;
        return;
      }
      targetSelectEl.disabled = false;
      let currentGroup = null;
      let currentLetter = '';
      state.targets.forEach((target) => {
        const letter = firstLetter(target);
        if (letter !== currentLetter) {
          currentGroup = document.createElement('optgroup');
          currentGroup.label = letter;
          targetSelectEl.appendChild(currentGroup);
          currentLetter = letter;
        }
        const option = new Option(targetLabel(target), targetKey(target));
        currentGroup.appendChild(option);
      });
    }

    async function selectTarget(index) {
      if (index < 0 || index >= state.filtered.length) return;
      state.selectedIndex = index;
      state.selected = state.filtered[index];
      state.draftOffset = normalizeOffset(Number(state.selected.rotation_deg_offset || 0));
      titleEl.textContent = state.selected.asset_id;
      subtitleEl.textContent = `${state.selected.name || ''} | ${state.selected.style_key}`;
      notesEl.value = state.selected.orientation_review?.notes || state.selected.preview_override?.notes || '';
      const contexts = state.selected.preview_override?.contexts || [];
      applyAllEl.checked = contexts.includes('all');
      targetSelectEl.value = targetKey(state.selected);
      renderMetadata();
      renderList();
      updateOffsetButtons();
      await loadModel();
    }

    async function selectTargetByKey(key) {
      const target = state.targets.find((candidate) => targetKey(candidate) === key);
      if (!target) return;
      searchEl.value = '';
      state.filtered = state.targets;
      state.selectedIndex = state.filtered.indexOf(target);
      await selectTarget(state.selectedIndex);
      setListStatus(`Showing all ${state.targets.length} GLB variant(s).`, 'ok');
    }

    function clearSelection() {
      state.selectedIndex = -1;
      state.selected = null;
      targetSelectEl.value = '';
      titleEl.textContent = 'No model selected';
      subtitleEl.textContent = 'Choose an object from the alphabetic list.';
      metadataEl.innerHTML = '';
      notesEl.value = '';
      applyAllEl.checked = false;
      clearModel();
      renderList();
    }

    function renderMetadata() {
      const target = state.selected;
      if (!target) {
        metadataEl.innerHTML = '';
        return;
      }
      const dimensions = target.dimensions || {};
      const calibration = target.preview_calibration || {};
      metadataEl.innerHTML = `
        <span>Asset</span><strong>${escapeHtml(target.asset_id)}</strong>
        <span>Style</span><strong>${escapeHtml(target.style_key)}</strong>
        <span>Category</span><strong>${escapeHtml(target.category || 'n/a')}</strong>
        <span>Size</span><strong>${formatDims(dimensions)}</strong>
        <span>Base yaw</span><strong>${Number(target.base_rotation_deg || 0)}deg</strong>
        <span>Draft offset</span><strong id="draft-offset">${state.draftOffset}deg</strong>
        <span>Front axis</span><strong id="front-axis">${offsetToAxis(state.draftOffset)}</strong>
        <span>Calibration</span><strong>${escapeHtml(calibration.status || 'none')} ${calibration.confidence ? `(${calibration.confidence})` : ''}</strong>
      `;
    }

    async function loadModel() {
      clearModel();
      const target = state.selected;
      if (!target) return;
      if (!viewerReady || !world) {
        setStatus('Object selected. The 3D viewer is not ready in this browser session.', 'error');
        return;
      }
      if (!target.file_exists) {
        setStatus(`Missing GLB file: ${target.local_path}`, 'error');
        return;
      }
      setStatus('Loading model...', '');
      try {
        const gltf = await loader.loadAsync(target.model_url);
        const sceneSource = gltf.scene || (gltf.scenes && gltf.scenes[0]);
        if (!sceneSource) {
          throw new Error('GLB has no scene.');
        }

        const visualRoot = new THREE.Group();
        const calibrationRoot = new THREE.Group();
        const model = sceneSource.clone(true);
        model.rotation.y = THREE.MathUtils.degToRad(
          Number(target.base_rotation_deg || 0) + state.draftOffset
        );
        calibrationRoot.add(model);
        visualRoot.add(calibrationRoot);
        applyCalibrationMatrix(calibrationRoot, target.preview_calibration);
        normalizeModelToViewer(visualRoot);
        visualRoot.traverse((node) => {
          if (node.isMesh) {
            node.castShadow = true;
            node.receiveShadow = true;
          }
        });
        state.modelRoot = visualRoot;
        world.add(visualRoot);
        setStatus('Model loaded. Align the real front to the white arrow, then save.', 'ok');
      } catch (error) {
        setStatus(error instanceof Error ? error.message : String(error), 'error');
      }
    }

    function clearModel() {
      if (!state.modelRoot) return;
      world?.remove(state.modelRoot);
      state.modelRoot.traverse((node) => {
        if (node.geometry) node.geometry.dispose?.();
        const materials = Array.isArray(node.material) ? node.material : [node.material];
        materials.forEach((material) => material?.dispose?.());
      });
      state.modelRoot = null;
    }

    function applyCalibrationMatrix(root, calibration) {
      if (!calibration || calibration.status !== 'calibrated' || !Array.isArray(calibration.rotationMatrix || calibration.rotation_matrix)) {
        return;
      }
      const matrixRows = calibration.rotationMatrix || calibration.rotation_matrix;
      if (matrixRows.length !== 4) return;
      const m = new THREE.Matrix4();
      m.set(
        matrixRows[0][0], matrixRows[0][1], matrixRows[0][2], matrixRows[0][3],
        matrixRows[1][0], matrixRows[1][1], matrixRows[1][2], matrixRows[1][3],
        matrixRows[2][0], matrixRows[2][1], matrixRows[2][2], matrixRows[2][3],
        matrixRows[3][0], matrixRows[3][1], matrixRows[3][2], matrixRows[3][3]
      );
      root.applyMatrix4(m);
    }

    function normalizeModelToViewer(root) {
      root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root);
      const size = box.getSize(new THREE.Vector3());
      const maxHorizontal = Math.max(size.x, size.z, 0.001);
      const maxDim = Math.max(size.x, size.y, size.z, 0.001);
      const scale = Math.min(1.85 / maxHorizontal, 1.65 / maxDim);
      root.scale.setScalar(scale);
      root.updateMatrixWorld(true);
      const fittedBox = new THREE.Box3().setFromObject(root);
      const center = fittedBox.getCenter(new THREE.Vector3());
      root.position.x -= center.x;
      root.position.z -= center.z;
      root.position.y -= fittedBox.min.y;
      root.updateMatrixWorld(true);
    }

    function setDraftOffset(offset) {
      state.draftOffset = normalizeOffset(offset);
      updateOffsetButtons();
      renderMetadata();
      loadModel();
    }

    function updateOffsetButtons() {
      document.querySelectorAll('[data-offset]').forEach((button) => {
        button.classList.toggle('active', Number(button.dataset.offset) === state.draftOffset);
      });
    }

    async function saveOrientation() {
      if (!state.selected) return;
      saveEl.disabled = true;
      setStatus('Saving orientation to DB...', '');
      try {
        const response = await fetch('/api/orientation', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            asset_id: state.selected.asset_id,
            style_key: state.selected.style_key,
            rotation_deg_offset: state.draftOffset,
            contexts: applyAllEl.checked ? ['all'] : ['panel'],
            notes: notesEl.value.trim() || null,
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || 'Failed to save orientation.');
        }
        state.selected.rotation_deg_offset = payload.rotation_deg_offset;
        state.selected.front_axis = payload.front_axis;
        state.selected.orientation_review = {
          status: 'reviewed',
          front_axis: payload.front_axis,
          rotation_deg_offset: payload.rotation_deg_offset,
          contexts: payload.contexts,
          notes: notesEl.value.trim() || null,
        };
        state.selected.preview_override = {
          ...(state.selected.preview_override || {}),
          enabled: true,
          contexts: payload.contexts,
          rotation_deg_offset: payload.rotation_deg_offset,
          notes: notesEl.value.trim() || 'Manual GLB orientation review.',
        };
        renderTargetSelect();
        renderList();
        renderMetadata();
        setStatus('Saved. This variant is now marked as manually reviewed.', 'ok');
      } catch (error) {
        setStatus(error instanceof Error ? error.message : String(error), 'error');
      } finally {
        saveEl.disabled = false;
      }
    }

    function filterTargets() {
      const query = searchEl.value.trim().toLowerCase();
      state.filtered = sortTargets(state.targets.filter((target) => {
        const haystack = [
          target.asset_id,
          target.name,
          target.display_label,
          target.style_key,
          target.category,
          target.material,
          target.brand,
        ].join(' ').toLowerCase();
        return haystack.includes(query);
      }));
      if (state.filtered.length === 0) {
        clearSelection();
        setListStatus(`No matches for "${searchEl.value.trim()}".`, 'error');
        return;
      }
      if (!state.filtered.includes(state.selected)) {
        selectTarget(0);
      } else {
        state.selectedIndex = state.filtered.indexOf(state.selected);
        renderList();
      }
      setListStatus(
        query
          ? `Showing ${state.filtered.length} of ${state.targets.length} GLB variant(s).`
          : `Showing all ${state.targets.length} GLB variant(s).`,
        'ok'
      );
    }

    function setStatus(text, tone) {
      statusEl.textContent = text;
      statusEl.className = `status ${tone || ''}`;
    }

    function setListStatus(text, tone) {
      listStatusEl.textContent = text;
      listStatusEl.className = `list-status ${tone || ''}`;
    }

    function targetLabel(target) {
      return target.display_label || `${target.name || target.asset_id} - ${target.style_key}`;
    }

    function targetKey(target) {
      return `${target.asset_id}::${target.style_key}`;
    }

    function firstLetter(target) {
      const label = targetLabel(target).trim();
      return (label[0] || '#').toUpperCase();
    }

    function sortTargets(targets) {
      return [...targets].sort((left, right) => {
        const labelCompare = targetLabel(left).localeCompare(targetLabel(right), undefined, {
          sensitivity: 'base',
          numeric: true,
        });
        if (labelCompare !== 0) return labelCompare;
        const styleCompare = String(left.style_key || '').localeCompare(String(right.style_key || ''), undefined, {
          sensitivity: 'base',
          numeric: true,
        });
        if (styleCompare !== 0) return styleCompare;
        return String(left.asset_id || '').localeCompare(String(right.asset_id || ''), undefined, {
          sensitivity: 'base',
          numeric: true,
        });
      });
    }

    function normalizeOffset(value) {
      return (((Math.round(value / 90) * 90) % 360) + 360) % 360;
    }

    function offsetToAxis(offset) {
      switch (normalizeOffset(offset)) {
        case 90: return '+x';
        case 180: return '+z';
        case 270: return '-x';
        default: return '-z';
      }
    }

    function formatDims(dimensions) {
      if (!dimensions) return 'n/a';
      const w = dimensions.width_mm || '?';
      const d = dimensions.depth_mm || '?';
      const h = dimensions.height_mm || '?';
      return `${w}w x ${d}d x ${h}h mm`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));
    }

    document.querySelectorAll('[data-offset]').forEach((button) => {
      button.addEventListener('click', () => setDraftOffset(Number(button.dataset.offset)));
    });
    document.getElementById('rotate-left').addEventListener('click', () => setDraftOffset(state.draftOffset - 90));
    document.getElementById('rotate-right').addEventListener('click', () => setDraftOffset(state.draftOffset + 90));
    document.getElementById('reset-camera').addEventListener('click', resetCamera);
    saveEl.addEventListener('click', saveOrientation);
    searchEl.addEventListener('input', filterTargets);
    clearSearchEl.addEventListener('click', () => {
      searchEl.value = '';
      filterTargets();
    });
    targetSelectEl.addEventListener('change', () => {
      selectTargetByKey(targetSelectEl.value);
    });
    window.addEventListener('keydown', (event) => {
      if (event.target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
      if (event.key.toLowerCase() === 'q') setDraftOffset(state.draftOffset - 90);
      if (event.key.toLowerCase() === 'e') setDraftOffset(state.draftOffset + 90);
      if (event.key === '[') selectTarget(Math.max(0, state.selectedIndex - 1));
      if (event.key === ']') selectTarget(Math.min(state.filtered.length - 1, state.selectedIndex + 1));
      if (event.key.toLowerCase() === 's') saveOrientation();
    });

    loadTargets().catch((error) => {
      setStatus(error instanceof Error ? error.message : String(error), 'error');
      setListStatus(error instanceof Error ? error.message : String(error), 'error');
    });
  </script>
</body>
</html>
"""


def build_request_handler(
    *,
    inspector: InventoryGlbOrientationInspector,
    vendor_dir: Path,
) -> type[OrientationInspectorRequestHandler]:
    class BoundOrientationInspectorRequestHandler(OrientationInspectorRequestHandler):
        pass

    BoundOrientationInspectorRequestHandler.inspector = inspector
    BoundOrientationInspectorRequestHandler.vendor_dir = vendor_dir
    return BoundOrientationInspectorRequestHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start a local browser-based tool for manually reviewing inventory GLB orientation."
        )
    )
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--asset-ids", nargs="*", default=None)
    parser.add_argument("--style-keys", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--models-public-dir",
        type=Path,
        default=DEFAULT_MODELS_PUBLIC_DIR,
        help="Directory that stores downloaded inventory GLB files.",
    )
    parser.add_argument(
        "--models-url-prefix",
        default=DEFAULT_MODELS_URL_PREFIX,
        help="Public URL prefix stored in inventory model metadata.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    models_public_dir = (ROOT_DIR / args.models_public_dir).resolve()
    vendor_dir = (ROOT_DIR / "frontend/src/vendor/three").resolve()
    inspector = InventoryGlbOrientationInspector(
        tenant_id=str(args.tenant_id),
        models_public_dir=models_public_dir,
        models_url_prefix=str(args.models_url_prefix),
        asset_ids=args.asset_ids,
        style_keys=args.style_keys,
        limit=args.limit,
    )
    handler = build_request_handler(inspector=inspector, vendor_dir=vendor_dir)
    server = ThreadingHTTPServer((str(args.host), int(args.port)), handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Inventory GLB orientation inspector running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping inspector.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
