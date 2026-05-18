import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { ProjectFiltersSliceType } from "./types";

const initialState: ProjectFiltersSliceType = {
  projectType: "Tất cả",
  areaRange: "Tất cả",
  modifiedDate: "Mới nhất",
};

const projectFiltersSlice = createSlice({
  name: "projectFilters",
  initialState,
  reducers: {
    setProjectType(state, action: PayloadAction<string>) {
      state.projectType = action.payload;
    },
    setAreaRange(state, action: PayloadAction<string>) {
      state.areaRange = action.payload;
    },
    setModifiedDate(state, action: PayloadAction<string>) {
      state.modifiedDate = action.payload;
    },
    resetProjectFilters() {
      return initialState;
    },
  },
});

export const projectFiltersActions = projectFiltersSlice.actions;

export const projectFiltersSelectors = {
  selectProjectFilters: (state: RootState) => state.projectFilters,
  selectProjectType: (state: RootState) => state.projectFilters.projectType,
  selectAreaRange: (state: RootState) => state.projectFilters.areaRange,
  selectModifiedDate: (state: RootState) => state.projectFilters.modifiedDate,
};

export default projectFiltersSlice.reducer;
