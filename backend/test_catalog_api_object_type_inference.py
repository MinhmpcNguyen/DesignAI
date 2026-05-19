from __future__ import annotations

import unittest
from typing import cast

from adapters.catalog_api import CatalogItem, infer_catalog_object_type


class CatalogApiObjectTypeInferenceTest(unittest.TestCase):
    def test_infers_tv_from_catalog_names(self) -> None:
        self.assertEqual(
            infer_catalog_object_type(name="TV Rustic 1"),
            "tv",
        )
        self.assertEqual(
            infer_catalog_object_type(name="Tivi Rustic 1"),
            "tv",
        )

    def test_infers_tv_console_before_generic_tv(self) -> None:
        self.assertEqual(
            infer_catalog_object_type(name="Kệ TV Rustic 1"),
            "tv_console",
        )
        self.assertEqual(
            infer_catalog_object_type(name="Kệ tivi gỗ"),
            "tv_console",
        )
        self.assertEqual(
            infer_catalog_object_type(slug="modern-tv-cabinet-oak"),
            "tv_console",
        )

    def test_catalog_items_match_requested_media_types(self) -> None:
        tv = CatalogItem.model_validate(
            {
                "id": "tv-1",
                "slug": "rustic-khach-plane002",
                "name": "TV Rustic 1",
                "modelUrl": "/catalog/models/tv.glb",
            }
        )
        tv_console = CatalogItem.model_validate(
            {
                "id": "console-1",
                "slug": "rustic-khach-group2132576442",
                "name": "Kệ TV Rustic 1",
                "modelUrl": "/catalog/models/tv-console.glb",
            }
        )

        self.assertTrue(tv.matches_types({"tv"}, category_slug="living-room"))
        self.assertTrue(
            tv_console.matches_types({"tv_console"}, category_slug="storage")
        )
        self.assertFalse(tv_console.matches_types({"tv"}, category_slug="storage"))

    def test_tv_dimensions_use_thin_depth_and_vertical_screen_axis(self) -> None:
        tv = CatalogItem.model_validate(
            {
                "id": "tv-1",
                "slug": "rustic-khach-plane002",
                "name": "TV Rustic 1",
                "modelUrl": "/catalog/models/tv.glb",
                "size": [1.2, 0.02, 0.75],
            }
        )

        self.assertEqual(
            tv.dimensions_mm(),
            {"length_mm": 1200.0, "width_mm": 20.0, "height_mm": 750.0},
        )

    def test_tv_inventory_payload_gets_upright_default_rotation(self) -> None:
        tv = CatalogItem.model_validate(
            {
                "id": "tv-1",
                "slug": "rustic-khach-plane002",
                "name": "TV Rustic 1",
                "modelUrl": "/catalog/models/tv.glb",
                "size": [1.2, 0.02, 0.75],
            }
        )

        payload = tv.to_inventory_payload(category_slug="media", asset_base_url="")

        attributes = cast(dict[str, object], payload["attributes"])
        self.assertIsInstance(attributes, dict)
        self.assertEqual(
            attributes.get("defaultRotation"),
            [-0.707106781187, 0.0, 0.0, 0.707106781187],
        )
