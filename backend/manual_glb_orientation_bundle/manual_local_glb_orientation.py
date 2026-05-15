from __future__ import annotations

import argparse
import html
import json
import mimetypes
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
DEFAULT_GLB_PATH = Path(__file__).resolve().parent / "demo_inventory"
VENDOR_DIR = Path(__file__).resolve().parent / "frontend" / "src" / "vendor" / "three"
BASIS_DIR = Path(__file__).resolve().parent / "frontend" / "public" / "assets" / "three" / "basis"
MODEL_FRONT_AXIS_BY_OFFSET = {
    0: "-z",
    90: "+x",
    180: "+z",
    270: "-x",
}
OFFSET_LABELS = {
    0: "Front is -Z",
    90: "Front is +X",
    180: "Front is +Z",
    270: "Front is -X",
}


def escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


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


def selected_offset(raw_offset: str | None) -> int:
    if raw_offset:
        try:
            return normalize_cardinal_offset(float(raw_offset))
        except ValueError:
            return 0
    return 0


def selected_tilt(raw_tilt: str | None) -> int:
    if raw_tilt:
        try:
            return normalize_quarter_turn_tilt(float(raw_tilt))
        except ValueError:
            return 0
    return 0


def adjusted_tilt(value: int, delta: int) -> int:
    return normalize_quarter_turn_tilt(float(value + delta))


def orientation_sidecar_path(glb_path: Path) -> Path:
    return Path(f"{glb_path}.orientation.json")


def discover_glb_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".glb":
            raise ValueError(f"Expected a .glb file, got: {input_path}")
        return [input_path.resolve()]
    if input_path.is_dir():
        paths = sorted(path.resolve() for path in input_path.glob("*.glb"))
        if paths:
            return paths
        raise ValueError(f"No .glb files found in directory: {input_path}")
    raise ValueError(f"GLB file or directory not found: {input_path}")


def selected_glb_path(
    *,
    params: dict[str, list[str]],
    glb_paths: list[Path],
) -> Path:
    raw_file = params.get("file", [""])[0]
    if raw_file:
        requested_name = Path(raw_file).name
        for glb_path in glb_paths:
            if raw_file == str(glb_path) or requested_name == glb_path.name:
                return glb_path
    return glb_paths[0]


def selected_glb_index(*, glb_path: Path, glb_paths: list[Path]) -> int:
    for index, candidate in enumerate(glb_paths):
        if candidate == glb_path:
            return index
    return 0


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


