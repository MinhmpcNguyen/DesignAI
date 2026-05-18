/**
 * Snapping System - Public API
 *
 * Barrel export for clean imports across the application.
 */

// Types
export type {
  PlacementType,
  WallType,
  FurnitureMetadata,
  SnapResult,
  RoomDimensions,
  SnappingConfig,
} from "./types";

// Metadata
export {
  FURNITURE_METADATA,
  getFurnitureMetadata,
  isFloorPlacement,
  isWallPlacement,
  isCeilingPlacement,
} from "./metadata";

// Redux state API (optional exports)
export { snappingActions, snappingSelectors } from "./state";

// Utilities
export { calculateSnap, canSnap, getSnapDistance } from "./utils";

// Hooks
export {
  useSnapThreshold,
  useShowSnapIndicators,
  useRoomDimensions,
  useWallThickness,
  useSnappingConfig,
  useUpdateSnapThreshold,
  useUpdateRoomDimensions,
  useCalculateSnap,
  useCanSnap,
  useGetSnapDistance,
} from "./hooks";
