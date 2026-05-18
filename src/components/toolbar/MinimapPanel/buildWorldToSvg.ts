import { SVG_SIZE, WALL_PAD } from "./constants";

export interface WorldToSvg {
  toSvg: (wx: number, wz: number) => [number, number];
  toWorld: (sx: number, sy: number) => [number, number];
}

export function buildWorldToSvg(
  walls: { startPoint: [number, number]; endPoint: [number, number] }[],
  extraPoints: [number, number][] = [],
): WorldToSvg {
  // Collect all wall endpoints to find bounding box
  const xs: number[] = [];
  const zs: number[] = [];
  for (const w of walls) {
    xs.push(w.startPoint[0], w.endPoint[0]);
    zs.push(w.startPoint[1], w.endPoint[1]);
  }
  for (const [x, z] of extraPoints) {
    xs.push(x);
    zs.push(z);
  }
  // Fallback when no walls
  if (xs.length === 0) {
    xs.push(-5, 5);
    zs.push(-5, 5);
  }

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);

  const worldW = maxX - minX || 1;
  const worldH = maxZ - minZ || 1;

  // Keep square aspect — use the larger dimension
  const worldSpan = Math.max(worldW, worldH);
  const padWorld = worldSpan * WALL_PAD;

  const originX = (minX + maxX) / 2 - (worldSpan + padWorld * 2) / 2;
  const originZ = (minZ + maxZ) / 2 - (worldSpan + padWorld * 2) / 2;
  const scale = SVG_SIZE / (worldSpan + padWorld * 2);

  return {
    toSvg(wx, wz): [number, number] {
      return [(wx - originX) * scale, (wz - originZ) * scale];
    },
    toWorld(sx, sy): [number, number] {
      return [sx / scale + originX, sy / scale + originZ];
    },
  };
}
