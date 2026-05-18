export interface SceneObject {
  id: string;
  /** Display name from catalog (e.g. "Bunk Bed"). Falls back to type if absent. */
  name?: string;
  /** When set to `door`, enables wall cutouts + 2D plan swing symbol (also inferred from known door model URLs). */
  objectRole?: string;
  type: "model";
  position: [number, number, number];
  rotation?: [number, number, number, number]; // quaternion [x, y, z, w]
  color: string;
  size: [number, number, number];
  /** URL to a .glb model file — only set for type === 'model' */
  modelUrl?: string;
  /** Placement type for snapping (floor/wall/ceiling). Undefined for legacy objects. */
  placementType?: "floor" | "wall" | "ceiling";
  /** ID of the wall segment this object is snapped to. */
  snappedToWall?: string;
  /** UUID of the catalog item this object was instantiated from. */
  catalogItemId?: string;
  /** Backend collision/display layer for generated placement results. */
  collisionLayer?:
    | "floor_solid"
    | "floor_underlay"
    | "surface_child"
    | "wall_mounted"
    | "ceiling";
  /** Backend placement relationship for objects attached to another object. */
  placeOn?: {
    target_instance_id: string;
    method: "on_top" | "hang_on" | "lean_on" | "floor";
  } | null;
  /** Active color hex set via SelectedObjectOverlay (e.g. "#c8a87e"). Written by setObjectDisplayOptions. */
  selectedColorHex?: string;
  /** Display name of active color (e.g. "Gỗ sồi"). Written by setObjectDisplayOptions. */
  selectedColorName?: string;
  /** Display name of active material (e.g. "Gỗ tự nhiên"). Written by setObjectDisplayOptions. */
  selectedMaterialName?: string;
  /** Resolved variant price in cents for the active options combo. Written by setObjectDisplayOptions. */
  variantPriceCents?: number;
}

export type ObjectsSliceType = {
  objects: SceneObject[];
};
