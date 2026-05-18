import type { Wall } from "@/states/slices/walls/types";
import type { CameraAnglePreset } from "@/types/global";
import { centroidKey, findRoomPolygons } from "./roomPolygons";

const CAMERA_HEIGHT = 1.6; // metres — eye level
const CAMERA_ELEVATION = 15; // degrees — slight downward tilt
const CAMERA_FOV = 65; // degrees — within 60–70 spec
const DIST_MULTIPLIER = 1.1; // scale factor applied to max(roomW, roomH)

interface AngleDef {
  id: string;
  label: string;
  /** Offset from room center in XZ — normalised unit vector × dist */
  ox: (dist: number) => number;
  oz: (dist: number) => number;
  azimuth: number;
}

const ANGLE_DEFS: AngleDef[] = [
  { id: "front", label: "Phía trước", ox: () => 0, oz: (d) => -d, azimuth: 0 },
  {
    id: "back",
    label: "Phía sau",
    ox: () => 0,
    oz: (d) => d,
    azimuth: Math.PI,
  },
  {
    id: "left",
    label: "Bên trái",
    ox: (d) => -d,
    oz: () => 0,
    azimuth: -Math.PI / 2,
  },
  {
    id: "right",
    label: "Bên phải",
    ox: (d) => d,
    oz: () => 0,
    azimuth: Math.PI / 2,
  },
  {
    id: "ne",
    label: "Góc Đông-Bắc",
    ox: (d) => d / Math.SQRT2,
    oz: (d) => -d / Math.SQRT2,
    azimuth: Math.PI / 4,
  },
  {
    id: "sw",
    label: "Góc Tây-Nam",
    ox: (d) => -d / Math.SQRT2,
    oz: (d) => d / Math.SQRT2,
    azimuth: -3 * (Math.PI / 4),
  },
];

/**
 * Compute 6 preset camera angles around a room.
 *
 * If `selectedRoomKey` matches a room polygon centroid key, that room's
 * bounding box is used. Otherwise falls back to the bounding box of all
 * wall endpoints.
 */
export function computeRoomCameraAngles(
  walls: Wall[],
  selectedRoomKey: string | null,
): CameraAnglePreset[] {
  // ── Determine bounding box ───────────────────────────────────────────
  let minX: number, maxX: number, minZ: number, maxZ: number;

  const polygons = findRoomPolygons(walls);
  const matchedPolygon = selectedRoomKey
    ? polygons.find((p) => centroidKey(p) === selectedRoomKey)
    : undefined;

  if (matchedPolygon) {
    const xs = matchedPolygon.map((p) => p[0]);
    const zs = matchedPolygon.map((p) => p[1]);
    minX = Math.min(...xs);
    maxX = Math.max(...xs);
    minZ = Math.min(...zs);
    maxZ = Math.max(...zs);
  } else {
    // Fallback: all wall endpoints
    const xs = walls.flatMap((w) => [w.startPoint[0], w.endPoint[0]]);
    const zs = walls.flatMap((w) => [w.startPoint[1], w.endPoint[1]]);
    if (xs.length === 0) {
      // No walls at all — use a small default area
      minX = -3;
      maxX = 3;
      minZ = -3;
      maxZ = 3;
    } else {
      minX = Math.min(...xs);
      maxX = Math.max(...xs);
      minZ = Math.min(...zs);
      maxZ = Math.max(...zs);
    }
  }

  // ── Compute center and viewing distance ─────────────────────────────
  const centerX = (minX + maxX) / 2;
  const centerZ = (minZ + maxZ) / 2;
  const roomW = maxX - minX || 1;
  const roomH = maxZ - minZ || 1;
  const dist = Math.max(roomW, roomH) * DIST_MULTIPLIER;

  // ── Build presets ────────────────────────────────────────────────────
  return ANGLE_DEFS.map((def) => ({
    id: def.id,
    label: def.label,
    x: centerX + def.ox(dist),
    z: centerZ + def.oz(dist),
    y: CAMERA_HEIGHT,
    azimuth: def.azimuth,
    elevation: CAMERA_ELEVATION,
    fov: CAMERA_FOV,
    selected: false,
  }));
}
