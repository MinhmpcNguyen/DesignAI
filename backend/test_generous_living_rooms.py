# pyright: reportPrivateUsage=false
# Integration tests: generous-mode pipeline for all unique living/combined rooms.
# Requires the backend server running at http://localhost:8000.
# Run: python -m pytest backend/test_generous_living_rooms.py -v
from __future__ import annotations

import json
import time
import unittest
import urllib.error
import urllib.request
from typing import Any

_BASE_URL = "http://localhost:8000/pipeline/normalize-run"
_SERVER_REACHABLE: bool | None = None
_POLL_INTERVAL_S = 3
_POLL_TIMEOUT_S = 300


def _check_server() -> bool:
    global _SERVER_REACHABLE
    if _SERVER_REACHABLE is None:
        try:
            req = urllib.request.Request(_BASE_URL, method="POST",
                                         data=b"{}",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2)
        except urllib.error.HTTPError:
            _SERVER_REACHABLE = True
        except Exception:
            _SERVER_REACHABLE = False
    return bool(_SERVER_REACHABLE)


def _get(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
    except Exception:
        return None


def _post_pipeline(payload: dict[str, Any]) -> dict[str, Any] | None:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        _BASE_URL, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            job = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
    except Exception:
        return None

    job_id = job.get("id")
    if not job_id:
        return job

    print(f"\n  [job {job_id}] queued", flush=True)
    deadline = time.monotonic() + _POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        status = _get(f"{_BASE_URL}/{job_id}/status")
        if status is None:
            return None
        state = str(status.get("status") or "").lower()
        print(f"  [job {job_id}] {state}", flush=True)
        if state == "ready":
            return _get(f"{_BASE_URL}/{job_id}/result")
        if state == "error":
            return status
        time.sleep(_POLL_INTERVAL_S)

    return {"status": "timeout", "job_id": job_id}


def _extract_placed_types(resp: dict[str, Any]) -> list[str]:
    types: list[str] = []
    for layout in resp.get("layouts") or []:
        for obj in layout.get("objects") or []:
            t = obj.get("object_type") or obj.get("category") or obj.get("type")
            if t:
                types.append(str(t))
    for obj in resp.get("objects") or []:
        t = obj.get("object_type") or obj.get("category") or obj.get("type")
        if t:
            types.append(str(t))
    return types


@unittest.skipUnless(_check_server(), "Backend server not reachable at localhost:8000")
class GenerousLivingRoomPipelineTest(unittest.TestCase):
    """
    Generous-mode pipeline tests for all 8 unique living/combined rooms.
    Each test POSTs a full user description (generous furnishing trigger) with
    the exact room polygon + walls from the apartment templates.
    Expected: pipeline returns OK/READY and places the named anchor objects.
    """

    def test_living_1_35m2(self) -> None:
        """Room: Room (Phòng khách forest), area=35.61m²"""
        payload = {
            "room": {
                "key": "-1:-0.5",
                "name": "Room",
                "polygons": [[-3.387992130007063, 3.2159432609943095], [-3.312008419677991, -4.808072478991597], [0.5, -4.800000000000001], [0.5, -1.2000000000000002], [3.9000000000000004, -1.2000000000000002], [3.9000000000000004, 0.2], [0.5, 0.2], [0.5, 3.2]],
            },
            "walls": [{"id": "wall-1778648174878-sojibob24", "startPoint": [-3.387992130007063, 3.2159432609943095], "endPoint": [-3.312008419677991, -4.808072478991597], "thickness": 0.2, "height": 3}, {"id": "wall-1778648224069-8hd32as93", "startPoint": [-3.312008419677991, -4.808072478991597], "endPoint": [0.5, -4.800000000000001], "thickness": 0.2, "height": 3}, {"id": "wall-1778648233308-xu19zp6sg", "startPoint": [0.5, -4.800000000000001], "endPoint": [0.5, -1.2000000000000002], "thickness": 0.2, "height": 3}, {"id": "wall-1778648320988-78ge1ofcu", "startPoint": [0.5, -1.2000000000000002], "endPoint": [3.9000000000000004, -1.2000000000000002], "thickness": 0.2, "height": 3}, {"id": "wall-1778648327294-2s2ixawry", "startPoint": [3.9000000000000004, -1.2000000000000002], "endPoint": [3.9000000000000004, 0.2], "thickness": 0.2, "height": 3}, {"id": "wall-1778648334862-uylikt936", "startPoint": [3.9000000000000004, 0.2], "endPoint": [0.5, 0.2], "thickness": 0.2, "height": 3}, {"id": "wall-1778648340912-l6qsnuhrv", "startPoint": [0.5, 0.2], "endPoint": [0.5, 3.2], "thickness": 0.2, "height": 3}, {"id": "wall-1778648345310-gje6lat5p", "startPoint": [0.5, 3.2], "endPoint": [-3.387992130007063, 3.2159432609943095], "thickness": 0.2, "height": 3}],
            "openings": [],
            "source_unit": "m",
            "description": "Phòng khách đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu kem; kệ TV 1.4m x 0.4m; bàn trà 1.0m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 1.6m x 2.4m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa. Chi phí tối đa 55 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Room (35.61m²), got {assigned}")

    def test_living_2_36m2(self) -> None:
        """Room: Phòng sinh hoạt (Chung cư Thăng Long mẫu căn hộ A4 - 2 phòng ngủ), area=36.4m²"""
        payload = {
            "room": {
                "key": "2.5:0",
                "name": "Phòng sinh hoạt",
                "polygons": [[-1.0019848977526817, -0.7000000000000001], [0.3, -0.7], [0.3, -3.9], [5, -3.9000000000000004], [5, 3.9000000000000004], [1.6, 3.9], [1.6, 1.5], [0.3, 1.5], [-1, 1.5]],
            },
            "walls": [{"id": "a2-outer-01", "startPoint": [-5.1, -3.9], "endPoint": [-3.1, -3.9], "thickness": 0.14, "height": 2.65}, {"id": "a2-outer-02", "startPoint": [-3.1, -3.9], "endPoint": [0.3, -3.9], "thickness": 0.14, "height": 2.65}, {"id": "a2-outer-08", "startPoint": [1.6, 3.9], "endPoint": [-1, 3.9], "thickness": 0.14, "height": 2.65}, {"id": "a2-outer-09", "startPoint": [-1, 3.9], "endPoint": [-3.1, 3.9], "thickness": 0.14, "height": 2.65}, {"id": "a2-outer-10", "startPoint": [-3.1, 3.9], "endPoint": [-5.1, 3.9], "thickness": 0.14, "height": 2.65}, {"id": "a2-outer-11", "startPoint": [-5.1, 3.9], "endPoint": [-5.1, 2], "thickness": 0.14, "height": 2.65}, {"id": "a2-pn2-right", "startPoint": [0.3, -3.9], "endPoint": [0.3, -0.7], "thickness": 0.12, "height": 2.65}, {"id": "a2-master-right-02", "startPoint": [-1, 1.5], "endPoint": [-1, 2], "thickness": 0.12, "height": 2.65}, {"id": "a2-master-wc-top", "startPoint": [-5.1, 2], "endPoint": [-3.1, 2], "thickness": 0.12, "height": 2.65}, {"id": "a2-hall-top", "startPoint": [-3.1, 2], "endPoint": [-1, 2], "thickness": 0.12, "height": 2.65}, {"id": "a2-hall-right", "startPoint": [-1, 2], "endPoint": [-1, 3.9], "thickness": 0.12, "height": 2.65}, {"id": "a2-wc-common-bottom", "startPoint": [-1, 1.5], "endPoint": [0.3, 1.5], "thickness": 0.12, "height": 2.65}, {"id": "a2-living-kitchen-bottom", "startPoint": [0.3, 1.5], "endPoint": [1.6, 1.5], "thickness": 0.12, "height": 2.65}, {"id": "a2-entry-left", "startPoint": [1.6, 1.5], "endPoint": [1.6, 3.9], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778121926077-318jxwyyf", "startPoint": [-1.0019848977526817, 1.5], "endPoint": [-1.0019848977526817, -0.7000000000000001], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778121927744-1d56fyk49", "startPoint": [-1, -0.6984735949286095], "endPoint": [0.3, -0.6984735949286094], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778122197248-of5czrdre", "startPoint": [0.3, -3.9], "endPoint": [5, -3.9000000000000004], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778122217226-32za7v5zr", "startPoint": [5, -3.9000000000000004], "endPoint": [5, 3.9000000000000004], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778122219660-e37g20bzy", "startPoint": [5, 3.9000000000000004], "endPoint": [1.6, 3.9], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137343492-yg7htp6qy", "startPoint": [-5.1, -3.9], "endPoint": [-5.1000000000000005, -1.9000000000000001], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137374718-vzak4wpgl", "startPoint": [-3.1, -3.9], "endPoint": [-3.1, -1.9000000000000001], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137377564-0qzqjv6ht", "startPoint": [-3.1, -1.9000000000000001], "endPoint": [-5.1000000000000005, -1.9000000000000001], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137383347-kljkw4plv", "startPoint": [-5.1000000000000005, -1.9000000000000001], "endPoint": [-5.1, 2], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137485980-l5w4uep6n", "startPoint": [-3.1, -1.9000000000000001], "endPoint": [-3.1, -0.7000000000000001], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778137488228-kz4ceekn5", "startPoint": [-3.1, -0.7000000000000001], "endPoint": [-1.0019848977526817, -0.7000000000000001], "thickness": 0.12, "height": 2.65}],
            "openings": [{"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [3.5595479435386204, 1.05, 3.8400000000000003], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778122219660-e37g20bzy"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-0.20053791231203535, 1.05, 1.52], "rotation": [0, -3.439913283669533e-15, 0, 1], "objectRole": "door", "snappedToWall": "a2-wc-common-bottom"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-0.32557117090245913, 1.05, -0.7599999999999999], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778121927744-1d56fyk49"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-1.0219848977526818, 1.05, 0.05842777001327762], "rotation": [0, -0.707106781186547, 0, 0.707106781186548], "objectRole": "door", "snappedToWall": "wall-1778121926077-318jxwyyf"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-4.077604217011379, 1.05, -1.82], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "a2-logia-bottom"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-2.5915220154384686, 1.05, 2.02], "rotation": [0, 0, 0, 1], "objectRole": "door", "snappedToWall": "a2-hall-top"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-4.444765620569125, 1.05, -1.9200000000000002], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778137377564-0qzqjv6ht"}],
            "source_unit": "m",
            "description": "Phòng khách đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu kem; kệ TV 1.4m x 0.4m; bàn trà 1.0m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 1.6m x 2.4m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa. Chi phí tối đa 55 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng sinh hoạt (36.4m²), got {assigned}")

    def test_living_3_40m2(self) -> None:
        """Room: Phòng sinh hoạt + bếp (Chung cư Thăng Long mẫu căn hộ A4 - 3 phòng ngủ), area=40.41m²"""
        payload = {
            "room": {
                "key": "1:-0.5",
                "name": "Phòng sinh hoạt + bếp",
                "polygons": [[-2.5, -0.8], [-2, -0.8], [-2, -2.2], [0, -2.2], [0, -5], [3.4982215173337563, -5], [3.5, 2.3000000000000003], [1.8, 2.3000000000000003], [1.8, 5], [0.2, 5], [0.2, 2.3000000000000003], [-2.5, 2.3000000000000003]],
            },
            "walls": [{"id": "a4-outer-01", "startPoint": [-5.5, -5], "endPoint": [-3.4, -5], "thickness": 0.14, "height": 2.65}, {"id": "a4-outer-15", "startPoint": [-5.5, -3], "endPoint": [-5.5, -5], "thickness": 0.14, "height": 2.65}, {"id": "a4-logia-right", "startPoint": [-3.401858569618604, -5], "endPoint": [-3.401858569618604, -3], "thickness": 0.12, "height": 2.65}, {"id": "a4-logia-bottom", "startPoint": [-5.5, -3], "endPoint": [-3.4, -3], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140508435-mhss1rhx7", "startPoint": [-5.501842920444005, 5], "endPoint": [-5.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140521173-ikbd9sv3a", "startPoint": [-5.5, 2.3015737599339987], "endPoint": [-5.5, -2.9984262400660016], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140658879-p8wame7lx", "startPoint": [-3.401858569618604, -5], "endPoint": [0, -5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140660563-28y5suju0", "startPoint": [0, -5], "endPoint": [3.4982215173337563, -5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140673181-mhc9yy16d", "startPoint": [0, -5], "endPoint": [0, -2.2], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140678508-ob0hks5z8", "startPoint": [-3.4000000000000004, -2.2], "endPoint": [-3.401858569618604, -3], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140697253-s6xaj4tcm", "startPoint": [0.2, 2.3000000000000003], "endPoint": [0.2, 5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140824119-63o7xf733", "startPoint": [3.5, 5], "endPoint": [3.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778140826200-m9uyv9i27", "startPoint": [3.5, 2.3000000000000003], "endPoint": [3.4982215173337563, -5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141034987-1zuizbw8j", "startPoint": [3.5, 5], "endPoint": [1.8, 5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141037486-r52of0gmu", "startPoint": [1.8, 5], "endPoint": [1.8, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141038937-7ik361xfd", "startPoint": [1.8, 2.3000000000000003], "endPoint": [3.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141083791-jrrde3dnu", "startPoint": [-5.501842920444005, 5], "endPoint": [-3.5, 5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141091372-rq2hlufwy", "startPoint": [-3.5, 5], "endPoint": [-3.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141104184-pgkx5ewmf", "startPoint": [-3.5, 5], "endPoint": [0.2, 5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141165012-mm040kqyt", "startPoint": [0.2, 5], "endPoint": [1.8, 5], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141174177-pdretxp9x", "startPoint": [-3.4000000000000004, -2.2], "endPoint": [-2, -2.2], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141175755-wyqxb89q9", "startPoint": [-2, -2.2], "endPoint": [0, -2.2], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141899780-tbx6pg0ot", "startPoint": [-5.5, 2.3015737599339987], "endPoint": [-3.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141901199-bu95o6li2", "startPoint": [-3.5, 2.3000000000000003], "endPoint": [-2.5, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141903198-y4frthamy", "startPoint": [-2.5, 2.3000000000000003], "endPoint": [0.2, 2.3000000000000003], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141926410-48b568mi1", "startPoint": [-2.5, 2.3000000000000003], "endPoint": [-2.5, -0.8], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141928469-1g0ms75dz", "startPoint": [-2.5, -0.8], "endPoint": [-2, -0.8], "thickness": 0.12, "height": 2.65}, {"id": "wall-1778141930252-1w55s6sli", "startPoint": [-2, -0.8], "endPoint": [-2, -2.2], "thickness": 0.12, "height": 2.65}],
            "openings": [{"name": "C\u1eeda s\u1ed5", "size": [1.027565, 1.611291, 0.042295], "position": [1.8892342489063463, 1.7056455000000001, -5.0488525], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "window", "snappedToWall": "wall-1778140660563-28y5suju0"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.8922413793103434, 1.05, 4.98], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778141165012-mm040kqyt"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.18000000000000002, 1.05, 2.9114224137930917], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778140697253-s6xaj4tcm"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [1.82, 1.05, 2.972844827586169], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778141037486-r52of0gmu"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-2.02, 1.05, -1.498706896551719], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778141930252-1w55s6sli"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-0.5896551724137904, 1.05, -2.22], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778141175755-wyqxb89q9"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-4.827801724137904, 1.05, -3.02], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "a4-logia-bottom"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-4.152272156102462, 1.05, 2.3205132660844683], "rotation": [0, 0.0003934398921468968, 0, 0.9999999226025227], "objectRole": "door", "snappedToWall": "wall-1778141899780-tbx6pg0ot"}],
            "source_unit": "m",
            "description": "Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu xanh navy; kệ TV 1.6m x 0.4m; bàn trà 1.1m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 2.0m x 3.0m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m; 1 bàn ăn 1.2m x 0.8m cùng 4 ghế ăn; tủ bếp rustic đặt sát tường bếp. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường. Chi phí tối đa 65 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table", "dining_table", "kitchen_base_cabinet"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng sinh hoạt + bếp (40.41m²), got {assigned}")

    def test_living_4_40m2(self) -> None:
        """Room: Room (Phòng khách Rustic), area=40.42m²"""
        payload = {
            "room": {
                "key": "3.5:2",
                "name": "Room",
                "polygons": [[5.5, -2.4000000000000004], [5.5, 0.9], [7.300000000000001, 0.9], [7.300000000000001, 2.4000000000000004], [5.5, 2.4000000000000004], [5.5, 6.800000000000001], [1.4000000000000001, 6.800000000000001], [1.4000000000000001, -2.4000000000000004]],
            },
            "walls": [{"id": "wall-1778051987249-tdaj12z7g", "startPoint": [1.4000000000000001, -2.4000000000000004], "endPoint": [5.5, -2.4000000000000004], "thickness": 0.2, "height": 3}, {"id": "wall-1778051996131-lpt3qhtx6", "startPoint": [5.5, -2.4000000000000004], "endPoint": [5.5, 0.9], "thickness": 0.2, "height": 3}, {"id": "wall-1778052021185-5hducbkrj", "startPoint": [5.5, 0.9], "endPoint": [7.300000000000001, 0.9], "thickness": 0.2, "height": 3}, {"id": "wall-1778052026921-yrh3se7zu", "startPoint": [7.300000000000001, 0.9], "endPoint": [7.300000000000001, 2.4000000000000004], "thickness": 0.2, "height": 3}, {"id": "wall-1778052030315-bxpaspqmo", "startPoint": [7.300000000000001, 2.4000000000000004], "endPoint": [5.5, 2.4000000000000004], "thickness": 0.2, "height": 3}, {"id": "wall-1778052076596-5buwu0218", "startPoint": [5.5, 2.4000000000000004], "endPoint": [5.5, 6.800000000000001], "thickness": 0.2, "height": 3}, {"id": "wall-1778052096119-8dosg0yxh", "startPoint": [5.5, 6.800000000000001], "endPoint": [1.4000000000000001, 6.800000000000001], "thickness": 0.2, "height": 3}, {"id": "wall-1778052123234-eeoo4q85j", "startPoint": [1.4000000000000001, 6.800000000000001], "endPoint": [1.4000000000000001, -2.4000000000000004], "thickness": 0.2, "height": 3}],
            "openings": [],
            "source_unit": "m",
            "description": "Phòng khách đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu xanh navy; kệ TV 1.6m x 0.4m; bàn trà 1.1m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 2.0m x 3.0m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa. Chi phí tối đa 65 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Room (40.42m²), got {assigned}")

    def test_living_5_43m2(self) -> None:
        """Room: Phòng khách + Bếp + Không gian chung (Chung cư Golden Land - C8-B), area=43.55m²"""
        payload = {
            "room": {
                "key": "3:-1",
                "name": "Phòng khách + Bếp + Không gian chung",
                "polygons": [[-3.3000000000000003, -0.5], [-2, -0.5], [-2, -1.6], [1.5, -1.6], [1.5, -3.99847230816831], [7.7, -4], [7.7, 0.9], [-2, 0.9], [-2, 2.9000000000000004], [-3.3000000000000003, 2.9000000000000004], [-3.3000000000000003, 0.9]],
            },
            "walls": [{"id": "wall-1778491935385-kp5auuwwj", "startPoint": [-5, -5], "endPoint": [-2, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492112145-ljegt0ihf", "startPoint": [-3.3000000000000003, -0.5], "endPoint": [-2, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492196504-u76jd3xyz", "startPoint": [-2, -5], "endPoint": [1.5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492214502-wd05wxk5u", "startPoint": [1.5, -1.6], "endPoint": [-2, -1.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778492222778-3blehal2o", "startPoint": [-2, -5], "endPoint": [-2, -1.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778492223995-6cj4b5uf9", "startPoint": [-2, -1.6], "endPoint": [-2, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492601810-sz6wghpkc", "startPoint": [1.5, -1.6], "endPoint": [1.5, -3.99847230816831], "thickness": 0.12, "height": 3}, {"id": "wall-1778492603025-363hia7bm", "startPoint": [1.5, -3.99847230816831], "endPoint": [1.5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492795193-tbd6ijemy", "startPoint": [-5, -5], "endPoint": [-5, -1.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778492797528-xyxsudxmp", "startPoint": [-5.001606654806105, -1.6000000000000152], "endPoint": [-3.3016066548061054, -1.6000000000000152], "thickness": 0.12, "height": 3}, {"id": "wall-1778492799861-3j3w56rdj", "startPoint": [-3.3000000000000003, -1.6], "endPoint": [-3.3000000000000003, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492827120-xls1i9w1l", "startPoint": [-5, -1.6], "endPoint": [-5, 0.9], "thickness": 0.12, "height": 3}, {"id": "wall-1778492841051-0qfc1luwf", "startPoint": [-5, 0.9], "endPoint": [-3.3000000000000003, 0.9], "thickness": 0.12, "height": 3}, {"id": "wall-1778492842036-41kfzhdo6", "startPoint": [-3.3000000000000003, 0.9], "endPoint": [-3.3000000000000003, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492868027-2svolol6r", "startPoint": [-5, 0.9], "endPoint": [-5, 2.9000000000000004], "thickness": 0.12, "height": 3}, {"id": "wall-1778492873109-y4ldiegjm", "startPoint": [-5, 2.9000000000000004], "endPoint": [-3.3000000000000003, 2.9000000000000004], "thickness": 0.12, "height": 3}, {"id": "wall-1778492874275-zfk73th9i", "startPoint": [-3.3000000000000003, 2.9000000000000004], "endPoint": [-3.3000000000000003, 0.9], "thickness": 0.12, "height": 3}, {"id": "wall-1778492893670-8zav9n45w", "startPoint": [-3.3000000000000003, 2.9000000000000004], "endPoint": [-2, 2.9000000000000004], "thickness": 0.12, "height": 3}, {"id": "wall-1778492897185-y66pexffa", "startPoint": [-2, 2.9000000000000004], "endPoint": [-2, 0.9], "thickness": 0.12, "height": 3}, {"id": "wall-1778492976986-os17nkdwj", "startPoint": [1.5, -3.99847230816831], "endPoint": [7.7, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778492977935-6ibq7ujaa", "startPoint": [7.7, -4], "endPoint": [7.7, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778492979570-tm3thxjqs", "startPoint": [7.7, -5], "endPoint": [1.5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778493010129-a122nrldx", "startPoint": [7.7, -4], "endPoint": [7.7, 0.9], "thickness": 0.12, "height": 3}, {"id": "wall-1778493012162-14x7dsov6", "startPoint": [7.7, 0.9], "endPoint": [-2, 0.9], "thickness": 0.12, "height": 3}],
            "openings": [{"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-3.3200000000000003, 1.05, 2.35], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778492367631-ppfhwq3t7"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-3.3200000000000003, 1.05, 1.4324296141814439], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778492874275-zfk73th9i"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-3.3200000000000003, 1.05, -0.95], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778492799861-3j3w56rdj"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-2.508237747653807, 1.05, -0.52], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778492112145-ljegt0ihf"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.89155370177268, 1.05, -1.62], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778492214502-wd05wxk5u"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-2.45, 1.05, 2.8800000000000003], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778492893670-8zav9n45w"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [4.6123642085782155, 1.05, -4.019239201255882], "rotation": [0, -0.9999999924107628, 0, 0.00012320095136179087], "objectRole": "door", "snappedToWall": "wall-1778492976986-os17nkdwj"}],
            "source_unit": "m",
            "description": "Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu xanh navy; kệ TV 1.6m x 0.4m; bàn trà 1.1m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 2.0m x 3.0m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m; 1 bàn ăn 1.2m x 0.8m cùng 4 ghế ăn; tủ bếp rustic đặt sát tường bếp. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường. Chi phí tối đa 65 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table", "dining_table", "kitchen_base_cabinet"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng khách + Bếp + Không gian chung (43.55m²), got {assigned}")

    def test_living_6_47m2(self) -> None:
        """Room: Phòng khách, Ăn + Bếp + Không gian chùn (Chung cư Golden Land - C4-B), area=47.44m²"""
        payload = {
            "room": {
                "key": "-5:-0.5",
                "name": "Phòng khách, Ăn + Bếp + Không gian chùn",
                "polygons": [[-8.200000000000001, 2.6], [-8.1, -4], [-5, -4], [-4.1000000000000005, -4], [-1.3, -4], [-1.3021516721141018, -0.4999999999999929], [0.6000000000000001, -0.5], [0.6000000000000001, 0.5], [-4, 0.5], [-4, 5], [-6.5, 5], [-6.5, 2.6]],
            },
            "walls": [{"id": "wall-1778484330026-rp8v4o23b", "startPoint": [5, -5], "endPoint": [1.5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484356427-54772bf83", "startPoint": [1.5, -5], "endPoint": [1.5, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484375830-5h0rrm5di", "startPoint": [0.6000000000000001, 0.5], "endPoint": [0.6000000000000001, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484376811-arm7vbsjv", "startPoint": [0.6000000000000001, -0.5], "endPoint": [1.5, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484507448-7dwr4w3jx", "startPoint": [-4, 5], "endPoint": [-4, 0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484522393-tytpcy7tm", "startPoint": [-4, 0.5], "endPoint": [0.6000000000000001, 0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484628118-sssy2bmg1", "startPoint": [-8.200000000000001, 5], "endPoint": [-6.5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484641944-udjc8zm7w", "startPoint": [-6.5, 5], "endPoint": [-6.5, 2.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778484646661-4d1jud63p", "startPoint": [-6.5, 2.6], "endPoint": [-8.200000000000001, 2.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778484656577-q0o48tih8", "startPoint": [-8.200000000000001, 5], "endPoint": [-8.200000000000001, 2.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778484663506-5kk9w4kpb", "startPoint": [-6.5, 5], "endPoint": [-4, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484688235-mi8yjkzub", "startPoint": [-8.1, -5], "endPoint": [-8.1, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778484700830-duqcvt8bg", "startPoint": [-8.1, -4], "endPoint": [-8.200000000000001, 2.6], "thickness": 0.12, "height": 3}, {"id": "wall-1778484744094-j3460zb0w", "startPoint": [-4.5, -4], "endPoint": [-4.5, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484787326-xbnk7hylc", "startPoint": [-5, -4], "endPoint": [-5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484795840-73itqdkpu", "startPoint": [-4.1000000000000005, -5], "endPoint": [-4.1000000000000005, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778484806937-bltsw27kn", "startPoint": [-8.1, -5], "endPoint": [-5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484807969-ssahmu2jm", "startPoint": [-5, -5], "endPoint": [-4.1000000000000005, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778484817540-iatxp28x0", "startPoint": [-8.1, -4], "endPoint": [-5, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778484820467-mdert68bi", "startPoint": [-5, -4], "endPoint": [-4.1000000000000005, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778485858418-m889qrowd", "startPoint": [0.6000000000000001, 0.5], "endPoint": [2.4000000000000004, 0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778485861050-ghaei1r3r", "startPoint": [2.3981147995430856, 0.4999999999999929], "endPoint": [4.998114799543085, 0.4999999999999929], "thickness": 0.12, "height": 3}, {"id": "wall-1778485905727-54njubdek", "startPoint": [2.3981147995430856, 0.5018297533846477], "endPoint": [2.4000000000000004, -0.7981702466153452], "thickness": 0.12, "height": 3}, {"id": "wall-1778485941444-erbp3f5lr", "startPoint": [2.4000000000000004, -0.7981702466153452], "endPoint": [5, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778485943010-1npbbu3wz", "startPoint": [5, -0.8], "endPoint": [4.998114799543085, 0.4999999999999929], "thickness": 0.12, "height": 3}, {"id": "wall-1778485947825-e7i2wyc2o", "startPoint": [5, -0.8], "endPoint": [5, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778486320303-2h8n4wdq3", "startPoint": [1.5, -5], "endPoint": [-1.3, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778486338765-ulbpxkjyv", "startPoint": [-1.3021516721141018, -0.4999999999999929], "endPoint": [0.6000000000000001, -0.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778486344747-ya751f5bi", "startPoint": [-4.1000000000000005, -5], "endPoint": [-1.3021516721141018, -4.999999999999993], "thickness": 0.12, "height": 3}, {"id": "wall-1778486668671-o0e13nyce", "startPoint": [-4.1000000000000005, -4], "endPoint": [-1.3, -4], "thickness": 0.12, "height": 3}, {"id": "wall-1778486674597-j7f4jsi30", "startPoint": [-1.3, -4], "endPoint": [-1.3, -5], "thickness": 0.12, "height": 3}, {"id": "wall-1778486680653-mpw4w53v7", "startPoint": [-1.3021516721141018, -0.4999999999999929], "endPoint": [-1.3, -4], "thickness": 0.12, "height": 3}],
            "openings": [{"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [1.52, 1.05, -2.45], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778227870817-9mdzp9xgt"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-4.85069525313953, 1.05, 4.98], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778484663506-5kk9w4kpb"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-6.52, 1.05, 3.1639762219341834], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778484641944-udjc8zm7w"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-5.852719304737537, 1.05, -4.02], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778484817540-iatxp28x0"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-1.96232671604281, 1.05, -4.02], "rotation": [0, 1, 0, 7.273661547324616e-16], "objectRole": "door", "snappedToWall": "wall-1778486668671-o0e13nyce"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.6200000000000001, 1.05, 0.04999999999999999], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778484375830-5h0rrm5di"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [2.4193474102677883, 1.05, -0.3481417167242617], "rotation": [0, 0.7065938887816589, 0, 0.7076193018399177], "objectRole": "door", "snappedToWall": "wall-1778485905727-54njubdek"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-0.7082790215163777, 1.05, -0.5199999999999951], "rotation": [0, -1, 0, 1.837589179357618e-15], "objectRole": "door", "snappedToWall": "wall-1778486338765-ulbpxkjyv"}],
            "source_unit": "m",
            "description": "Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu xanh navy; kệ TV 1.6m x 0.4m; bàn trà 1.1m x 0.6m; 1 ghế armchair 0.85m x 0.85m; thảm 2.0m x 3.0m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m; 1 bàn ăn 1.6m x 0.9m cùng 6 ghế ăn; tủ bếp rustic đặt sát tường bếp. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường. Chi phí tối đa 65 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table", "dining_table", "kitchen_base_cabinet"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng khách, Ăn + Bếp + Không gian chùn (47.44m²), got {assigned}")

    def test_living_7_54m2(self) -> None:
        """Room: Phòng khách, Ăn + Bếp + KHông gian chung (Chung cư Golden Land - C1-1-B), area=54.04m²"""
        payload = {
            "room": {
                "key": "-3:2.5",
                "name": "Phòng khách, Ăn + Bếp + KHông gian chung",
                "polygons": [[-8, -0.8], [-6.5, -0.8], [-2.0019108465826676, -0.8], [-2, 1.5], [-0.2, 1.5], [3.5, 1.5], [3.5, 5], [-7.998060083743152, 5]],
            },
            "walls": [{"id": "wall-1778227835144-qzleq1von", "startPoint": [5, 1.5040891341677818], "endPoint": [5, -1.9959108658322182], "thickness": 0.12, "height": 3}, {"id": "wall-1778227836927-4aajp5ity", "startPoint": [5, -2], "endPoint": [5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227866101-er90wajsi", "startPoint": [5, -3.5], "endPoint": [1.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227870817-9mdzp9xgt", "startPoint": [1.5, -3.5], "endPoint": [1.5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227872586-e8u8vx5ic", "startPoint": [1.5, -2], "endPoint": [5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227955188-7rv7nsz7k", "startPoint": [-0.2, -2], "endPoint": [1.5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227983822-asvsledsk", "startPoint": [-8, -3.5], "endPoint": [-6.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227999235-27jsr70ow", "startPoint": [-6.5, -3.5], "endPoint": [-6.5, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228002800-gibf8bxr6", "startPoint": [-6.5, -0.8], "endPoint": [-8, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228010597-kq7sihmjy", "startPoint": [-8, -3.5], "endPoint": [-8, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228012015-ibsrzjvg8", "startPoint": [-7.998060083743152, -0.8], "endPoint": [-7.998060083743152, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228020929-kwx6gka74", "startPoint": [-6.5, -3.5], "endPoint": [1.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228054008-0izcf9doy", "startPoint": [-0.2, -2], "endPoint": [-0.2, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228056410-s53bwgay8", "startPoint": [-0.2, -0.8], "endPoint": [-0.2, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228099545-6c9s00rvd", "startPoint": [-0.2, 1.5], "endPoint": [-2, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228103351-kie618b1y", "startPoint": [-2.0019108465826676, 1.5], "endPoint": [-2.0019108465826676, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228175365-844pnbq7x", "startPoint": [-6.5, -0.8], "endPoint": [-2.0019108465826676, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228179894-29sajo109", "startPoint": [-2.0019108465826676, -0.8], "endPoint": [-0.2, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228484578-i81l5rbf5", "startPoint": [5, 1.5040891341677818], "endPoint": [5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228493694-frqgxgk4g", "startPoint": [5, 5], "endPoint": [3.5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228499657-x8io4hs3d", "startPoint": [3.5, 5], "endPoint": [3.5, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228501873-zj3dery09", "startPoint": [3.5, 1.5], "endPoint": [-0.2, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228508300-6whvez8o1", "startPoint": [3.5, 1.5], "endPoint": [5, 1.5040891341677818], "thickness": 0.12, "height": 3}, {"id": "wall-1778228515161-nwb59k9sl", "startPoint": [-7.998060083743152, 5], "endPoint": [3.5, 5], "thickness": 0.12, "height": 3}],
            "openings": [{"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-7.978060083743152, 1.05, -0.2194464896145466], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778228012015-ibsrzjvg8"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-6.52, 1.05, -1.3177018176780955], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778227999235-27jsr70ow"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-1.55, 1.05, 1.48], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778228099545-6c9s00rvd"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.5080293778571683, 1.05, 1.48], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778228501873-zj3dery09"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [3.52, 1.05, 4.412636171538255], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778228499657-x8io4hs3d"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [1.52, 1.05, -2.45], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778227870817-9mdzp9xgt"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-5.291311159631861, 1.05, -0.8200000000000001], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778228175365-844pnbq7x"}],
            "source_unit": "m",
            "description": "Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 3.0m x 1.8m màu ghi; kệ TV 1.9m x 0.45m; bàn trà 1.3m x 0.7m; 2 ghế armchair 0.85m x 0.85m; thảm 2.5m x 3.5m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m; 1 bàn ăn 1.6m x 0.9m cùng 6 ghế ăn; tủ bếp rustic đặt sát tường bếp. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường. Chi phí tối đa 80 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table", "dining_table", "kitchen_base_cabinet"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng khách, Ăn + Bếp + KHông gian chung (54.04m²), got {assigned}")

    def test_living_8_54m2(self) -> None:
        """Room: Phòng khách, Ăn + Bếp + Không gian chung (Chung cư Golden Land - C7-B), area=54.14m²"""
        payload = {
            "room": {
                "key": "-2.5:2.5",
                "name": "Phòng khách, Ăn + Bếp + Không gian chung",
                "polygons": [[-8, -0.8], [-6.5, -0.8], [-2.0019108465826676, -0.8], [-0.2, -0.8], [-0.2, 1.5], [3.5, 1.5], [3.5, 5], [-6.5, 5], [-6.5, 2.3000000000000003], [-8, 2.3000000000000003]],
            },
            "walls": [{"id": "wall-1778227835144-qzleq1von", "startPoint": [5, 1.5040891341677818], "endPoint": [5, -1.9959108658322182], "thickness": 0.12, "height": 3}, {"id": "wall-1778227836927-4aajp5ity", "startPoint": [5, -2], "endPoint": [5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227866101-er90wajsi", "startPoint": [5, -3.5], "endPoint": [1.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227870817-9mdzp9xgt", "startPoint": [1.5, -3.5], "endPoint": [1.5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227872586-e8u8vx5ic", "startPoint": [1.5, -2], "endPoint": [5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227955188-7rv7nsz7k", "startPoint": [-0.2, -2], "endPoint": [1.5, -2], "thickness": 0.12, "height": 3}, {"id": "wall-1778227983822-asvsledsk", "startPoint": [-8, -3.5], "endPoint": [-6.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778227999235-27jsr70ow", "startPoint": [-6.5, -3.5], "endPoint": [-6.5, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228002800-gibf8bxr6", "startPoint": [-6.5, -0.8], "endPoint": [-8, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228010597-kq7sihmjy", "startPoint": [-8, -3.5], "endPoint": [-8, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228020929-kwx6gka74", "startPoint": [-6.5, -3.5], "endPoint": [1.5, -3.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228054008-0izcf9doy", "startPoint": [-0.2, -2], "endPoint": [-0.2, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228056410-s53bwgay8", "startPoint": [-0.2, -0.8], "endPoint": [-0.2, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228175365-844pnbq7x", "startPoint": [-6.5, -0.8], "endPoint": [-2.0019108465826676, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228179894-29sajo109", "startPoint": [-2.0019108465826676, -0.8], "endPoint": [-0.2, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778228484578-i81l5rbf5", "startPoint": [5, 1.5040891341677818], "endPoint": [5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228493694-frqgxgk4g", "startPoint": [5, 5], "endPoint": [3.5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228499657-x8io4hs3d", "startPoint": [3.5, 5], "endPoint": [3.5, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228501873-zj3dery09", "startPoint": [3.5, 1.5], "endPoint": [-0.2, 1.5], "thickness": 0.12, "height": 3}, {"id": "wall-1778228508300-6whvez8o1", "startPoint": [3.5, 1.5], "endPoint": [5, 1.5040891341677818], "thickness": 0.12, "height": 3}, {"id": "wall-1778568560811-22cz05c98", "startPoint": [3.5, 5], "endPoint": [-6.5, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778568562404-5p5qa8xet", "startPoint": [-6.5, 5], "endPoint": [-8, 5], "thickness": 0.12, "height": 3}, {"id": "wall-1778568595755-ivzz3pakb", "startPoint": [-8, 5], "endPoint": [-8, 2.3000000000000003], "thickness": 0.12, "height": 3}, {"id": "wall-1778568597356-89m7r10o5", "startPoint": [-8, 2.3000000000000003], "endPoint": [-8, -0.8], "thickness": 0.12, "height": 3}, {"id": "wall-1778568612521-uk04gknrx", "startPoint": [-6.5, 5], "endPoint": [-6.5, 2.3000000000000003], "thickness": 0.12, "height": 3}, {"id": "wall-1778568613865-5g9mz9u5c", "startPoint": [-6.5, 2.3000000000000003], "endPoint": [-8, 2.3000000000000003], "thickness": 0.12, "height": 3}],
            "openings": [{"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-7.978060083743152, 1.05, -0.2194464896145466], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778228012015-ibsrzjvg8"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-6.52, 1.05, -1.3177018176780955], "rotation": [0, -0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778227999235-27jsr70ow"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [0.5080293778571683, 1.05, 1.48], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778228501873-zj3dery09"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [3.52, 1.05, 4.412636171538255], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778228499657-x8io4hs3d"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [1.52, 1.05, -2.45], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778227870817-9mdzp9xgt"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-5.291311159631861, 1.05, -0.8200000000000001], "rotation": [0, 1, 0, 6.123233995736766e-17], "objectRole": "door", "snappedToWall": "wall-1778228175365-844pnbq7x"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-7.98, 1.05, 0.07277079612574333], "rotation": [0, 0.7071067811865475, 0, 0.7071067811865476], "objectRole": "door", "snappedToWall": "wall-1778568597356-89m7r10o5"}, {"name": "C\u1eeda (XHome)", "size": [0.9, 2.1, 0.1], "position": [-7.066852868211294, 1.05, 2.3200000000000003], "rotation": [0, 0, 0, 1], "objectRole": "door", "snappedToWall": "wall-1778568613865-5g9mz9u5c"}],
            "source_unit": "m",
            "description": "Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 3.0m x 1.8m màu ghi; kệ TV 1.9m x 0.45m; bàn trà 1.3m x 0.7m; 2 ghế armchair 0.85m x 0.85m; thảm 2.5m x 3.5m; 2 bàn đầu sofa 0.45m x 0.45m; 1 đèn sàn; 1 kệ sách 0.8m x 0.35m; 1 bàn ăn 1.6m x 0.9m cùng 6 ghế ăn; tủ bếp rustic đặt sát tường bếp. Sofa đặt sát tường dài hướng về TV; bàn trà đặt giữa sofa và kệ TV; ghế armchair đặt bên cạnh sofa; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường. Chi phí tối đa 80 triệu.",
            "style": "modern",
        }
        resp = _post_pipeline(payload)
        self.assertIsNotNone(resp, "Pipeline did not return a response")
        if resp is None:
            return
        status = resp.get("status")
        self.assertIn(str(status).upper(), {"OK", "READY", "PARTIAL"},
                      f"Unexpected pipeline status: {status}")
        assigned = _extract_placed_types(resp)
        for t in ["sectional_sofa", "sofa", "tv_console", "coffee_table", "dining_table", "kitchen_base_cabinet"]:
            self.assertIn(t, assigned,
                          f"Expected {t} in layout for Phòng khách, Ăn + Bếp + Không gian chung (54.14m²), got {assigned}")


if __name__ == "__main__":
    _ = unittest.main()
