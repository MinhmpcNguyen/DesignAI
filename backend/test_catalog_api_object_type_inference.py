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

    def test_infers_living_room_vietnamese_names(self) -> None:
        self.assertEqual(
            infer_catalog_object_type(name_vn="Ghế sofa đơn Rustic 1"),
            "armchair",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Ghế sofa forest"),
            "sofa",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bàn"),
            "coffee_table",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bàn trà forest"),
            "coffee_table",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bàn ăn forest"),
            "dining_table",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bàn đôn Rustic 1"),
            "side_table",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Thảm phòng khách forest"),
            "rug",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Tranh forest 1"),
            "wall_art",
        )

    def test_catalog_items_infer_living_decor_from_placement(self) -> None:
        floor_lamp = CatalogItem.model_validate(
            {
                "id": "lamp-1",
                "slug": "forest-khach-mod142fl01b",
                "name": "đèn forest",
                "nameVn": "đèn forest",
                "modelUrl": "/catalog/models/floor-lamp.glb",
                "placementType": "floor",
            }
        )
        ceiling_light = CatalogItem.model_validate(
            {
                "id": "ceiling-1",
                "slug": "forest-khach-group2132577650",
                "name": "đèn trần forest 10",
                "nameVn": "đèn trần forest 10",
                "modelUrl": "/catalog/models/ceiling-light.glb",
                "placementType": "ceiling",
            }
        )
        plant = CatalogItem.model_validate(
            {
                "id": "plant-1",
                "slug": "forest-khach-group2132577681",
                "name": "Chậu hoa nhỏ forest 3",
                "nameVn": "Chậu hoa nhỏ forest 3",
                "modelUrl": "/catalog/models/plant.glb",
                "placementType": "floor",
            }
        )

        self.assertEqual(floor_lamp.inventory_type(category_slug=None), "floor_lamp")
        self.assertEqual(
            ceiling_light.inventory_type(category_slug=None), "ceiling_light"
        )
        self.assertEqual(plant.inventory_type(category_slug=None), "plant")

    def test_infers_kitchen_vietnamese_names_before_generic_table(self) -> None:
        self.assertEqual(
            infer_catalog_object_type(name_vn="Tủ bếp forest 12"),
            "kitchen_base_cabinet",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bàn bếp forest 1"),
            "kitchen_base_cabinet",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Tủ lạnh 2 cửa Rustic"),
            "fridge",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bồn rửa bát forest"),
            "sink",
        )
        self.assertEqual(
            infer_catalog_object_type(name_vn="Bồn rửa chén Rustic"),
            "sink",
        )

    def test_catalog_items_match_vietnamese_living_and_kitchen_types(self) -> None:
        coffee_table = CatalogItem.model_validate(
            {
                "id": "coffee-table-1",
                "slug": "forest-khach-table",
                "name": "Forest table",
                "nameVn": "Bàn",
                "modelUrl": "/catalog/models/coffee-table.glb",
            }
        )
        kitchen_counter = CatalogItem.model_validate(
            {
                "id": "kitchen-counter-1",
                "slug": "forest-khach-box2131645502",
                "name": "Forest kitchen counter",
                "nameVn": "Bàn bếp forest 1",
                "modelUrl": "/catalog/models/kitchen-counter.glb",
            }
        )
        sink = CatalogItem.model_validate(
            {
                "id": "sink-1",
                "slug": "forest-khach-sink",
                "name": "Forest sink",
                "nameVn": "Bồn rửa bát forest",
                "modelUrl": "/catalog/models/sink.glb",
            }
        )

        self.assertTrue(
            coffee_table.matches_types({"coffee_table"}, category_slug="living-room")
        )
        self.assertFalse(
            coffee_table.matches_types(
                {"kitchen_base_cabinet"}, category_slug="living-room"
            )
        )
        self.assertTrue(
            kitchen_counter.matches_types(
                {"kitchen_base_cabinet"}, category_slug="kitchen"
            )
        )
        self.assertTrue(sink.matches_types({"sink"}, category_slug="kitchen"))

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
