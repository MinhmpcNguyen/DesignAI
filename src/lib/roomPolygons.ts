import type { Wall } from "@/states/slices/walls/types";

const EPSILON = 0.05;

function ptKey(x: number, z: number): string {
  return `${Math.round(x / EPSILON)},${Math.round(z / EPSILON)}`;
}

interface GraphNode {
  x: number;
  z: number;
  neighbors: Set<string>;
}

function buildGraph(walls: Wall[]): Map<string, GraphNode> {
  const graph = new Map<string, GraphNode>();
  const getOrCreate = (x: number, z: number): string => {
    const k = ptKey(x, z);
    if (!graph.has(k)) graph.set(k, { x, z, neighbors: new Set() });
    return k;
  };
  for (const wall of walls) {
    const sk = getOrCreate(wall.startPoint[0], wall.startPoint[1]);
    const ek = getOrCreate(wall.endPoint[0], wall.endPoint[1]);
    if (sk !== ek) {
      graph.get(sk)!.neighbors.add(ek);
      graph.get(ek)!.neighbors.add(sk);
    }
  }
  return graph;
}

/**
 * Finds all interior room polygons using the planar half-edge "always turn
 * most clockwise" algorithm.
 *
 * Unlike the old simple-loop algorithm, this correctly handles T-junctions,
 * multi-room layouts, and any connected wall topology. Two rooms sharing a
 * dividing wall both receive floors.
 *
 * Algorithm:
 *   1. Build an undirected adjacency graph from wall endpoints.
 *   2. Pre-sort each node's neighbors in CCW angle order.
 *   3. For each unused directed edge (u→v), trace a face by always taking the
 *      most clockwise (previous in CCW list) outgoing edge at each vertex.
 *   4. Keep only faces whose signed area is positive (interior faces).
 *      The outer unbounded face always has negative signed area and is
 *      discarded automatically.
 */
export function findRoomPolygons(walls: Wall[]): [number, number][][] {
  if (walls.length < 3) return [];
  const graph = buildGraph(walls);
  if (graph.size < 3) return [];

  // Pre-sort each node's neighbors CCW by angle from the +x axis.
  const sortedNeighbors = new Map<string, string[]>();
  for (const [k, node] of graph.entries()) {
    const sorted = [...node.neighbors].sort(
      (a, b) =>
        Math.atan2(graph.get(a)!.z - node.z, graph.get(a)!.x - node.x) -
        Math.atan2(graph.get(b)!.z - node.z, graph.get(b)!.x - node.x),
    );
    sortedNeighbors.set(k, sorted);
  }

  const usedEdges = new Set<string>();
  const polygons: [number, number][][] = [];
  const maxSteps = graph.size * 2 + 4;

  for (const startKey of graph.keys()) {
    for (const firstTo of sortedNeighbors.get(startKey)!) {
      if (usedEdges.has(`${startKey}>${firstTo}`)) continue;

      const face: [number, number][] = [];
      let curFrom = startKey;
      let curTo = firstTo;
      let steps = 0;

      while (steps < maxSteps) {
        const edgeKey = `${curFrom}>${curTo}`;
        if (usedEdges.has(edgeKey)) break;
        usedEdges.add(edgeKey);

        const toNode = graph.get(curTo)!;
        face.push([toNode.x, toNode.z]);

        // At curTo, pick the neighbor immediately clockwise from the back
        // direction (curTo→curFrom). In the CCW-sorted list, "previous index"
        // is the most clockwise next step.
        const neighbors = sortedNeighbors.get(curTo)!;
        const fromIdx = neighbors.indexOf(curFrom);
        const nextTo =
          neighbors[(fromIdx - 1 + neighbors.length) % neighbors.length];

        curFrom = curTo;
        curTo = nextTo;
        steps++;
      }

      if (face.length < 3) continue;

      // Compute signed area (shoelace formula).
      // Positive → CCW winding → interior face. Negative → outer face → discard.
      let area = 0;
      for (let i = 0; i < face.length; i++) {
        const [x0, z0] = face[i];
        const [x1, z1] = face[(i + 1) % face.length];
        area += x0 * z1 - x1 * z0;
      }
      if (area > 0) polygons.push(face);
    }
  }

  return polygons;
}

/** Compute the centroid [cx, cz] of a polygon using the shoelace formula. */
export function polygonCentroid(polygon: [number, number][]): [number, number] {
  let cx = 0,
    cz = 0,
    area = 0;
  for (let i = 0; i < polygon.length; i++) {
    const [x0, z0] = polygon[i];
    const [x1, z1] = polygon[(i + 1) % polygon.length];
    const cross = x0 * z1 - x1 * z0;
    area += cross;
    cx += (x0 + x1) * cross;
    cz += (z0 + z1) * cross;
  }
  area /= 2;
  if (Math.abs(area) < 1e-9) {
    // Degenerate polygon — fall back to arithmetic mean
    cx = polygon.reduce((s, p) => s + p[0], 0) / polygon.length;
    cz = polygon.reduce((s, p) => s + p[1], 0) / polygon.length;
    return [cx, cz];
  }
  cx /= 6 * area;
  cz /= 6 * area;
  return [cx, cz];
}

/**
 * Stable string key for a polygon based on its centroid snapped to a 0.5 m grid.
 * Used to key per-room floor material overrides in the floor Redux slice.
 */
export function centroidKey(polygon: [number, number][]): string {
  const [cx, cz] = polygonCentroid(polygon);
  return `${Math.round(cx * 2) / 2}:${Math.round(cz * 2) / 2}`;
}

/**
 * Ray-casting point-in-polygon test.
 * Returns true if (px, pz) is inside the given XZ polygon.
 */
export function isPointInPolygon(
  px: number,
  pz: number,
  polygon: [number, number][],
): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, zi] = polygon[i];
    const [xj, zj] = polygon[j];
    const intersect =
      zi > pz !== zj > pz && px < ((xj - xi) * (pz - zi)) / (zj - zi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** Sum of areas of all detected interior rooms, or null if none are closed. */
export function computeTotalFloorArea(walls: Wall[]): number | null {
  const polygons = findRoomPolygons(walls);
  if (polygons.length === 0) return null;

  let total = 0;
  for (const poly of polygons) {
    let area = 0;
    for (let i = 0; i < poly.length; i++) {
      const [x0, z0] = poly[i];
      const [x1, z1] = poly[(i + 1) % poly.length];
      area += x0 * z1 - x1 * z0;
    }
    total += area / 2;
  }
  return total > 0 ? total : null;
}
