/**
 * Snapping System Types
 *
 * Defines placement types, furniture metadata, and snap calculation results
 * for the floor/wall snapping system.
 */

export type PlacementType = "floor" | "wall" | "ceiling";

/** Wall identifier — either a cardinal name (legacy) or a wall segment ID */
export type WallType = string;

/**
 * Furniture metadata defining how each object type can be placed
 */
export interface FurnitureMetadata {
  /** Where this furniture can be placed */
  placement: PlacementType;
  /** Default height for wall-mounted items (in meters) */
  wallMountHeight?: number;
  /** Offset from wall surface (in meters) to prevent z-fighting */
  wallOffset?: number;
}

/**
 * Result of snap calculation with position, rotation, and snap target info
 */
export interface SnapResult {
  /** Final snapped position [x, y, z] */
  position: [number, number, number];
  /** Rotation as quaternion [x, y, z, w] for wall orientation */
  rotation?: [number, number, number, number];
  /** What surface the object snapped to */
  snappedTo: "floor" | "wall" | "ceiling" | null;
  /** Which wall (if snapped to wall) */
  wallType?: WallType;
  /** Distance to snap target (for visual feedback) */
  distance?: number;
}

/**
 * Room dimensions for snap calculations
 */
export interface RoomDimensions {
  width: number;
  depth: number;
  height?: number;
}

/**
 * Configuration for snap behavior
 */
export interface SnappingConfig {
  /** Distance threshold for snapping (in meters) */
  snapThreshold: number;
  /** Show visual snap indicators during drag */
  showIndicators: boolean;
  /** Enable floor snapping */
  enableFloorSnap: boolean;
  /** Enable wall snapping */
  enableWallSnap: boolean;
  /** Enable ceiling snapping */
  enableCeilingSnap: boolean;
}
