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

    def test_tv_console_generates_surface_child_tv(self) -> None:
        payload = build_deterministic_stylist_payload(
            {
                "room": {
                    "room_type": "bedroom",
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


if __name__ == "__main__":
    _ = unittest.main()
