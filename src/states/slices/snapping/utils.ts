/**
 * Snapping Calculation Utilities
 *
 * High-performance snap calculation functions for floor and wall placement.
 * Wall snapping works against actual Wall segments from the walls Redux slice,
 * supporting both axis-aligned and diagonal walls of any length.
 */

import { Quaternion, Euler } from "three";
import type { SnapResult } from "./types";
import type { Wall } from "@/states/slices/walls/types";
import { getFurnitureMetadata } from "./metadata";

/**
 * Internal result from findNearestWallSegment.
 * Carries geometry needed to compute final snap position + rotation.
 */
interface WallSnapCandidate {
  /** ID of the matched wall */
  wallId: string;
  /** Closest point on the wall centerline segment [x, z] */
  closestPointX: number;
  closestPointZ: number;
  /** Unit normal from wall toward object [nx, nz] */
  normalX: number;
  normalZ: number;
  /** Per-wall thickness */
  thickness: number;
  /** Distance from object to wall surface (0 when inside wall) */
  surfaceDistance: number;
  /** Y-axis rotation (radians) so object's +Z front faces the normal */
  rotationY: number;
}

/**
 * Find the nearest wall segment to a 3D position.
 *
 * Works on arbitrary Wall segments (any angle, any length).
 * Distance is measured from the object position to the nearest wall SURFACE
 * (centerline distance minus half-thickness), matching the old behavior.
 *
 * @returns Closest wall within threshold, or null
 */
function findNearestWallSegment(
  position: [number, number, number],
  walls: Wall[],
  snapThreshold: number,
): WallSnapCandidate | null {
  const [px, , pz] = position;

  let best: WallSnapCandidate | null = null;
  let minDist = snapThreshold;

  for (const wall of walls) {
    const [sx, sz] = wall.startPoint;
    const [ex, ez] = wall.endPoint;

    const dx = ex - sx;
    const dz = ez - sz;
    const len = Math.sqrt(dx * dx + dz * dz);
    if (len < 1e-6) continue; // skip degenerate walls

    const dirX = dx / len;
    const dirZ = dz / len;

    // Parameter of the closest point on the infinite line, clamped to segment [0, len]
    const t = Math.max(0, Math.min(len, (px - sx) * dirX + (pz - sz) * dirZ));

    // Closest point on wall centerline
    const cpX = sx + t * dirX;
    const cpZ = sz + t * dirZ;

    // Vector from closest centerline point to object
    const toObjX = px - cpX;
    const toObjZ = pz - cpZ;
    const perpDist = Math.sqrt(toObjX * toObjX + toObjZ * toObjZ);

    // Surface distance: subtract half-thickness, floor at 0
    const surfaceDist = Math.max(0, perpDist - wall.thickness / 2);
    if (surfaceDist >= minDist) continue;

    // Unit normal from wall toward object (pick wall perpendicular if on centerline)
    let normalX: number;
    let normalZ: number;
    if (perpDist < 1e-6) {
      normalX = -dirZ;
      normalZ = dirX;
    } else {
      normalX = toObjX / perpDist;
      normalZ = toObjZ / perpDist;
    }

    // Rotation: atan2(nx, nz) rotates +Z toward the normal direction (Three.js Y-up)
    const rotationY = Math.atan2(normalX, normalZ);

    minDist = surfaceDist;
    best = {
      wallId: wall.id,
      closestPointX: cpX,
      closestPointZ: cpZ,
      normalX,
      normalZ,
      thickness: wall.thickness,
      surfaceDistance: surfaceDist,
      rotationY,
    };
  }

  return best;
}

/**
 * Calculate snapped position and rotation for a furniture item.
 *
 * @param furnitureType - Shape/type identifier
 * @param position - Current 3D position [x, y, z]
 * @param walls - All wall segments from the walls Redux slice
 * @param snapThreshold - Distance threshold for snapping (meters)
 * @param objectSize - Object bounding box [width, height, depth]
 * @param placementTypeOverride - Per-catalog override for 'model' types
 * @param wallSnapThresholdOverride - When set (e.g. Infinity), nearest wall is always used for wall placement
 */
