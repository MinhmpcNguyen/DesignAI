from __future__ import annotations

import unittest
from typing import cast

from agent.request_contract import build_request_contract
from stylist.deterministic_layout import build_deterministic_stylist_payload


class MediaTvConsoleContractTest(unittest.TestCase):
    def test_bare_tv_request_targets_console_contract(self) -> None:
        contract = build_request_contract(
            brief_text="Phong ngu co mot ke tv va 1 tv doi dien giuong.",
            available_object_types=["tv_console"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertEqual(object_types, ["tv_console"])

    def test_vietnamese_wardrobe_request_is_protected(self) -> None:
        contract = build_request_contract(
            brief_text="Phong ngu co mot tu quan ao tren mot buc tuong kin.",
            available_object_types=["wardrobe"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertEqual(object_types, ["wardrobe"])

    def test_living_sofa_does_not_create_generic_chair_contract(self) -> None:
        contract = build_request_contract(
            brief_text="Phong khach gom ghe sofa, ban, ke TV va TV.",
            available_object_types=["sofa", "coffee_table", "tv_console"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertIn("sofa", object_types)
        self.assertNotIn("chair", object_types)

    def test_vietnamese_living_support_items_are_detected(self) -> None:
        contract = build_request_contract(
            brief_text=("Phong khach co ghe thu gian, ban don, den cay va tham."),
            available_object_types=["armchair", "side_table", "floor_lamp", "rug"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertEqual(
            object_types,
            ["armchair", "floor_lamp", "rug", "side_table"],
        )

    def test_one_or_two_sofas_keeps_one_primary_sofa_contract(self) -> None:
        contract = build_request_contract(
            brief_text=(
                "Do bat buoc: 1 hoac 2 sofa (sofa), trong do co it nhat mot "
                "sofa lon lam sofa chinh."
            ),
            available_object_types=["sofa"],
        )

        objects = cast(list[dict[str, object]], contract["objects"])
        sofa = next(item for item in objects if item.get("object_type") == "sofa")

        self.assertEqual(sofa.get("target_count"), 1)
        self.assertEqual(sofa.get("min_keep"), 1)

    def test_sofa_seat_capacity_does_not_increase_sofa_count(self) -> None:
        contract = build_request_contract(
            brief_text="Do bat buoc: mot sofa lon 2 3 cho lam sofa chinh (sofa).",
            available_object_types=["sofa"],
        )

        objects = cast(list[dict[str, object]], contract["objects"])
        sofa = next(item for item in objects if item.get("object_type") == "sofa")

        self.assertEqual(sofa.get("target_count"), 1)
        self.assertEqual(sofa.get("min_keep"), 1)

    def test_try_to_add_living_accessories_is_soft_contract(self) -> None:
        contract = build_request_contract(
            brief_text=(
                "Can co gang co them ghe thu gian (armchair), ban phu "
                "(side_table), den cay (floor_lamp) va tham (rug)."
            ),
            available_object_types=["armchair", "side_table", "floor_lamp", "rug"],
        )

        objects = cast(list[dict[str, object]], contract["objects"])

        self.assertTrue(objects)
        self.assertEqual({item.get("min_keep") for item in objects}, {0})

    def test_kitchen_table_phrase_does_not_create_desk_contract(self) -> None:
        contract = build_request_contract(
            brief_text="Khong dat do bep nhu tu bep, ban bep trong phong khach.",
            available_object_types=["desk"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertNotIn("desk", object_types)

    def test_coffee_table_annotation_does_not_create_desk_contract(self) -> None:
        contract = build_request_contract(
            brief_text="Them ban (coffee_table) vao trung tam phong.",
            available_object_types=["desk", "coffee_table"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertEqual(object_types, ["coffee_table"])

    def test_tv_console_generates_surface_child_tv(self) -> None:
        payload = build_deterministic_stylist_payload(
            {
                "room": {
                    "room_type": "room",
                    "polygon_ccw": [
                        {"x": 0, "y": 0},
                        {"x": 4200, "y": 0},
                        {"x": 4200, "y": 3200},
                        {"x": 0, "y": 3200},
                    ],
                },
                "objects": [
                    {
                        "instance_id": "tv_console",
                        "object_type": "tv_console",
                        "cluster_id": "media_optional",
                        "bbox": {
                            "min_x": 1000,
                            "min_y": 200,
                            "max_x": 2600,
                            "max_y": 600,
                        },
                    }
                ],
            }
        )
        objects = cast(list[dict[str, object]], payload["objects"])
        tv = next(item for item in objects if item.get("object_type") == "tv")

        self.assertEqual(tv.get("source"), "inventory")
        self.assertEqual(tv.get("collision_layer"), "surface_child")
        self.assertEqual(
            tv.get("place_on"),
            {"target_instance_id": "tv_console", "method": "on_top"},
        )

    def test_tv_stand_alias_generates_surface_child_tv(self) -> None:
        payload = build_deterministic_stylist_payload(
            {
                "room": {
                    "room_type": "room",
                    "polygon_ccw": [
                        {"x": 0, "y": 0},
                        {"x": 4200, "y": 0},
                        {"x": 4200, "y": 3200},
                        {"x": 0, "y": 3200},
                    ],
                },
                "objects": [
                    {
                        "instance_id": "tv_stand",
                        "object_type": "tv_stand",
                        "cluster_id": "media_optional",
                        "bbox": {
                            "min_x": 1000,
                            "min_y": 200,
                            "max_x": 2600,
                            "max_y": 600,
                        },
                    }
                ],
            }
        )
        objects = cast(list[dict[str, object]], payload["objects"])
        tv = next(item for item in objects if item.get("object_type") == "tv")

        self.assertEqual(tv.get("collision_layer"), "surface_child")
        self.assertEqual(
            tv.get("place_on"),
            {"target_instance_id": "tv_stand", "method": "on_top"},
        )


if __name__ == "__main__":
    _ = unittest.main()