def read_object(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def load_saved_orientation(orientation_path: Path) -> dict[str, object] | None:
    if not orientation_path.is_file():
        return None
    try:
        payload = json.loads(orientation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return read_object(payload)


def saved_offset(payload: dict[str, object] | None) -> int:
    if payload is None:
        return 0
    override = read_object(payload.get("preview_override"))
    raw_value = (
        read_number((override or {}).get("rotation_deg_offset"))
        or read_number(payload.get("rotation_deg_offset"))
        or 0.0
    )
    return normalize_cardinal_offset(raw_value)


def saved_tilt(payload: dict[str, object] | None, *, axis: str) -> int:
    if payload is None:
        return 0
    override = read_object(payload.get("preview_override"))
    key = f"rotation_deg_{axis}"
    raw_value = (
        read_number((override or {}).get(key))
        or read_number(payload.get(key))
        or 0.0
    )
    return normalize_quarter_turn_tilt(raw_value)


def resolve_orientation(
    *,
    params: dict[str, list[str]],
    saved_payload: dict[str, object] | None,
) -> tuple[int, int, int]:
    raw_offset = params.get("offset", [None])[0]
    raw_tilt_x = params.get("tilt_x", [None])[0]
    raw_tilt_z = params.get("tilt_z", [None])[0]
    offset = selected_offset(raw_offset) if raw_offset is not None else saved_offset(saved_payload)
    tilt_x = (
        selected_tilt(raw_tilt_x)
        if raw_tilt_x is not None
        else saved_tilt(saved_payload, axis="x")
    )
    tilt_z = (
        selected_tilt(raw_tilt_z)
        if raw_tilt_z is not None
        else saved_tilt(saved_payload, axis="z")
    )
    return offset, tilt_x, tilt_z


def build_preview_payload(
    *,
    glb_path: Path,
    offset: int,
    tilt_x: int,
    tilt_z: int,
) -> dict[str, object]:
    preview_override = {
        "enabled": True,
        "contexts": ["panel"],
        "rotation_deg_offset": float(offset),
        "rotation_deg_x": float(tilt_x),
        "rotation_deg_z": float(tilt_z),
        "notes": "Manual local GLB orientation review.",
    }
    orientation_review = {
        "version": 1,
        "status": "reviewed",
        "front_axis": MODEL_FRONT_AXIS_BY_OFFSET[offset],
        "rotation_deg_offset": float(offset),
        "rotation_deg_x": float(tilt_x),
        "rotation_deg_z": float(tilt_z),
        "reference_front": "2D plan +Y / 3D scene -Z",
        "contexts": ["panel"],
        "notes": "Manual local GLB orientation review.",
    }
    return {
        "source_file": str(glb_path),
        "file_name": glb_path.name,
        "front_axis": MODEL_FRONT_AXIS_BY_OFFSET[offset],
        "rotation_deg_offset": float(offset),
        "rotation_deg_x": float(tilt_x),
        "rotation_deg_z": float(tilt_z),
        "preview_override": preview_override,
        "orientation_review": orientation_review,
    }


class LocalGlbOrientationHandler(BaseHTTPRequestHandler):
    glb_paths: list[Path]
    basis_dir: Path

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
                glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
                self._send_file(glb_path, default_content_type="model/gltf-binary")
                return
            if parsed.path == "/export.json":
                self._send_json(self._build_export_payload(parsed.query))
                return
            if parsed.path.startswith("/vendor/"):
                self._send_vendor_file(parsed.path.removeprefix("/vendor/"))
                return
            if parsed.path.startswith("/basis/"):
                self._send_basis_file(parsed.path.removeprefix("/basis/"))
                return
            self._send_plain("Not found.", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_plain(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/save":
                length_raw = self.headers.get("Content-Length")
                length = int(length_raw) if length_raw and length_raw.isdigit() else 0
                body = self.rfile.read(length).decode("utf-8")
                params = parse_qs(body)
                glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
                orientation_path = orientation_sidecar_path(glb_path)
                offset, tilt_x, tilt_z = resolve_orientation(
                    params=params,
                    saved_payload=load_saved_orientation(orientation_path),
                )
                payload = build_preview_payload(
                    glb_path=glb_path,
                    offset=offset,
                    tilt_x=tilt_x,
                    tilt_z=tilt_z,
                )
                payload["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
                orientation_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                    encoding="utf-8",
                )
                query = urlencode(
                    {
                        "file": glb_path.name,
                        "offset": str(offset),
                        "tilt_x": str(tilt_x),
                        "tilt_z": str(tilt_z),
                        "saved": "1",
                    }
                )
                self.send_response(int(HTTPStatus.SEE_OTHER))
                self.send_header("Location", f"/?{query}")
                self.end_headers()
                return

            if parsed.path == "/reset-saved":
                length_raw = self.headers.get("Content-Length")
                length = int(length_raw) if length_raw and length_raw.isdigit() else 0
                body = self.rfile.read(length).decode("utf-8")
                params = parse_qs(body)
                glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
                orientation_path = orientation_sidecar_path(glb_path)
                if orientation_path.exists():
                    orientation_path.unlink()
                self.send_response(int(HTTPStatus.SEE_OTHER))
                reset_query = urlencode({"file": glb_path.name, "reset": "1"})
                self.send_header("Location", f"/?{reset_query}")
                self.end_headers()
                return

            self._send_plain("Not found.", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_plain(str(exc), status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _build_index(self, query: str) -> bytes:
        params = parse_qs(query)
        glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
        orientation_path = orientation_sidecar_path(glb_path)
        current_index = selected_glb_index(glb_path=glb_path, glb_paths=self.glb_paths)
        saved_payload = load_saved_orientation(orientation_path)
        offset, tilt_x, tilt_z = resolve_orientation(
            params=params,
            saved_payload=saved_payload,
        )
        payload = build_preview_payload(
            glb_path=glb_path,
            offset=offset,
            tilt_x=tilt_x,
            tilt_z=tilt_z,
        )
        payload["orientation_file"] = str(orientation_path)
        pretty_payload = json.dumps(payload, indent=2, ensure_ascii=True)
        saved_now = params.get("saved", [""])[0] == "1"
        reset_now = params.get("reset", [""])[0] == "1"
        status_text = (
            "Saved local orientation."
            if saved_now
            else "Cleared saved orientation."
            if reset_now
            else "Loaded saved orientation."
            if saved_payload is not None
            else "No saved orientation yet."
        )
        viewer_src = (
            "/viewer?"
            + urlencode(
                {
                    "file": glb_path.name,
                    "offset": str(offset),
                    "tilt_x": str(tilt_x),
                    "tilt_z": str(tilt_z),
                }
            )
        )
        export_url = (
            "/export.json?"
            + urlencode(
                {
                    "file": glb_path.name,
                    "offset": str(offset),
                    "tilt_x": str(tilt_x),
                    "tilt_z": str(tilt_z),
                }
            )
        )
        offset_links = " ".join(
            self._offset_link(
                offset=value,
                file_name=glb_path.name,
                tilt_x=tilt_x,
                tilt_z=tilt_z,
                selected=offset == value,
            )
            for value in OFFSET_LABELS
        )
        tilt_x_links = " ".join(
            (
                self._tilt_link(
                    offset=offset,
                    file_name=glb_path.name,
                    tilt_x=adjusted_tilt(tilt_x, -90),
                    tilt_z=tilt_z,
                    label="X -90",
                ),
                self._tilt_link(
                    offset=offset,
                    file_name=glb_path.name,
                    tilt_x=adjusted_tilt(tilt_x, 90),
                    tilt_z=tilt_z,
                    label="X +90",
                ),
            )
        )
        tilt_z_links = " ".join(
            (
                self._tilt_link(
                    offset=offset,
                    file_name=glb_path.name,
                    tilt_x=tilt_x,
                    tilt_z=adjusted_tilt(tilt_z, -90),
                    label="Z -90",
                ),
                self._tilt_link(
                    offset=offset,
                    file_name=glb_path.name,
                    tilt_x=tilt_x,
                    tilt_z=adjusted_tilt(tilt_z, 90),
                    label="Z +90",
                ),
            )
        )
        tilt_reset_link = self._tilt_link(
            offset=offset,
            file_name=glb_path.name,
            tilt_x=0,
            tilt_z=0,
            label="Reset tilt",
        )
        file_links = "\n".join(
            self._file_link(
                glb_path=candidate,
                selected=candidate == glb_path,
                index=index,
                total=len(self.glb_paths),
            )
            for index, candidate in enumerate(self.glb_paths)
        )
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local GLB Orientation Review</title>
  <style>
    body {{ margin: 0; font: 14px system-ui, sans-serif; color: #111; background: #f6f6f4; }}
    .layout {{ display: grid; grid-template-columns: 420px 1fr; height: 100vh; }}
    aside {{ padding: 14px; border-right: 1px solid #ccc; overflow: auto; background: #fff; }}
    main {{ display: grid; grid-template-rows: auto 1fr; min-width: 0; }}
    h1 {{ font-size: 18px; margin: 0 0 8px; }}
    h2 {{ font-size: 14px; margin: 16px 0 8px; }}
    .muted {{ color: #666; font-size: 12px; }}
    .topbar {{ padding: 10px 14px; border-bottom: 1px solid #ccc; background: #fff; }}
    .name {{ font-weight: 800; }}
    .offsets {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0 12px; }}
    .offsets a {{ display: block; padding: 10px; border: 1px solid #bbb; border-radius: 6px; text-align: center; color: #111; text-decoration: none; background: #fafafa; }}
    .offsets a.selected {{ border-color: #176b32; background: #dcfce7; font-weight: 800; }}
    .tilts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0; }}
    .tilts a {{ display: block; padding: 10px; border: 1px solid #bbb; border-radius: 6px; text-align: center; color: #111; text-decoration: none; background: #fafafa; }}
    .tilts.single {{ grid-template-columns: 1fr; }}
    .files {{ display: grid; gap: 6px; margin: 8px 0 12px; }}
    .files a {{ display: block; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; color: #111; text-decoration: none; background: #fafafa; }}
    .files a.selected {{ border-color: #176b32; background: #dcfce7; font-weight: 800; }}
    .files .reviewed {{ color: #176b32; font-weight: 800; }}
    .export {{ display: inline-block; margin-top: 8px; padding: 10px 12px; border-radius: 6px; background: #176b32; color: #fff; font-weight: 700; text-decoration: none; }}
    pre {{ margin: 8px 0 0; padding: 12px; border-radius: 6px; background: #111; color: #d8f3dc; overflow: auto; font-size: 12px; line-height: 1.45; }}
    iframe {{ width: 100%; height: 100%; border: 0; background: #202020; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    @media (max-width: 980px) {{ .layout {{ grid-template-columns: 1fr; grid-template-rows: auto 60vh; }} }}
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h1>Local GLB Orientation Review</h1>
      <div><strong>File:</strong> {escape(glb_path.name)}</div>
      <div class="muted"><code>{escape(glb_path)}</code></div>
      <div class="muted"><strong>Item:</strong> {current_index + 1}/{len(self.glb_paths)}</div>
      <div class="muted" style="margin-top:6px;"><strong>Status:</strong> {escape(status_text)}</div>
      <div class="muted"><strong>Saved to:</strong> <code>{escape(orientation_path)}</code></div>

      <h2>0. Pick a model</h2>
      <div class="files">{file_links}</div>

      <h2>1. Pick the real front</h2>
      <div class="offsets">{offset_links}</div>

      <h2>2. Stand the object upright if needed</h2>
      <div class="muted">Current tilt: X={tilt_x}deg, Z={tilt_z}deg</div>
      <div class="tilts">{tilt_x_links}</div>
      <div class="tilts">{tilt_z_links}</div>
      <div class="tilts single">{tilt_reset_link}</div>

      <form method="post" action="/save" style="margin-top:12px;">
        <input type="hidden" name="file" value="{escape(glb_path.name)}">
        <input type="hidden" name="offset" value="{offset}">
        <input type="hidden" name="tilt_x" value="{tilt_x}">
        <input type="hidden" name="tilt_z" value="{tilt_z}">
        <button class="export" type="submit" style="border:0; cursor:pointer;">Save local orientation</button>
      </form>
      <form method="post" action="/reset-saved" onsubmit="return confirm('Delete the saved local orientation file?')" style="margin-top:8px;">
        <input type="hidden" name="file" value="{escape(glb_path.name)}">
        <button type="submit" style="width:100%; padding:10px 12px; border:0; border-radius:6px; background:#b42318; color:#fff; font-weight:700; cursor:pointer;">Clear saved orientation</button>
      </form>

      <h2>3. Copy the output</h2>
      <div class="muted">This tool does not write to DB. It only helps you inspect the file and produces the payload to reuse later.</div>
      <a class="export" href="{escape(export_url)}" target="_blank" rel="noreferrer">Open JSON only</a>
      <pre>{escape(pretty_payload)}</pre>
    </aside>
    <main>
      <div class="topbar">
        <div class="name">{escape(glb_path.name)}</div>
        <div class="muted">offset={offset}deg | {escape(OFFSET_LABELS[offset])} | tiltX={tilt_x}deg | tiltZ={tilt_z}deg | front_axis={escape(MODEL_FRONT_AXIS_BY_OFFSET[offset])}</div>
      </div>
      <iframe src="{escape(viewer_src)}" title="GLB viewer"></iframe>
    </main>
  </div>
</body>
</html>"""
        return document.encode("utf-8")

    def _build_viewer(self, query: str) -> bytes:
        params = parse_qs(query)
        glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
        orientation_path = orientation_sidecar_path(glb_path)
        offset, tilt_x, tilt_z = resolve_orientation(
            params=params,
            saved_payload=load_saved_orientation(orientation_path),
        )
        model_url_json = json.dumps(f"/model?{urlencode({'file': glb_path.name})}")
        status_text = (
            f"Loaded {glb_path.name} "
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
    import {{ KTX2Loader }} from '/vendor/loaders/KTX2Loader.js';

    const status = document.getElementById('status');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x202020);
    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    document.body.appendChild(renderer.domElement);
    const ktx2Loader = new KTX2Loader()
      .setTranscoderPath('/basis/')
      .setWorkerLimit(2)
      .detectSupport(renderer);

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
      const loader = new GLTFLoader();
      if (typeof loader.setKTX2Loader === 'function') {{
        loader.setKTX2Loader(ktx2Loader);
      }}
      const gltf = await new Promise((resolve, reject) => {{
        loader.parse(bytes, '', resolve, reject);
      }});
      const sceneSource = gltf.scene || (Array.isArray(gltf.scenes) ? gltf.scenes[0] : null);
      if (!sceneSource || typeof sceneSource.clone !== 'function') {{
        throw new Error('GLB loaded, but it does not contain a usable scene.');
      }}

      const root = new THREE.Group();
      const yawRoot = new THREE.Group();
      const tiltRoot = new THREE.Group();
      const model = sceneSource.clone(true);
      yawRoot.rotation.y = THREE.MathUtils.degToRad({offset});
      tiltRoot.rotation.x = THREE.MathUtils.degToRad({tilt_x});
      tiltRoot.rotation.z = THREE.MathUtils.degToRad({tilt_z});
      tiltRoot.add(model);
      yawRoot.add(tiltRoot);
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
  </script>
</body>
</html>"""
        return document.encode("utf-8")

    def _build_export_payload(self, query: str) -> dict[str, object]:
        params = parse_qs(query)
        glb_path = selected_glb_path(params=params, glb_paths=self.glb_paths)
        orientation_path = orientation_sidecar_path(glb_path)
        offset, tilt_x, tilt_z = resolve_orientation(
            params=params,
            saved_payload=load_saved_orientation(orientation_path),
        )
        payload = build_preview_payload(
            glb_path=glb_path,
            offset=offset,
            tilt_x=tilt_x,
            tilt_z=tilt_z,
        )
        payload["orientation_file"] = str(orientation_path)
        return payload

    def _offset_link(
        self,
        *,
        offset: int,
        file_name: str,
        tilt_x: int,
        tilt_z: int,
        selected: bool,
    ) -> str:
        query = urlencode(
            {
                "file": file_name,
                "offset": str(offset),
                "tilt_x": str(tilt_x),
                "tilt_z": str(tilt_z),
            }
        )
        classes = "selected" if selected else ""
        return (
            f'<a class="{classes}" href="/?{query}">'
            f"{escape(OFFSET_LABELS[offset])}<br>{offset}deg</a>"
        )

    def _tilt_link(
        self,
        *,
        offset: int,
        file_name: str,
        tilt_x: int,
        tilt_z: int,
        label: str,
    ) -> str:
        query = urlencode(
            {
                "file": file_name,
                "offset": str(offset),
                "tilt_x": str(tilt_x),
                "tilt_z": str(tilt_z),
            }
        )
        return f'<a href="/?{query}">{escape(label)}</a>'

    def _file_link(
        self,
        *,
        glb_path: Path,
        selected: bool,
        index: int,
        total: int,
    ) -> str:
        query = urlencode({"file": glb_path.name})
        classes = "selected" if selected else ""
        review_label = (
            '<span class="reviewed">reviewed</span>'
            if orientation_sidecar_path(glb_path).is_file()
            else "unreviewed"
        )
        return (
            f'<a class="{classes}" href="/?{query}">'
            f"{index + 1}/{total} - {escape(glb_path.name)}<br>"
            f'<span class="muted">{review_label}</span></a>'
        )

    def _send_vendor_file(self, relative_path: str) -> None:
        relative = Path(relative_path)
        candidate = (VENDOR_DIR / relative).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Vendor file not found: {candidate}")
        if VENDOR_DIR.resolve() not in candidate.parents and candidate != VENDOR_DIR.resolve():
            raise FileNotFoundError(f"Vendor file is outside allowed directory: {candidate}")
        self._send_file(candidate)

    def _send_basis_file(self, relative_path: str) -> None:
        relative = Path(relative_path)
        candidate = (self.basis_dir / relative).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Basis transcoder file not found: {candidate}")
        resolved_basis_dir = self.basis_dir.resolve()
        if resolved_basis_dir not in candidate.parents and candidate != resolved_basis_dir:
            raise FileNotFoundError(f"Basis file is outside allowed directory: {candidate}")
        self._send_file(candidate)

    def _send_file(self, path: Path, *, default_content_type: str | None = None) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        content_type = (
            default_content_type
            or mimetypes.guess_type(path.name)[0]
            or "application/octet-stream"
        )
        data = path.read_bytes()
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, document: bytes) -> None:
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(document)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(document)

    def _send_json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_plain(self, message: str, *, status: HTTPStatus) -> None:
        data = message.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and manually orient a local GLB file without reading from DB."
    )
    parser.add_argument(
        "glb_path",
        nargs="?",
        default=str(DEFAULT_GLB_PATH),
        help="Path to a local .glb file or a directory containing .glb files.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="HTTP host to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="HTTP port to bind.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    input_path = Path(args.glb_path).expanduser().resolve()
    try:
        glb_paths = discover_glb_paths(input_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    handler = type(
        "BoundLocalGlbOrientationHandler",
        (LocalGlbOrientationHandler,),
        {
            "glb_paths": glb_paths,
            "basis_dir": BASIS_DIR.resolve(),
        },
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving local GLB orientation viewer for {len(glb_paths)} model(s)")
    print(f"Input: {input_path}")
    print("Orientation sidecars are saved next to each .glb file.")
    print(f"Open http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
