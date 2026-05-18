/**
 * Wall System Types
 *
 * Defines wall data structures for the room editor.
 * Walls use 2D coordinates [x, z] since they extend vertically (Y axis).
 */

/**
 * A single wall segment defined by start and end points
 */
export interface Wall {
  /** Unique identifier for the wall */
  id: string;
  /** Start point [x, z] in 3D space (Y is height) */
  startPoint: [number, number];
  /** End point [x, z] in 3D space (Y is height) */
  endPoint: [number, number];
  /** Wall thickness in meters (default: 0.5m) */
  thickness: number;
  /** Wall height in meters (default: 3m) */
  height: number;
  /** Wall color as hex string */
  color: string;
}

/**
 * Walls slice state type
 */
export interface WallsSliceType {
  walls: Wall[];
  history: { ts: number; walls: Wall[] }[];
  future: { ts: number; walls: Wall[] }[];
}
