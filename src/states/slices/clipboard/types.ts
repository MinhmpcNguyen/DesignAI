import { SceneObject } from "../objects/types";

export interface ClipboardSliceType {
  copiedObjects: SceneObject[]; // Changed to array for multi-copy
  isPasting: boolean;
}
