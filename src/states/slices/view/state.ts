import { createSlice } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { ViewSliceType, ViewMode } from "./types";

const initialState: ViewSliceType = {
  viewMode: "2D", // Default to 2D mode as requested
  isAIGenMode: false,
};

const viewSlice = createSlice({
  name: "view",
  initialState,
  reducers: {
    toggleViewMode(state) {
      state.viewMode = state.viewMode === "2D" ? "3D" : "2D";
    },
    setViewMode(state, action: { payload: ViewMode }) {
      state.viewMode = action.payload;
    },
    setIsAIGenMode(state, action: { payload: boolean }) {
      state.isAIGenMode = action.payload;
    },
  },
});

export const viewSelectors = {
  selectView: (state: RootState) => state.view,
  selectViewMode: (state: RootState) => state.view.viewMode,
  selectIsAIGenMode: (state: RootState) => state.view.isAIGenMode,
};

export const viewActions = viewSlice.actions;

export default viewSlice.reducer;
