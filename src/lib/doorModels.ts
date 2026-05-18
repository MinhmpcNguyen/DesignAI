import type { SceneObject } from "@/states/slices/objects/types";

/** Snap / metadata should use the `door` or `window` entry in FURNITURE_METADATA. */
export function getSnapFurnitureType(
  shape: SceneObject["type"],
  objectRole?: SceneObject["objectRole"],
): string {
  if (objectRole === "door") return "door";
  if (objectRole === "window") return "window";
  return shape;
}

/**
 * Returns true for any wall-snapped object that creates a wall opening
 * (both doors and windows cut openings through walls).
 */
export function isWallDoorSceneObject(obj: SceneObject): boolean {
  if (obj.placementType !== "wall" || obj.snappedToWall == null) return false;
  return obj.objectRole === "door" || obj.objectRole === "window";
}