export function calculateSnap(
  furnitureType: string,
  position: [number, number, number],
  walls: Wall[],
  snapThreshold: number,
  objectSize?: [number, number, number],
  placementTypeOverride?: "floor" | "wall" | "ceiling",
  wallSnapThresholdOverride?: number,
): SnapResult {
  const metadata = getFurnitureMetadata(furnitureType);

  if (!metadata) {
    return { position, snappedTo: null };
  }

  const effectivePlacement = placementTypeOverride ?? metadata.placement;

  // --- Ceiling placement ---
  // Force-snap to ceiling surface; no distance threshold (always snaps).
  // ceilingHeight = max wall height in the scene, falling back to 3 m.
  if (effectivePlacement === "ceiling") {
    const ceilingHeight =
      walls.length > 0 ? Math.max(...walls.map((w) => w.height)) : 3;
    const halfHeight = objectSize ? objectSize[1] / 2 : 0.15;
    return {
      position: [position[0], ceilingHeight - halfHeight, position[2]],
      snappedTo: "ceiling",
      distance: Math.abs(position[1] - (ceilingHeight - halfHeight)),
    };
  }

  // --- Floor placement ---
  if (effectivePlacement === "floor") {
    const halfHeight = objectSize ? objectSize[1] / 2 : 0.75;
    const distance = Math.abs(position[1] - halfHeight);
    if (distance > snapThreshold) {
      return { position, snappedTo: null, distance };
    }
    return {
      position: [position[0], halfHeight, position[2]],
      snappedTo: "floor",
      distance,
    };
  }

  // --- Wall placement ---
  if (effectivePlacement === "wall") {
    const wallTh = wallSnapThresholdOverride ?? snapThreshold;
    const wallSnap = findNearestWallSegment(position, walls, wallTh);
    if (!wallSnap) {
      return { position, snappedTo: null };
    }

    const wallOffset = metadata.wallOffset ?? 0.02;
    // Object depth is the dimension perpendicular to the wall face
    const objectDepth = objectSize ? objectSize[2] : 0.1;

    let objX: number;
    let objZ: number;

    if (furnitureType === "door" || furnitureType === "window") {
      // Doors and windows sit in the wall opening: center on the wall centerline (plan),
      // not on the outer face + half depth like pictures/TVs.
      // Clamp center along wall so full object width stays inside segment bounds.
      let centerX = wallSnap.closestPointX;
      let centerZ = wallSnap.closestPointZ;
      const wall = walls.find((w) => w.id === wallSnap.wallId);
      const openingWidth = objectSize?.[0] ?? 0.9;
      if (wall) {
        const [sx, sz] = wall.startPoint;
        const [ex, ez] = wall.endPoint;
        const dx = ex - sx;
        const dz = ez - sz;
        const len = Math.hypot(dx, dz);
        if (len > 1e-6) {
          const dirX = dx / len;
          const dirZ = dz / len;
          const halfWidth = Math.min(openingWidth / 2, len / 2);
          const rawT =
            (wallSnap.closestPointX - sx) * dirX +
            (wallSnap.closestPointZ - sz) * dirZ;
          const clampedT = Math.max(halfWidth, Math.min(len - halfWidth, rawT));
          centerX = sx + clampedT * dirX;
          centerZ = sz + clampedT * dirZ;
        }
      }
      // Flush-fit: back face of the object rests on the wall outer surface so the
      // model visually fills across the wall thickness from the outside.
      // Centre is pulled back by objectDepth/2 from the face.
      // collectDoorIntervalsFromS uses only the along-wall projection so this
      // perpendicular shift doesn't affect where the opening is cut.
      const surfaceX = centerX + wallSnap.normalX * (wallSnap.thickness / 2);
      const surfaceZ = centerZ + wallSnap.normalZ * (wallSnap.thickness / 2);
      objX = surfaceX + wallSnap.normalX * (wallOffset - objectDepth / 2);
      objZ = surfaceZ + wallSnap.normalZ * (wallOffset - objectDepth / 2);
    } else {
      // Surface point: move from centerline to wall face along normal
      const surfaceX =
        wallSnap.closestPointX + wallSnap.normalX * (wallSnap.thickness / 2);
      const surfaceZ =
        wallSnap.closestPointZ + wallSnap.normalZ * (wallSnap.thickness / 2);

      // Object center: surface + normal * (half object depth + clearance)
      objX = surfaceX + wallSnap.normalX * (objectDepth / 2 + wallOffset);
      objZ = surfaceZ + wallSnap.normalZ * (objectDepth / 2 + wallOffset);
    }

    const snapQuat = new Quaternion().setFromEuler(
      new Euler(0, wallSnap.rotationY, 0),
    );

    // For doors: always floor-anchored (wallMountHeight=0 → center at halfHeight).
    // For windows: preserve dragged Y so users can slide up/down; clamp within wall bounds.
    // For other wall items (picture, TV, shelf): preserve dragged Y.
    let objY: number;
    if (furnitureType === "door") {
      const mountHeight = metadata.wallMountHeight ?? 0;
      const halfHeight = objectSize ? objectSize[1] / 2 : 0.5;
      objY = mountHeight + halfHeight;
    } else if (furnitureType === "window") {
      const halfHeight = objectSize ? objectSize[1] / 2 : 0.5;
      const wall = walls.find((w) => w.id === wallSnap.wallId);
      const wallH = wall?.height ?? 3;
      // Clamp: bottom edge ≥ 0, top edge ≤ wall height
      objY = Math.max(halfHeight, Math.min(wallH - halfHeight, position[1]));
    } else {
      objY = position[1];
    }

    return {
      position: [objX, objY, objZ],
      rotation: [snapQuat.x, snapQuat.y, snapQuat.z, snapQuat.w],
      snappedTo: "wall",
      wallType: wallSnap.wallId,
      distance: wallSnap.surfaceDistance,
    };
  }

  return { position, snappedTo: null };
}

