from __future__ import annotations

from dataclasses import dataclass

from db.models import AssetId, FileKind


@dataclass(frozen=True)
class StorageKeyBuilder:
    image_prefix: str = "furniture_images"
    template_prefix: str = "templates"

    def build_image_key(self, asset_id: AssetId, filename: str) -> str:
        return f"{self.image_prefix}/{asset_id}/{filename}"

    def build_template_key(self, asset_id: AssetId, filename: str) -> str:
        return f"{self.template_prefix}/{asset_id}/{filename}"

    def build_key(self, asset_id: AssetId, file_kind: FileKind, filename: str) -> str:
        if file_kind == "IMAGE":
            return self.build_image_key(asset_id, filename)
        return self.build_template_key(asset_id, filename)
