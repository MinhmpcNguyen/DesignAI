/**
 * Furniture Placement Metadata
 *
 * Defines placement rules for each furniture type.
 * This is a performance-optimized lookup table using a frozen object
 * to enable V8 optimizations.
 */

import type { FurnitureMetadata } from "./types";

/**
 * Furniture metadata lookup table
 *
 * Performance notes:
 * - Frozen object for V8 optimization (monomorphic property access)
 * - O(1) lookup time
 * - Immutable to prevent runtime modifications
 */
export const FURNITURE_METADATA: Readonly<Record<string, FurnitureMetadata>> =
  Object.freeze({
    // Floor-placed furniture

    // Generic GLB model (floor-placed by default; catalog overrides per-item via placementType)
    model: {
      placement: "floor",
    },

    // Wall-mounted furniture
    picture: {
      placement: "wall",
      wallMountHeight: 1.5, // Eye level
      wallOffset: 0.02, // 2cm from wall to prevent z-fighting
    },
    tv: {
      placement: "wall",
      wallMountHeight: 1.2, // Seated eye level
      wallOffset: 0.05, // 5cm from wall (TV has depth)
    },
    shelf: {
      placement: "wall",
      wallMountHeight: 1.8, // Above head height
      wallOffset: 0.03, // 3cm from wall
    },
    door: {
      placement: "wall",
      wallMountHeight: 0, // Door starts at floor
      wallOffset: 0.01, // Minimal offset
    },
    window: {
      placement: "wall",
      wallMountHeight: 0.9, // Typical window sill height
      wallOffset: 0.01, // Minimal offset
    },
    // Ceiling-mounted items
    ceiling_light: {
      placement: "ceiling",
    },
    hanger_ceil_light: {
      placement: "ceiling",
    },
  } as const);

/**
 * Get metadata for a furniture type
 *
 * @param type - Furniture type identifier
 * @returns Metadata or undefined if not found
 *
 * Performance: O(1) lookup with monomorphic inline cache
 */
export function getFurnitureMetadata(
  type: string,
): FurnitureMetadata | undefined {
  return FURNITURE_METADATA[type];
}

/**
 * Check if a furniture type can be placed on floor
 */
export function isFloorPlacement(type: string): boolean {
  return FURNITURE_METADATA[type]?.placement === "floor";
}

/**
 * Check if a furniture type can be placed on wall
 */
export function isWallPlacement(type: string): boolean {
  return FURNITURE_METADATA[type]?.placement === "wall";
}

/**
 * Check if a furniture type can be placed on ceiling
 */
export function isCeilingPlacement(type: string): boolean {
  return FURNITURE_METADATA[type]?.placement === "ceiling";
}
