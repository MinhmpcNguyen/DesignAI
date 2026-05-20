import type { AutoFillDebugSplitWall, AutoFillDebugZone } from "@/types/api";

export interface FloorSliceType {
  /** Material id applied to all rooms unless overridden */
  globalMaterialId: string;
  /** Per-room material overrides keyed by centroid key (e.g. "5.0:3.0") */
  roomMaterials: Record<string, string>;
  /** User-assigned room names keyed by centroid key */
  roomNames: Record<string, string>;
  /** User-assigned room descriptions keyed by centroid key */
  roomDescriptions: Record<string, string>;
  /** Temporary normalize-run split walls keyed by room centroid key */
  debugSplitWalls: Record<string, AutoFillDebugSplitWall>;
  /** Temporary normalize-run split zones keyed by room centroid key */
  debugSplitZones: Record<string, AutoFillDebugZone[]>;
  /** Centroid key of the currently-selected room polygon, or null */
  selectedRoomKey: string | null;
}
