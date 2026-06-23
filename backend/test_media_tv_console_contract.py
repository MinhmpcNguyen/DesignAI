from __future__ import annotations

import unittest
from typing import cast

from agent.request_contract import (
    attach_request_contract_to_semantic_program,
    build_request_contract,
    sanitize_request_contract,
)
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

        objects = cast(list[dict[str, object]], contract["objects"])
        object_types = [item.get("object_type") for item in objects]

        self.assertIn("sofa", object_types)
        self.assertIn("coffee_table", object_types)
        self.assertNotIn("chair", object_types)
        coffee_table = next(
            item for item in objects if item.get("object_type") == "coffee_table"
        )
        self.assertEqual(coffee_table.get("min_keep"), 1)
        self.assertEqual(
            coffee_table.get("requested_dims_mm"),
            {"L_mm": 900, "W_mm": 550},
        )

    def test_living_generic_table_request_targets_coffee_table(self) -> None:
        contract = build_request_contract(
            brief_text=(
                "Toi can phong khach co day du sofa, ban, tv; "
                "phong bep thi co tu bep, tu lanh, bon rua, ban an va ghe."
            ),
            available_object_types=[
                "sofa",
                "coffee_table",
                "tv_console",
                "kitchen_base_cabinet",
                "fridge",
                "sink",
                "dining_table",
                "chair",
            ],
        )

        objects = cast(list[dict[str, object]], contract["objects"])
        object_types = [item.get("object_type") for item in objects]

        self.assertIn("coffee_table", object_types)
        self.assertIn("dining_table", object_types)
        self.assertNotIn("desk", object_types)
        coffee_table = next(
            item for item in objects if item.get("object_type") == "coffee_table"
        )
        self.assertEqual(
            coffee_table.get("requested_dims_mm"),
            {"L_mm": 900, "W_mm": 550},
        )

    def test_sanitize_merges_missing_hard_living_table_heuristic(self) -> None:
        contract = sanitize_request_contract(
            {
                "objects": [
                    {
                        "object_type": "sofa",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "target_count": 1,
                        "evidence": "phong khach co day du sofa",
                    },
                    {
                        "object_type": "tv_console",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "target_count": 1,
                        "evidence": "tv",
                    },
                ]
            },
            brief_text="Phong khach co day du sofa, ban, tv.",
            available_object_types=["sofa", "coffee_table", "tv_console"],
            fallback_to_heuristic=True,
        )

        objects = cast(list[dict[str, object]], contract["objects"])
        coffee_table = next(
            item for item in objects if item.get("object_type") == "coffee_table"
        )

        self.assertEqual(coffee_table.get("min_keep"), 1)
        self.assertEqual(
            coffee_table.get("requested_dims_mm"),
            {"L_mm": 900, "W_mm": 550},
        )

    def test_attach_contract_injects_missing_living_coffee_table_candidate(
        self,
    ) -> None:
        program = {
            "room_type": "living_room",
            "active_clusters": [
                {
                    "cluster_id": "main_seating",
                    "required_bundles": [
                        {
                            "bundle_id": "main_seating_bundle",
                            "objects": [
                                {
                                    "object_type": "sofa",
                                    "role": "dominant_anchor",
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        updated = attach_request_contract_to_semantic_program(
            program,
            brief_text="Phong khach co sofa, ban va tv.",
        )

        clusters = cast(list[dict[str, object]], updated["active_clusters"])
        bundle = cast(
            dict[str, object],
            cast(list[object], clusters[0]["required_bundles"])[0],
        )
        objects = cast(list[dict[str, object]], bundle["objects"])
        object_types = [row.get("object_type") for row in objects]
        contract_objects = cast(
            list[dict[str, object]],
            cast(dict[str, object], updated["request_contract"])["objects"],
        )
        coffee_table = next(
            row for row in contract_objects if row.get("object_type") == "coffee_table"
        )

        self.assertIn("coffee_table", object_types)
        self.assertTrue(coffee_table.get("available_in_program"))

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

    def test_living_wall_art_typo_and_plant_are_detected(self) -> None:
        contract = build_request_contract(
            brief_text="Trang tri them trang treo tuong va cay canh.",
            available_object_types=["plant", "wall_art"],
        )

        object_types = [
            item.get("object_type")
            for item in cast(list[dict[str, object]], contract["objects"])
        ]

        self.assertEqual(object_types, ["plant", "wall_art"])

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

    def test_living_room_position_phrase_does_not_create_desk_contract(self) -> None:
        # "bàn nằm giữa sofa và TV" is a layout description, not a desk request.
        # The generic "ban" alias should be blocked when sofa/TV context is nearby.
        contract = build_request_contract(
            brief_text=(
                "Bo cuc phai co sofa quay mat truc tiep ve ke tv, "
                "ban nam giua sofa va tv, armchair dat lech canh sofa."
            ),
            available_object_types=["desk", "coffee_table", "sofa"],
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

    def test_tv_console_generates_wall_mounted_tv(self) -> None:
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
        self.assertEqual(tv.get("collision_layer"), "wall_mounted")
        self.assertEqual(
            tv.get("place_on"),
            {"target_instance_id": "wall", "method": "hang_on"},
        )

    def test_tv_stand_alias_generates_wall_mounted_tv(self) -> None:
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

        self.assertEqual(tv.get("collision_layer"), "wall_mounted")
        self.assertEqual(
            tv.get("place_on"),
            {"target_instance_id": "wall", "method": "hang_on"},
        )


if __name__ == "__main__":
    _ = unittest.main()
