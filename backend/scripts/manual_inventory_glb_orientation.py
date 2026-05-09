from __future__ import annotations

import argparse
import html
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(BASE_DIR))

from inspect_inventory_glb_orientation import (
    DEFAULT_HOST,
    DEFAULT_MODELS_PUBLIC_DIR,
    DEFAULT_MODELS_URL_PREFIX,
    InventoryGlbOrientationInspector,
    JsonObject,
    normalize_cardinal_offset,
    normalize_quarter_turn_tilt,
)

DEFAULT_PORT = 8788
OFFSET_LABELS = {
    0: "Front is -Z",
    90: "Front is +X",
    180: "Front is +Z",
    270: "Front is -X",
}


def escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def target_key(target: JsonObject) -> str:
    return f"{target.get('asset_id')}::{target.get('style_key')}"


def first_target(targets: list[JsonObject]) -> tuple[str, str] | None:
    if not targets:
        return None
    first = targets[0]
    asset_id = str(first.get("asset_id") or "")
    style_key = str(first.get("style_key") or "")
    if not asset_id or not style_key:
        return None
    return asset_id, style_key


def find_target(
    *,
    targets: list[JsonObject],
    asset_id: str,
    style_key: str,
) -> JsonObject | None:
    for target in targets:
        if target.get("asset_id") == asset_id and target.get("style_key") == style_key:
            return target
    return None


def selected_offset(target: JsonObject | None, raw_offset: str | None) -> int:
    if raw_offset:
        try:
            return normalize_cardinal_offset(float(raw_offset))
        except ValueError:
            return 0
    if target is None:
        return 0
    raw_value = target.get("rotation_deg_offset")
    try:
        return normalize_cardinal_offset(float(raw_value or 0))
    except ValueError:
        return 0


def selected_tilt(
    target: JsonObject | None,
    raw_tilt: str | None,
    *,
    axis: str,
) -> int:
    if raw_tilt:
        try:
            return normalize_quarter_turn_tilt(float(raw_tilt))
        except ValueError:
            return 0
    if target is None:
        return 0
    raw_value = target.get(f"rotation_deg_{axis}")
    try:
        return normalize_quarter_turn_tilt(float(raw_value or 0))
    except ValueError:
        return 0


def adjusted_tilt(value: int, delta: int) -> int:
    return normalize_quarter_turn_tilt(float(value + delta))


