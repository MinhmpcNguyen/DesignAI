import type { Wall } from "@/states/slices/walls/types";
import {
  BufferGeometry,
  Float32BufferAttribute,
  Quaternion,
  Vector3,
} from "three";

export const DOOR_PLAN_Y_FILL = 0.09;
export const DOOR_PLAN_Y_LINE = 0.14;
export const DOOR_PLAN_ARC_SEGMENTS = 16;

/**
 * Plan-view swing arc + open leaf for a door on a wall (world XZ, constant Y).
 */
export function computeDoorSwingPlanGeometry(
  wall: Wall,
  doorPosition: [number, number, number],
  doorRotation: [number, number, number, number] | undefined,
  doorSize: [number, number, number],
  lineY: number = DOOR_PLAN_Y_LINE,
): {
  arcPts: Vector3[];
  leafPts: Vector3[];
  hingeX: number;
  hingeZ: number;
} | null {
  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const dx = ex - sx;
  const dz = ez - sz;
  const L = Math.hypot(dx, dz);
  if (L < 1e-6) return null;

  const dirX = dx / L;
  const dirZ = dz / L;
  const [px, , pz] = doorPosition;
  const t = Math.max(0, Math.min(L, (px - sx) * dirX + (pz - sz) * dirZ));
  const w = doorSize[0];
  const half = w / 2;
  const fromS = Math.max(0, t - half);
  const toS = Math.min(L, t + half);
  if (toS <= fromS) return null;

  const R = toS - fromS;
  const hingeX = sx + dirX * fromS;
  const hingeZ = sz + dirZ * fromS;

  const D = new Vector3(dirX, 0, dirZ).normalize();
  const up = new Vector3(0, 1, 0);
  const swing = new Vector3().crossVectors(up, D).normalize();
  const q = new Quaternion(
    doorRotation?.[0] ?? 0,
    doorRotation?.[1] ?? 0,
    doorRotation?.[2] ?? 0,
    doorRotation?.[3] ?? 1,
  );
  const doorFwd = new Vector3(0, 0, 1).applyQuaternion(q);
  doorFwd.y = 0;
  if (doorFwd.lengthSq() < 1e-8) doorFwd.set(dirX, 0, dirZ);
  else doorFwd.normalize();

  if (swing.dot(doorFwd) < 0) swing.multiplyScalar(-1);

  const start = D.clone().normalize();
  const arcPts: Vector3[] = [];
  for (let i = 0; i <= DOOR_PLAN_ARC_SEGMENTS; i++) {
    const u = i / DOOR_PLAN_ARC_SEGMENTS;
    const a = (Math.PI / 2) * u;
    const c = Math.cos(a);
    const s = Math.sin(a);
    const dir = start
      .clone()
      .multiplyScalar(c)
      .add(swing.clone().multiplyScalar(s));
    arcPts.push(new Vector3(hingeX + dir.x * R, lineY, hingeZ + dir.z * R));
  }

  const openEnd = swing.clone().multiplyScalar(R);
  const leafPts = [
    new Vector3(hingeX, lineY, hingeZ),
    new Vector3(hingeX + openEnd.x, lineY, hingeZ + openEnd.z),
  ];

  return { arcPts, leafPts, hingeX, hingeZ };
}

/**
 * Plan-view window symbol: two parallel lines spanning the opening width,
 * offset by ±half the wall thickness in the wall-perpendicular direction.
 */
export function computeWindowPlanGeometry(
  wall: Wall,
  windowPosition: [number, number, number],
  windowSize: [number, number, number],
  lineY: number = DOOR_PLAN_Y_LINE,
): {
  outerLine: Vector3[];
  innerLine: Vector3[];
  corners: [Vector3, Vector3, Vector3, Vector3]; // fill quad corners
} | null {
  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const dx = ex - sx;
  const dz = ez - sz;
  const L = Math.hypot(dx, dz);
  if (L < 1e-6) return null;

  const dirX = dx / L;
  const dirZ = dz / L;
  // Wall-perpendicular (rotated 90° CCW in XZ plane)
  const perpX = -dirZ;
  const perpZ = dirX;

  const [px, , pz] = windowPosition;
  const t = Math.max(0, Math.min(L, (px - sx) * dirX + (pz - sz) * dirZ));
  const w = windowSize[0];
  const half = w / 2;
  const fromS = Math.max(0, t - half);
  const toS = Math.min(L, t + half);
  if (toS <= fromS) return null;

  const startX = sx + dirX * fromS;
  const startZ = sz + dirZ * fromS;
  const endX = sx + dirX * toS;
  const endZ = sz + dirZ * toS;

  // Offset lines by ±(wallThickness * 0.35) from centre — keeps the two
  // glass lines clearly separated but inside the wall gap.
  const offset = (wall.thickness ?? 0.5) * 0.35;

  const outerLine: Vector3[] = [
    new Vector3(startX + perpX * offset, lineY, startZ + perpZ * offset),
    new Vector3(endX + perpX * offset, lineY, endZ + perpZ * offset),
  ];
  const innerLine: Vector3[] = [
    new Vector3(startX - perpX * offset, lineY, startZ - perpZ * offset),
    new Vector3(endX - perpX * offset, lineY, endZ - perpZ * offset),
  ];

  // Fill quad (white rectangle between the two lines)
  const corners: [Vector3, Vector3, Vector3, Vector3] = [
    outerLine[0].clone().setY(DOOR_PLAN_Y_FILL),
    outerLine[1].clone().setY(DOOR_PLAN_Y_FILL),
    innerLine[1].clone().setY(DOOR_PLAN_Y_FILL),
    innerLine[0].clone().setY(DOOR_PLAN_Y_FILL),
  ];

  return { outerLine, innerLine, corners };
}

export function buildWindowPlanFillGeometry(
  corners: [Vector3, Vector3, Vector3, Vector3],
): BufferGeometry {
  const g = new BufferGeometry();
  // Two triangles: (0,1,2) and (0,2,3)
  const pos = new Float32Array([
    corners[0].x,
    corners[0].y,
    corners[0].z,
    corners[1].x,
    corners[1].y,
    corners[1].z,
    corners[2].x,
    corners[2].y,
    corners[2].z,
    corners[3].x,
    corners[3].y,
    corners[3].z,
  ]);
  g.setAttribute("position", new Float32BufferAttribute(pos, 3));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  g.computeVertexNormals();
  return g;
}

export function buildDoorSwingFillGeometry(
  hingeX: number,
  hingeZ: number,
  arcPts: Vector3[],
  fillY: number = DOOR_PLAN_Y_FILL,
): BufferGeometry {
  const g = new BufferGeometry();
  const nArc = arcPts.length;
  const pos = new Float32Array(3 * (1 + nArc));
  pos[0] = hingeX;
  pos[1] = fillY;
  pos[2] = hingeZ;
  for (let i = 0; i < nArc; i++) {
    pos[3 + 3 * i] = arcPts[i].x;
    pos[4 + 3 * i] = fillY;
    pos[5 + 3 * i] = arcPts[i].z;
  }
  const indices: number[] = [];
  for (let i = 1; i < nArc; i++) {
    indices.push(0, i, i + 1);
  }
  g.setAttribute("position", new Float32BufferAttribute(pos, 3));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}
