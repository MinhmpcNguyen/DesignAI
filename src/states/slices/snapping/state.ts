import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { RoomDimensions, SnappingConfig } from "./types";

export type SnappingState = {
  snapThreshold: number;
  showSnapIndicators: boolean;
  enableFloorSnap: boolean;
  enableWallSnap: boolean;
  enableCeilingSnap: boolean;
  roomDimensions: RoomDimensions;
  wallThickness: number;
};

const initialState: SnappingState = {
  snapThreshold: 0.1,
  showSnapIndicators: true,
  enableFloorSnap: true,
  enableWallSnap: true,
  enableCeilingSnap: true,
  roomDimensions: { width: 20, depth: 20, height: 3 },
  wallThickness: 0.5,
};

const snappingSlice = createSlice({
  name: "snapping",
  initialState,
  reducers: {
    setSnapThreshold(state, action: PayloadAction<number>) {
      // Clamp between 0.1m and 2.0m for reasonable snapping
      state.snapThreshold = Math.max(0.1, Math.min(2.0, action.payload));
    },
    setShowSnapIndicators(state, action: PayloadAction<boolean>) {
      state.showSnapIndicators = action.payload;
    },
    setEnableFloorSnap(state, action: PayloadAction<boolean>) {
      state.enableFloorSnap = action.payload;
    },
    setEnableWallSnap(state, action: PayloadAction<boolean>) {
      state.enableWallSnap = action.payload;
    },
    setEnableCeilingSnap(state, action: PayloadAction<boolean>) {
      state.enableCeilingSnap = action.payload;
    },
    setRoomDimensions(state, action: PayloadAction<Partial<RoomDimensions>>) {
      const current = state.roomDimensions;
      state.roomDimensions = {
        width: action.payload.width ?? current.width,
        depth: action.payload.depth ?? current.depth,
        height: action.payload.height ?? current.height,
      };
    },
    setWallThickness(state, action: PayloadAction<number>) {
      state.wallThickness = action.payload;
    },
  },
});

export const snappingSelectors = {
  selectSnapThreshold: (state: RootState) => state.snapping.snapThreshold,
  selectShowSnapIndicators: (state: RootState) =>
    state.snapping.showSnapIndicators,
  selectEnableFloorSnap: (state: RootState) => state.snapping.enableFloorSnap,
  selectEnableWallSnap: (state: RootState) => state.snapping.enableWallSnap,
  selectEnableCeilingSnap: (state: RootState) =>
    state.snapping.enableCeilingSnap,
  selectRoomDimensions: (state: RootState) => state.snapping.roomDimensions,
  selectWallThickness: (state: RootState) => state.snapping.wallThickness,
  selectSnappingConfig: (state: RootState): SnappingConfig => ({
    snapThreshold: state.snapping.snapThreshold,
    showIndicators: state.snapping.showSnapIndicators,
    enableFloorSnap: state.snapping.enableFloorSnap,
    enableWallSnap: state.snapping.enableWallSnap,
    enableCeilingSnap: state.snapping.enableCeilingSnap,
  }),
};

export const snappingActions = snappingSlice.actions;

export default snappingSlice.reducer;