class ManualInventoryGlbReviewHandler(BaseHTTPRequestHandler):
    inspector: InventoryGlbOrientationInspector
    vendor_dir: Path

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in ("", "/"):
                self._send_html(self._build_index(parsed.query))
                return
            if parsed.path == "/viewer":
                self._send_html(self._build_viewer(parsed.query))
                return
            if parsed.path == "/model":
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
            self._send_plain("Not found.", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_plain(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path not in ("/save", "/delete"):
                self._send_plain("Not found.", status=HTTPStatus.NOT_FOUND)
                return

            length_raw = self.headers.get("Content-Length")
            length = int(length_raw) if length_raw and length_raw.isdigit() else 0
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            asset_id = params.get("asset_id", [""])[0]
            style_key = params.get("style_key", [""])[0]

            if parsed.path == "/delete":
                payload: JsonObject = {
                    "asset_id": asset_id,
                    "style_key": style_key,
                    "delete_file": params.get("delete_file", [""])[0],
                }
                self.inspector.delete_variant(payload)
                self.send_response(int(HTTPStatus.SEE_OTHER))
                self.send_header("Location", "/?deleted=1")
                self.end_headers()
                return

            offset = params.get("offset", ["0"])[0]
            tilt_x = params.get("tilt_x", ["0"])[0]
            tilt_z = params.get("tilt_z", ["0"])[0]
            contexts = ["all"] if params.get("apply_all", [""])[0] == "on" else ["panel"]
            notes = params.get("notes", [""])[0].strip() or None
            payload: JsonObject = {
                "asset_id": asset_id,
                "style_key": style_key,
                "rotation_deg_offset": normalize_cardinal_offset(float(offset)),
                "rotation_deg_x": normalize_quarter_turn_tilt(float(tilt_x)),
                "rotation_deg_z": normalize_quarter_turn_tilt(float(tilt_z)),
                "contexts": contexts,
                "notes": notes,
            }
            self.inspector.save_orientation(payload)
            query = urlencode(
                {
                    "asset_id": asset_id,
                    "style_key": style_key,
                    "offset": str(payload["rotation_deg_offset"]),
                    "tilt_x": str(payload["rotation_deg_x"]),
                    "tilt_z": str(payload["rotation_deg_z"]),
                    "saved": "1",
                }
            )
            self.send_response(int(HTTPStatus.SEE_OTHER))
            self.send_header("Location", f"/?{query}")
            self.end_headers()
        except Exception as exc:
            self._send_plain(str(exc), status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _build_index(self, query: str) -> bytes:
        params = parse_qs(query)
        targets = self.inspector.list_targets()
        requested_asset_id = params.get("asset_id", [""])[0]
        requested_style_key = params.get("style_key", [""])[0]
        target_value = params.get("target", [""])[0]
        if target_value and "::" in target_value:
            requested_asset_id, requested_style_key = target_value.split("::", 1)
        if not requested_asset_id or not requested_style_key:
            first = first_target(targets)
            if first is not None:
                requested_asset_id, requested_style_key = first

        target = find_target(
            targets=targets,
            asset_id=requested_asset_id,
            style_key=requested_style_key,
        )
        offset = selected_offset(target, params.get("offset", [None])[0])
        tilt_x = selected_tilt(target, params.get("tilt_x", [None])[0], axis="x")
        tilt_z = selected_tilt(target, params.get("tilt_z", [None])[0], axis="z")
        saved = params.get("saved", [""])[0] == "1"
        deleted = params.get("deleted", [""])[0] == "1"
        selected_key = (
            f"{requested_asset_id}::{requested_style_key}"
            if requested_asset_id and requested_style_key
            else ""
        )

        option_rows = "\n".join(
            self._target_option(target=target_row, selected_key=selected_key)
            for target_row in targets
        )
        offset_links = " ".join(
            self._offset_link(
                asset_id=requested_asset_id,
                style_key=requested_style_key,
                offset=value,
                tilt_x=tilt_x,
                tilt_z=tilt_z,
                selected=offset == value,
            )
            for value in OFFSET_LABELS
        )
        tilt_x_links = " ".join(
            (
                self._tilt_link(
                    asset_id=requested_asset_id,
                    style_key=requested_style_key,
                    offset=offset,
                    tilt_x=adjusted_tilt(tilt_x, -90),
                    tilt_z=tilt_z,
                    label="X -90",
                ),
                self._tilt_link(
                    asset_id=requested_asset_id,
                    style_key=requested_style_key,
                    offset=offset,
                    tilt_x=adjusted_tilt(tilt_x, 90),
                    tilt_z=tilt_z,
                    label="X +90",
                ),
            )
        )
        tilt_z_links = " ".join(
            (
                self._tilt_link(
                    asset_id=requested_asset_id,
                    style_key=requested_style_key,
                    offset=offset,
                    tilt_x=tilt_x,
                    tilt_z=adjusted_tilt(tilt_z, -90),
                    label="Z -90",
                ),
                self._tilt_link(
                    asset_id=requested_asset_id,
                    style_key=requested_style_key,
                    offset=offset,
                    tilt_x=tilt_x,
                    tilt_z=adjusted_tilt(tilt_z, 90),
                    label="Z +90",
                ),
            )
        )
        tilt_reset_link = self._tilt_link(
            asset_id=requested_asset_id,
            style_key=requested_style_key,
            offset=offset,
            tilt_x=0,
            tilt_z=0,
            label="Reset tilt",
        )
        viewer_src = (
            "/viewer?"
            + urlencode(
                {
                    "asset_id": requested_asset_id,
                    "style_key": requested_style_key,
                    "offset": str(offset),
                    "tilt_x": str(tilt_x),
                    "tilt_z": str(tilt_z),
                }
            )
            if target is not None
            else ""
        )
        status = (
            "Saved orientation to DB."
            if saved
            else "Deleted selected GLB variant from DB."
            if deleted
            else f"Loaded {len(targets)} GLB inventory variants."
        )
        target_name = target.get("display_label") if target is not None else "No model selected"
        notes = ""
        if target is not None and isinstance(target.get("orientation_review"), dict):
            notes = str(target["orientation_review"].get("notes") or "")

        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Manual GLB Orientation Review</title>
  <style>
    body {{ margin: 0; font: 14px system-ui, sans-serif; color: #111; background: #f6f6f4; }}
    .layout {{ display: grid; grid-template-columns: 360px 1fr; height: 100vh; }}
    aside {{ padding: 14px; border-right: 1px solid #ccc; overflow: auto; background: #fff; }}
    main {{ display: grid; grid-template-rows: auto 1fr; min-width: 0; }}
    h1 {{ font-size: 18px; margin: 0 0 10px; }}
    label {{ display: block; font-weight: 700; margin: 12px 0 6px; }}
    select, textarea, button {{ width: 100%; font: inherit; }}
    select {{ height: 45vh; }}
    textarea {{ min-height: 70px; }}
    .topbar {{ padding: 10px 14px; border-bottom: 1px solid #ccc; background: #fff; }}
    .name {{ font-weight: 800; }}
    .muted {{ color: #666; font-size: 12px; }}
    .status {{ color: #176b32; margin: 8px 0; }}
    .offsets {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0 12px; }}
    .offsets a {{ display: block; padding: 10px; border: 1px solid #bbb; border-radius: 6px; text-align: center; color: #111; text-decoration: none; background: #fafafa; }}
    .offsets a.selected {{ border-color: #176b32; background: #dcfce7; font-weight: 800; }}
    .tilts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0; }}
    .tilts a {{ display: block; padding: 10px; border: 1px solid #bbb; border-radius: 6px; text-align: center; color: #111; text-decoration: none; background: #fafafa; }}
    .tilts.single {{ grid-template-columns: 1fr; }}
    iframe {{ width: 100%; height: 100%; border: 0; background: #202020; }}
    .save {{ margin-top: 12px; padding: 11px; border: 0; border-radius: 6px; background: #176b32; color: #fff; font-weight: 800; cursor: pointer; }}
    .delete {{ margin-top: 10px; padding: 11px; border: 0; border-radius: 6px; background: #b42318; color: #fff; font-weight: 800; cursor: pointer; }}
    .apply {{ display: flex; align-items: center; gap: 8px; font-weight: 400; }}
    .apply input {{ width: auto; }}
    @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; grid-template-rows: auto 65vh; }} select {{ height: 28vh; }} }}
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h1>Manual GLB Orientation Review</h1>
      <div class="status">{escape(status)}</div>
      <form method="get" action="/">
        <label for="target">Inventory objects A-Z</label>
        <select id="target" name="target" onchange="const [asset, style] = this.value.split('::'); location.href='/?asset_id=' + encodeURIComponent(asset) + '&style_key=' + encodeURIComponent(style);">
          {option_rows}
        </select>
        <noscript><button type="submit">Open selected</button></noscript>
      </form>

      <label>Pick which model axis is the real front</label>
      <div class="offsets">{offset_links}</div>

      <label>Stand the object upright if needed</label>
      <div class="muted">Current tilt: X={tilt_x}deg, Z={tilt_z}deg</div>
      <div class="tilts">{tilt_x_links}</div>
      <div class="tilts">{tilt_z_links}</div>
      <div class="tilts single">{tilt_reset_link}</div>

      <form method="post" action="/save">
        <input type="hidden" name="asset_id" value="{escape(requested_asset_id)}">
        <input type="hidden" name="style_key" value="{escape(requested_style_key)}">
        <input type="hidden" name="offset" value="{offset}">
        <input type="hidden" name="tilt_x" value="{tilt_x}">
        <input type="hidden" name="tilt_z" value="{tilt_z}">
        <label class="apply"><input type="checkbox" name="apply_all"> Apply to all 3D contexts</label>
        <label for="notes">Notes</label>
        <textarea id="notes" name="notes">{escape(notes)}</textarea>
        <button class="save" type="submit">Save orientation to DB</button>
      </form>

      <form method="post" action="/delete" onsubmit="return confirm('Delete this selected GLB variant from DB?')">
        <input type="hidden" name="asset_id" value="{escape(requested_asset_id)}">
        <input type="hidden" name="style_key" value="{escape(requested_style_key)}">
        <label class="apply"><input type="checkbox" name="delete_file"> Also delete local .glb file</label>
        <button class="delete" type="submit">Delete selected GLB</button>
      </form>

      <p class="muted">Workflow: first stand the object upright with X/Z tilt if it is lying on its side, then choose the front offset, then save.</p>
    </aside>
    <main>
      <div class="topbar">
        <div class="name">{escape(target_name)}</div>
        <div class="muted">offset={offset}deg | {escape(OFFSET_LABELS[offset])} | tiltX={tilt_x}deg | tiltZ={tilt_z}deg</div>
      </div>
      <iframe src="{escape(viewer_src)}" title="GLB viewer"></iframe>
    </main>
  </div>
</body>
</html>"""
        return document.encode("utf-8")

    def _build_viewer(self, query: str) -> bytes:
        params = parse_qs(query)
        asset_id = params.get("asset_id", [""])[0]
        style_key = params.get("style_key", [""])[0]
        offset = selected_offset(None, params.get("offset", ["0"])[0])
        tilt_x = selected_tilt(None, params.get("tilt_x", ["0"])[0], axis="x")
        tilt_z = selected_tilt(None, params.get("tilt_z", ["0"])[0], axis="z")
        model_url = "/model?" + urlencode({"asset_id": asset_id, "style_key": style_key})
        targets = self.inspector.list_targets()
        target = find_target(targets=targets, asset_id=asset_id, style_key=style_key)
        base_rotation_deg = float((target or {}).get("base_rotation_deg") or 0)
        calibration = (target or {}).get("preview_calibration")
        calibration_json = json.dumps(calibration if isinstance(calibration, dict) else None)
        model_url_json = json.dumps(model_url)
        status_text = (
            f"Loaded {asset_id} [{style_key}] "
            f"offset={offset}deg tiltX={tilt_x}deg tiltZ={tilt_z}deg"
        )
        status_text_json = json.dumps(status_text)
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ margin: 0; overflow: hidden; background: #202020; color: white; font: 13px system-ui, sans-serif; }}
    #status {{ position: fixed; left: 12px; top: 12px; padding: 8px 10px; background: rgba(0,0,0,.7); border-radius: 6px; z-index: 5; }}
    #hint {{ position: fixed; left: 12px; bottom: 12px; padding: 8px 10px; background: rgba(0,0,0,.7); border-radius: 6px; z-index: 5; }}
  </style>
</head>
<body>
  <div id="status">Loading model...</div>
  <div id="hint">White arrow = 2D plan front. Drag to orbit, scroll to zoom.</div>
  <script>
    window.addEventListener('error', (event) => {{
      const status = document.getElementById('status');
      if (status) status.textContent = 'Viewer error: ' + event.message;
    }});
    window.addEventListener('unhandledrejection', (event) => {{
      const status = document.getElementById('status');
      const reason = event.reason && event.reason.message ? event.reason.message : String(event.reason);
      if (status) status.textContent = 'Viewer error: ' + reason;
    }});
  </script>
  <script type="module">
    import * as THREE from '/vendor/three.module.js';
    import {{ OrbitControls }} from '/vendor/OrbitControls.js';
    import {{ GLTFLoader }} from '/vendor/loaders/GLTFLoader.js';

    const status = document.getElementById('status');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x202020);
    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    document.body.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.01, 100);
    camera.position.set(2.6, 2.0, 3.0);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0.55, 0);

    const world = new THREE.Group();
    scene.add(world);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.7));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(4, 6, 5);
    key.castShadow = true;
    scene.add(key);

    const grid = new THREE.GridHelper(4, 8, 0x999999, 0x444444);
    world.add(grid);
    const arrow = new THREE.ArrowHelper(
      new THREE.Vector3(0, 0, -1),
      new THREE.Vector3(0, 0.08, 1.0),
      1.5,
      0xffffff,
      0.25,
      0.12
    );
    world.add(arrow);

    function makeLabel(text, x, y, z, color = '#ffffff') {{
      const c = document.createElement('canvas');
      c.width = 256;
      c.height = 64;
      const ctx = c.getContext('2d');
      ctx.font = '700 28px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = color;
      ctx.fillText(text, 128, 32);
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({{ map: new THREE.CanvasTexture(c), transparent: true }}));
      sprite.position.set(x, y, z);
      sprite.scale.set(0.75, 0.18, 1);
      world.add(sprite);
    }}
    makeLabel('PLAN FRONT', 0, 0.1, -0.85);
    makeLabel('BACK', 0, 0.1, 1.0, '#bdbdbd');
    makeLabel('LEFT', -1.25, 0.1, 0, '#bdbdbd');
    makeLabel('RIGHT', 1.25, 0.1, 0, '#bdbdbd');

    window.addEventListener('resize', resize);
    resize();

    function tick() {{
      requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    }}
    tick();

    main().catch((error) => {{
      status.textContent = 'Viewer error: ' + (error instanceof Error ? error.message : String(error));
      console.error(error);
    }});

    async function main() {{
      const modelUrl = {model_url_json};
      status.textContent = 'Fetching GLB...';
      const response = await fetch(modelUrl, {{ cache: 'no-store' }});
      if (!response.ok) {{
        throw new Error(`GLB request failed: ${{response.status}} ${{response.statusText}}`);
      }}
      const bytes = await response.arrayBuffer();
      status.textContent = `Parsing GLB (${{formatBytes(bytes.byteLength)}})...`;
      const gltf = await new Promise((resolve, reject) => {{
        new GLTFLoader().parse(bytes, '', resolve, reject);
      }});
      const sceneSource = gltf.scene || (Array.isArray(gltf.scenes) ? gltf.scenes[0] : null);
      if (!sceneSource || typeof sceneSource.clone !== 'function') {{
        throw new Error('GLB loaded, but it does not contain a usable scene.');
      }}

      const root = new THREE.Group();
      const yawRoot = new THREE.Group();
      const tiltRoot = new THREE.Group();
      const calibrationRoot = new THREE.Group();
      const model = sceneSource.clone(true);
      yawRoot.rotation.y = THREE.MathUtils.degToRad({base_rotation_deg + offset});
      tiltRoot.rotation.x = THREE.MathUtils.degToRad({tilt_x});
      tiltRoot.rotation.z = THREE.MathUtils.degToRad({tilt_z});
      calibrationRoot.add(model);
      tiltRoot.add(calibrationRoot);
      yawRoot.add(tiltRoot);
      applyCalibrationMatrix(calibrationRoot, {calibration_json});
      root.add(yawRoot);
      world.add(root);
      root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root);
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      if (!Number.isFinite(maxDim) || maxDim <= 0) {{
        throw new Error('GLB parsed, but its bounds are empty.');
      }}
      const scale = Math.min(
        1.8 / Math.max(size.x, size.z, 0.001),
        1.6 / Math.max(size.x, size.y, size.z, 0.001)
      );
      root.scale.setScalar(scale);
      root.updateMatrixWorld(true);
      const fitted = new THREE.Box3().setFromObject(root);
      const center = fitted.getCenter(new THREE.Vector3());
      root.position.x -= center.x;
      root.position.z -= center.z;
      root.position.y -= fitted.min.y;
      root.traverse((node) => {{
        if (node.isMesh) {{
          node.castShadow = true;
          node.receiveShadow = true;
          if (node.material) {{
            const materials = Array.isArray(node.material) ? node.material : [node.material];
            for (const material of materials) {{
              material.side = THREE.DoubleSide;
              material.needsUpdate = true;
            }}
          }}
        }}
      }});
      status.textContent = {status_text_json};
    }}

    function resize() {{
      renderer.setSize(window.innerWidth, window.innerHeight);
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
    }}

    function formatBytes(size) {{
      if (!Number.isFinite(size)) return 'unknown size';
      if (size < 1024 * 1024) return `${{Math.round(size / 1024)}} KB`;
      return `${{(size / (1024 * 1024)).toFixed(1)}} MB`;
    }}

    function applyCalibrationMatrix(root, calibration) {{
      if (!calibration || calibration.status !== 'calibrated') return;
      const matrixRows = calibration.rotationMatrix || calibration.rotation_matrix;
      if (!Array.isArray(matrixRows) || matrixRows.length !== 4) return;
      const m = new THREE.Matrix4();
      m.set(
        matrixRows[0][0], matrixRows[0][1], matrixRows[0][2], matrixRows[0][3],
        matrixRows[1][0], matrixRows[1][1], matrixRows[1][2], matrixRows[1][3],
        matrixRows[2][0], matrixRows[2][1], matrixRows[2][2], matrixRows[2][3],
        matrixRows[3][0], matrixRows[3][1], matrixRows[3][2], matrixRows[3][3]
      );
      root.applyMatrix4(m);
    }}
  </script>
</body>
</html>"""
        return document.encode("utf-8")

    def _target_option(self, *, target: JsonObject, selected_key: str) -> str:
        key = target_key(target)
        label = target.get("display_label") or f"{target.get('name')} - {target.get('style_key')}"
        selected = " selected" if key == selected_key else ""
        return f'<option value="{escape(key)}"{selected}>{escape(label)}</option>'

    def _offset_link(
        self,
        *,
        asset_id: str,
        style_key: str,
        offset: int,
        tilt_x: int,
        tilt_z: int,
        selected: bool,
    ) -> str:
        query = urlencode(
            {
                "asset_id": asset_id,
                "style_key": style_key,
                "offset": str(offset),
                "tilt_x": str(tilt_x),
                "tilt_z": str(tilt_z),
            }
        )
        class_name = " selected" if selected else ""
        return f'<a class="{class_name}" href="/?{query}">{escape(OFFSET_LABELS[offset])}<br>{offset}deg</a>'

    def _tilt_link(
        self,
        *,
        asset_id: str,
        style_key: str,
        offset: int,
        tilt_x: int,
        tilt_z: int,
        label: str,
    ) -> str:
        query = urlencode(
            {
                "asset_id": asset_id,
                "style_key": style_key,
                "offset": str(offset),
                "tilt_x": str(tilt_x),
                "tilt_z": str(tilt_z),
            }
        )
        return f'<a href="/?{query}">{escape(label)}<br>X={tilt_x} Z={tilt_z}</a>'

    def _send_vendor_file(self, relative_path: str) -> None:
        allowed_files = {
            "three.module.js": self.vendor_dir / "three.module.js",
            "OrbitControls.js": self.vendor_dir / "OrbitControls.js",
            "loaders/GLTFLoader.js": self.vendor_dir / "loaders" / "GLTFLoader.js",
            "utils/BufferGeometryUtils.js": self.vendor_dir / "utils" / "BufferGeometryUtils.js",
        }
        path = allowed_files.get(relative_path)
        if path is None or not path.exists():
            self._send_plain("Vendor file not found.", status=HTTPStatus.NOT_FOUND)
            return
        self._send_file(path, default_content_type="text/javascript")

    def _send_file(self, path: Path, *, default_content_type: str) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or default_content_type
        body = path.read_bytes()
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: bytes) -> None:
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_plain(self, text: str, *, status: HTTPStatus) -> None:
        body = text.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_handler(
    *,
    inspector: InventoryGlbOrientationInspector,
    vendor_dir: Path,
) -> type[ManualInventoryGlbReviewHandler]:
    class BoundManualInventoryGlbReviewHandler(ManualInventoryGlbReviewHandler):
        pass

    BoundManualInventoryGlbReviewHandler.inspector = inspector
    BoundManualInventoryGlbReviewHandler.vendor_dir = vendor_dir
    return BoundManualInventoryGlbReviewHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the simplest manual inventory GLB orientation review page."
    )
    parser.add_argument("--tenant-id", default="demo_tenant")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--asset-ids", nargs="*", default=None)
    parser.add_argument("--style-keys", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--models-public-dir", type=Path, default=DEFAULT_MODELS_PUBLIC_DIR)
    parser.add_argument("--models-url-prefix", default=DEFAULT_MODELS_URL_PREFIX)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    inspector = InventoryGlbOrientationInspector(
        tenant_id=str(args.tenant_id),
        models_public_dir=(ROOT_DIR / args.models_public_dir).resolve(),
        models_url_prefix=str(args.models_url_prefix),
        asset_ids=args.asset_ids,
        style_keys=args.style_keys,
        limit=args.limit,
    )
    handler = build_handler(
        inspector=inspector,
        vendor_dir=(ROOT_DIR / "frontend/src/vendor/three").resolve(),
    )
    server = ThreadingHTTPServer((str(args.host), int(args.port)), handler)
    print(f"Manual inventory GLB orientation review: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping review server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
