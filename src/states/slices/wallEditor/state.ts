import {
  createSlice,
  createSelector,
  type PayloadAction,
} from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { EditMode, WallEditorSliceType } from "./types";

const initialState: WallEditorSliceType = {
  editMode: "objects", // Default to objects mode
  selectedWallId: null,
  draggingWallEndpoint: null,
  draggingWallMidpoint: null,
  isDrawing: false,
  drawingStartPoint: null,
  defaultWallHeight: 3,
  defaultWallThickness: 0.2,
};

const wallEditorSlice = createSlice({
  name: "wallEditor",
  initialState,
  reducers: {
    /**
     * Set the current edit mode
     */
    setEditMode(state, action: PayloadAction<EditMode>) {
      state.editMode = action.payload;
      // Clear selection when switching modes
      if (action.payload === "objects") {
        state.selectedWallId = null;
        state.draggingWallEndpoint = null;
        state.draggingWallMidpoint = null;
      }
    },
    /**
     * Toggle between objects and walls edit mode
     */
    toggleEditMode(state) {
      state.editMode = state.editMode === "objects" ? "walls" : "objects";
      // Clear wall selection when switching to objects mode
      if (state.editMode === "objects") {
        state.selectedWallId = null;
        state.draggingWallEndpoint = null;
        state.draggingWallMidpoint = null;
      }
    },
    /**
     * Select a wall by ID
     */
    selectWall(state, action: PayloadAction<string | null>) {
      state.selectedWallId = action.payload;
    },
    /**
     * Start dragging a wall endpoint
     */
    startDraggingWallEndpoint(
      state,
      action: PayloadAction<{ wallId: string; endpoint: "start" | "end" }>,
    ) {
      state.draggingWallEndpoint = action.payload;
      state.selectedWallId = action.payload.wallId;
    },
    /**
     * Stop dragging wall endpoint
     */
    stopDraggingWallEndpoint(state) {
      state.draggingWallEndpoint = null;
    },
    /**
     * Start dragging wall midpoint (moves entire wall)
     */
    startDraggingWallMidpoint(state, action: PayloadAction<string>) {
      state.draggingWallMidpoint = action.payload;
      state.selectedWallId = action.payload;
    },
    /**
     * Stop dragging wall midpoint
     */
    stopDraggingWallMidpoint(state) {
      state.draggingWallMidpoint = null;
    },
    /**
     * Start drawing a new wall
     */
    startDrawingWall(state, action: PayloadAction<[number, number]>) {
      state.isDrawing = true;
      state.drawingStartPoint = action.payload;
      state.selectedWallId = null; // Deselect any selected wall
    },
    /**
     * Cancel wall drawing in progress
     */
    cancelDrawingWall(state) {
      state.isDrawing = false;
      state.drawingStartPoint = null;
      state.selectedWallId = null;
      state.draggingWallEndpoint = null;
      state.draggingWallMidpoint = null;
    },
    /**
     * Complete wall drawing (called after wall is added to state)
     */
    completeDrawingWall(state) {
      state.isDrawing = false;
      state.drawingStartPoint = null;
      state.draggingWallEndpoint = null;
      state.draggingWallMidpoint = null;
    },
    /**
     * Update default height/thickness for newly drawn walls
     */
    setWallDefaults(
      state,
      action: PayloadAction<{ height?: number; thickness?: number }>,
    ) {
      if (action.payload.height !== undefined)
        state.defaultWallHeight = action.payload.height;
      if (action.payload.thickness !== undefined)
        state.defaultWallThickness = action.payload.thickness;
    },
  },
});

/**
 * Selectors for accessing wall editor state
 */
export const wallEditorSelectors = {
  selectEditMode: (state: RootState) => state.wallEditor.editMode,
  selectIsWallEditMode: (state: RootState) =>
    state.wallEditor.editMode === "walls",
  selectSelectedWallId: (state: RootState) => state.wallEditor.selectedWallId,
  selectDraggingWallEndpoint: (state: RootState) =>
    state.wallEditor.draggingWallEndpoint,
  selectDraggingWallMidpoint: (state: RootState) =>
    state.wallEditor.draggingWallMidpoint,
  selectIsDrawing: (state: RootState) => state.wallEditor.isDrawing,
  selectDrawingStartPoint: (state: RootState) =>
    state.wallEditor.drawingStartPoint,
  selectWallDefaults: createSelector(
    (state: RootState) => state.wallEditor.defaultWallHeight,
    (state: RootState) => state.wallEditor.defaultWallThickness,
    (height, thickness) => ({ height, thickness }),
  ),
};

export const wallEditorActions = wallEditorSlice.actions;

export default wallEditorSlice.reducer;