/**
 * Check if a position can snap (used for validation / warnings).
 */
export function canSnap(
  furnitureType: string,
  position: [number, number, number],
  walls: Wall[],
  snapThreshold: number,
): boolean {
  const metadata = getFurnitureMetadata(furnitureType);
  if (!metadata) return false;
  if (metadata.placement === "floor") return true;
  if (metadata.placement === "ceiling") return true;
  if (metadata.placement === "wall") {
    return findNearestWallSegment(position, walls, snapThreshold) !== null;
  }
  return false;
}

/**
 * Get distance to nearest snap target (for visual feedback intensity).
 */
export function getSnapDistance(
  furnitureType: string,
  position: [number, number, number],
  walls: Wall[],
  objectSize?: [number, number, number],
): number {
  const metadata = getFurnitureMetadata(furnitureType);
  if (!metadata) return Infinity;

  if (metadata.placement === "floor") {
    const halfHeight = objectSize ? objectSize[1] / 2 : 0.75;
    return Math.abs(position[1] - halfHeight);
  }

  if (metadata.placement === "ceiling") {
    const ceilingHeight =
      walls.length > 0 ? Math.max(...walls.map((w) => w.height)) : 3;
    const halfHeight = objectSize ? objectSize[1] / 2 : 0.15;
    return Math.abs(position[1] - (ceilingHeight - halfHeight));
  }

  if (metadata.placement === "wall") {
    const wallSnap = findNearestWallSegment(position, walls, Infinity);
    return wallSnap?.surfaceDistance ?? Infinity;
  }

  return Infinity;
}
