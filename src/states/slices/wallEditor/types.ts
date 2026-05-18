/**
 * Wall Editor Types
 *
 * Defines state for wall editing mode, selection, and interaction
 */

/**
 * Edit mode - controls what the user can interact with
 * - "objects": Normal mode - place and edit furniture objects
 * - "walls": Wall editing mode - select, move, and modify walls
 */
export type EditMode = "objects" | "walls";

/**
 * Wall editor state
 */
export interface WallEditorSliceType {
  /** Current editing mode (only "walls" mode works in 2D) */
  editMode: EditMode;
  /** ID of currently selected wall (null if none selected) */
  selectedWallId: string | null;
  /** IDs of walls being dragged/edited */
  draggingWallEndpoint: { wallId: string; endpoint: "start" | "end" } | null;
  draggingWallMidpoint: string | null;
  /** Wall drawing state - tracks drawing in progress */
  isDrawing: boolean;
  /** First point of wall being drawn (null if not drawing) */
  drawingStartPoint: [number, number] | null;
  /** Default properties applied to every newly drawn wall */
  defaultWallHeight: number;
  defaultWallThickness: number;
}
