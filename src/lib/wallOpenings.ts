import type { Wall } from "@/states/slices/walls/types";
import type { SceneObject } from "@/states/slices/objects/types";
import { isWallDoorSceneObject } from "./doorModels";

/** One merged door/window interval along the wall, in wall-local X (origin at wall center, S at -L/2). */
export type WallOpeningInterval = {
  localXStart: number;
  localXEnd: number;
  /** World-space bottom of the opening (0 for doors, sill height for windows). */
  bottomY: number;
  /** World-space top of the opening (capped by wall height). */
  doorHeight: number;
};

export type WallSubMesh = {
  /** Local position (wall group space: X along wall, Y vertical from wall mid-height, Z through thickness). */
  position: [number, number, number];
  size: [number, number, number];
};

function mergeIntervals(
  raw: { fromS: number; toS: number; bottomY: number; doorHeight: number }[],
): { fromS: number; toS: number; bottomY: number; doorHeight: number }[] {
  if (raw.length === 0) return [];
  const sorted = [...raw].sort((a, b) => a.fromS - b.fromS);
  const out: {
    fromS: number;
    toS: number;
    bottomY: number;
    doorHeight: number;
  }[] = [];
  let cur = { ...sorted[0] };
  for (let i = 1; i < sorted.length; i++) {
    const n = sorted[i];
    if (n.fromS <= cur.toS) {
      cur.toS = Math.max(cur.toS, n.toS);
      cur.bottomY = Math.min(cur.bottomY, n.bottomY);
      cur.doorHeight = Math.max(cur.doorHeight, n.doorHeight);
    } else {
      out.push(cur);
      cur = { ...n };
    }
  }
  out.push(cur);
  return out;
}

/**
 * Collect door/window openings on a wall from scene objects (distance along wall from startPoint).
 */
export function collectDoorIntervalsFromS(
  wall: Wall,
  objects: SceneObject[],
): { fromS: number; toS: number; bottomY: number; doorHeight: number }[] {
  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const dx = ex - sx;
  const dz = ez - sz;
  const L = Math.hypot(dx, dz);
  if (L < 1e-6) return [];

  const dirX = dx / L;
  const dirZ = dz / L;

  const raw: {
    fromS: number;
    toS: number;
    bottomY: number;
    doorHeight: number;
  }[] = [];

  for (const obj of objects) {
    if (!isWallDoorSceneObject(obj) || obj.snappedToWall !== wall.id) continue;
    const [px, py, pz] = obj.position;
    const t = Math.max(0, Math.min(L, (px - sx) * dirX + (pz - sz) * dirZ));
    const w = obj.size[0];
    const half = w / 2;
    let fromS = t - half;
    let toS = t + half;
    fromS = Math.max(0, fromS);
    toS = Math.min(L, toS);
    if (toS <= fromS) continue;

    // bottomY: bottom edge of the object in world Y (center Y minus half height)
    const bottomY = Math.max(0, py - obj.size[1] / 2);
    const topY = Math.min(py + obj.size[1] / 2, wall.height);
    if (topY <= bottomY) continue;

    raw.push({ fromS, toS, bottomY, doorHeight: topY });
  }

  return mergeIntervals(raw);
}

export function intervalsToLocalX(
  intervals: {
    fromS: number;
    toS: number;
    bottomY: number;
    doorHeight: number;
  }[],
  wallLength: number,
): WallOpeningInterval[] {
  const half = wallLength / 2;
  return intervals.map((it) => ({
    localXStart: it.fromS - half,
    localXEnd: it.toS - half,
    bottomY: it.bottomY,
    doorHeight: it.doorHeight,
  }));
}

/**
 * Build wall sub-meshes: piers (full height), lintels above openings, and sills below openings.
 *
 * Coordinate system: wall group is centred at (wallMidX, wallHeight/2, wallMidZ) in world space.
 * Local Y=0 is the vertical centre of the wall, so:
 *   localY = worldY - wallHeight/2
 * e.g. a sill at worldY=0.9 → localY = 0.9 - wallHeight/2
 */
export function buildWallSubMeshes(
  wallLength: number,
  wallHeight: number,
  wallThickness: number,
  openings: WallOpeningInterval[],
): WallSubMesh[] {
  const L = wallLength;
  const H = wallHeight;
  const T = wallThickness;
  const halfH = H / 2; // offset: world Y → local Y
  const meshes: WallSubMesh[] = [];

  if (openings.length === 0) {
    meshes.push({
      position: [0, 0, 0],
      size: [L, H, T],
    });
    return meshes;
  }

  const sorted = [...openings].sort((a, b) => a.localXStart - b.localXStart);
  let cursor = -L / 2;

  for (const op of sorted) {
    const a = Math.max(-L / 2, op.localXStart);
    const b = Math.min(L / 2, op.localXEnd);
    if (b <= a) continue;

    // --- Pier to the left of this opening ---
    if (a > cursor + 1e-6) {
      const width = a - cursor;
      meshes.push({
        position: [(cursor + a) / 2, 0, 0],
        size: [width, H, T],
      });
    }

    const bottomY = Math.max(0, op.bottomY); // world Y of opening bottom
    const topY = Math.min(op.doorHeight, H); // world Y of opening top

    // --- Sill below the opening (only for windows / raised-bottom openings) ---
    if (bottomY > 1e-6) {
      const sillH = bottomY; // world height of sill
      const sillCenterLocalY = bottomY / 2 - halfH; // local Y of sill centre
      meshes.push({
        position: [(a + b) / 2, sillCenterLocalY, 0],
        size: [b - a, sillH, T],
      });
    }

    // --- Lintel above the opening ---
    if (topY < H - 1e-6) {
      const lintelH = H - topY;
      const lintelCenterLocalY = topY + lintelH / 2 - halfH;
      meshes.push({
        position: [(a + b) / 2, lintelCenterLocalY, 0],
        size: [b - a, lintelH, T],
      });
    }

    cursor = b;
  }

  // --- Pier to the right of the last opening ---
  if (cursor < L / 2 - 1e-6) {
    const width = L / 2 - cursor;
    meshes.push({
      position: [(cursor + L / 2) / 2, 0, 0],
      size: [width, H, T],
    });
  }

  return meshes;
}
