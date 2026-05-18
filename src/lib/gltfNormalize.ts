import { Box3, Object3D, Vector3 } from "three";

export type GltfScaleMode = "per-axis" | "uniform-contain";

export interface GltfAssetOverride {
  centerX?: boolean;
  centerY?: boolean;
  centerZ?: boolean;
  alignFloorY?: boolean;
  scaleMode?: GltfScaleMode;
  /**
   * Optional fine-tuning scale multiplier for exceptional assets.
   * - number: uniform multiplier for all axes
   * - tuple: per-axis multiplier [x, y, z]
   */
  scaleMultiplier?: number | [number, number, number];
  /** Optional offset after normalization, in local space. */
  extraOffset?: [number, number, number];
  /** Optional yaw rotation (radians) applied after reset. */
  yaw?: number;
}

export interface NormalizeGltfOptions {
  targetSize: [number, number, number];
  centerX?: boolean;
  centerY?: boolean;
  centerZ?: boolean;
  alignFloorY?: boolean;
  scaleMode?: GltfScaleMode;
  scaleMultiplier?: number | [number, number, number];
  extraOffset?: [number, number, number];
  yaw?: number;
}

/**
 * Optional per-asset adjustments. Keep this small and only for true outliers.
 * Most assets should work with default normalization and need no overrides.
 */
export const gltfAssetOverridesByUrl: Record<string, GltfAssetOverride> = {};

const TMP_BOX = new Box3();
const TMP_SIZE = new Vector3();
const TMP_CENTER = new Vector3();

function getMultiplierTuple(
  scaleMultiplier: NormalizeGltfOptions["scaleMultiplier"],
): [number, number, number] {
  if (Array.isArray(scaleMultiplier)) return scaleMultiplier;
  if (typeof scaleMultiplier === "number") {
    return [scaleMultiplier, scaleMultiplier, scaleMultiplier];
  }
  return [1, 1, 1];
}

/**
 * Normalize a cloned GLTF root so every asset behaves consistently:
 * - reset root transform,
 * - scale to target box,
 * - center axes as requested,
 * - optionally place model bottom at local Y = -(targetHeight/2).
 */
export function normalizeGltfRoot(
  root: Object3D,
  {
    targetSize,
    centerX = true,
    centerY = false,
    centerZ = true,
    alignFloorY = true,
    scaleMode = "per-axis",
    scaleMultiplier,
    extraOffset,
    yaw = 0,
  }: NormalizeGltfOptions,
): void {
  root.position.set(0, 0, 0);
  root.rotation.set(0, 0, 0);
  root.scale.set(1, 1, 1);
  root.updateMatrixWorld(true);

  TMP_BOX.setFromObject(root);
  TMP_BOX.getSize(TMP_SIZE);

  const modelSizeX = TMP_SIZE.x > 0 ? TMP_SIZE.x : 1;
  const modelSizeY = TMP_SIZE.y > 0 ? TMP_SIZE.y : 1;
  const modelSizeZ = TMP_SIZE.z > 0 ? TMP_SIZE.z : 1;

  let scaleX = targetSize[0] / modelSizeX;
  let scaleY = targetSize[1] / modelSizeY;
  let scaleZ = targetSize[2] / modelSizeZ;

  if (scaleMode === "uniform-contain") {
    const uniform = Math.min(scaleX, scaleY, scaleZ);
    scaleX = uniform;
    scaleY = uniform;
    scaleZ = uniform;
  }

  const [mx, my, mz] = getMultiplierTuple(scaleMultiplier);
  root.scale.set(scaleX * mx, scaleY * my, scaleZ * mz);

  if (yaw !== 0) {
    root.rotation.y = yaw;
  }

  root.updateMatrixWorld(true);

  TMP_BOX.setFromObject(root);
  TMP_BOX.getCenter(TMP_CENTER);

  const nextPos = new Vector3(0, 0, 0);
  if (centerX) nextPos.x = -TMP_CENTER.x;
  if (centerY) nextPos.y = -TMP_CENTER.y;
  if (centerZ) nextPos.z = -TMP_CENTER.z;
  root.position.copy(nextPos);
  root.updateMatrixWorld(true);

  if (alignFloorY) {
    TMP_BOX.setFromObject(root);
    root.position.y += -(targetSize[1] / 2) - TMP_BOX.min.y;
    root.updateMatrixWorld(true);
  }

  if (extraOffset) {
    root.position.x += extraOffset[0];
    root.position.y += extraOffset[1];
    root.position.z += extraOffset[2];
    root.updateMatrixWorld(true);
  }
}

export function buildRuntimeNormalizeOptions(
  modelUrl: string,
  targetSize: [number, number, number],
): NormalizeGltfOptions {
  const override = gltfAssetOverridesByUrl[modelUrl] ?? {};
  return {
    targetSize,
    centerX: true,
    centerY: false,
    centerZ: true,
    alignFloorY: true,
    scaleMode: "per-axis",
    ...override,
  };
}

export function buildThumbnailNormalizeOptions(
  modelUrl: string,
  targetSize: [number, number, number] = [0.9, 0.9, 0.9],
): NormalizeGltfOptions {
  const override = gltfAssetOverridesByUrl[modelUrl] ?? {};
  return {
    targetSize,
    centerX: true,
    centerY: true,
    centerZ: true,
    alignFloorY: false,
    scaleMode: "uniform-contain",
    ...override,
  };
}
