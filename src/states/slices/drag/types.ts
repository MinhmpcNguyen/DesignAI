import type { SceneObject } from "@/states/slices/objects/types";

export type DraggingShape = {
  shape: "model";
  /** Mirrors SceneObject.objectRole for doors from catalog. */
  objectRole?: string;
  /** Display name from catalog (e.g. "Bunk Bed"). */
  name?: string;
  color: string;
  size: [number, number, number];
  /** URL to a .glb model file — only set when shape === 'model' */
  modelUrl?: string;
  /** Per-catalog-item placement override (overrides shape-level metadata for 'model' types) */
  placementType?: "floor" | "wall" | "ceiling";
  /** UUID of the catalog item being dragged — copied to SceneObject on drop. */
  catalogItemId?: string;
  /** UUID of the collection being dragged. When set, this is a collection drop. */
  collectionId?: string;
  /**
   * All scene objects belonging to a dragged collection.
   * When set, dropping replaces all scene objects with these (offset to drop position).
   */
  collectionObjects?: SceneObject[];
};

export interface DragSliceType {
  isDragging: boolean;
  draggingShape: DraggingShape | null;
}
