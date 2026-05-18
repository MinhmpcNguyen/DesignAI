import {
  AmbientLight,
  DirectionalLight,
  Group,
  Mesh,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import {
  buildThumbnailNormalizeOptions,
  normalizeGltfRoot,
} from "@/lib/gltfNormalize";

const SIZE = 128; // offscreen canvas size (rendered at 2× for sharpness)

const cache = new Map<string, string>();
let _renderer: WebGLRenderer | null = null;
let _suspended = false;
let _ktx2Loader: KTX2Loader | null = null;

function getRenderer(): WebGLRenderer | null {
  if (typeof window === "undefined") return null;
  if (_suspended) return null;
  if (!_renderer) {
    _renderer = new WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true, // required for toDataURL()
    });
    _renderer.setSize(SIZE, SIZE);
    _renderer.setPixelRatio(window.devicePixelRatio > 1 ? 2 : 1);
    _renderer.outputColorSpace = SRGBColorSpace;
  }
  return _renderer;
}

/**
 * Renders a GLB model to a data URL using a single shared offscreen WebGL
 * renderer. Results are cached — repeated calls for the same URL are instant.
 */
export async function renderModelThumbnail(modelUrl: string): Promise<string> {
  if (cache.has(modelUrl)) return cache.get(modelUrl)!;

  const renderer = getRenderer();
  if (!renderer) return "";

  // Lazily initialise the KTX2Loader bound to the offscreen renderer.
  if (!_ktx2Loader) {
    _ktx2Loader = new KTX2Loader();
    _ktx2Loader.setTranscoderPath("/basis/");
    _ktx2Loader.detectSupport(renderer);
  }

  const loader = new GLTFLoader();
  loader.setKTX2Loader(_ktx2Loader);
  const gltf = await new Promise<{ scene: Group }>((resolve, reject) =>
    loader.load(modelUrl, resolve as (g: unknown) => void, undefined, reject),
  );

  const scene = new Scene();

  // Lighting: main key + soft fill
  scene.add(new AmbientLight(0xffffff, 0.75));
  const key = new DirectionalLight(0xffffff, 1.4);
  key.position.set(3, 5, 4);
  scene.add(key);
  const fill = new DirectionalLight(0xffffff, 0.35);
  fill.position.set(-3, 2, -4);
  scene.add(fill);

  // Normalize model with the same pipeline used at runtime.
  const model = gltf.scene;
  normalizeGltfRoot(model, buildThumbnailNormalizeOptions(modelUrl));

  scene.add(model);

  // Isometric-ish camera (fixed 45° angle)
  const camera = new PerspectiveCamera(45, 1, 0.001, 1000);
  camera.position.set(1.4, 1.0, 1.4);
  camera.lookAt(0, 0, 0);

  renderer.render(scene, camera);
  const dataUrl = renderer.domElement.toDataURL("image/webp", 0.85);

  // Release GPU memory for this model — keep renderer alive for next item
  model.traverse((child) => {
    if (!(child instanceof Mesh)) return;
    child.geometry.dispose();
    const mats = Array.isArray(child.material)
      ? child.material
      : [child.material];
    mats.forEach((m) => m.dispose());
  });

  cache.set(modelUrl, dataUrl);
  return dataUrl;
}

/**
 * Disposes the shared offscreen WebGL renderer and frees its GPU context.
 * Also sets a suspended flag so the async thumbnail loop cannot silently
 * resurrect the renderer after disposal (race-condition guard).
 * Call this before mounting the main 3D scene to avoid hitting the browser's
 * concurrent WebGL context limit.
 */
export function disposeThumbnailRenderer(): void {
  _suspended = true; // block recreation before dispose, closing the race window
  if (_ktx2Loader) {
    _ktx2Loader.dispose();
    _ktx2Loader = null;
  }
  if (_renderer) {
    _renderer.dispose();
    _renderer = null;
  }
}

/**
 * Re-enables thumbnail rendering after the main 3D scene has been unmounted.
 * Call this in the cleanup of the design-page effect so that the home/project
 * pages can render thumbnails again after the user navigates away.
 */
export function enableThumbnailRenderer(): void {
  _suspended = false;
}
