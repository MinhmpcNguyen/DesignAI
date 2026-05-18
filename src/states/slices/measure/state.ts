import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { MeasureLine, MeasureSliceType } from "./types";

const initialState: MeasureSliceType = {
  isActive: false,
  pendingStart: null,
  lines: [],
};

const measureSlice = createSlice({
  name: "measure",
  initialState,
  reducers: {
    /** Activate the measure tool */
    activateMeasure(state) {
      state.isActive = true;
      state.pendingStart = null;
    },
    /** Deactivate the measure tool and clear all lines */
    deactivateMeasure(state) {
      state.isActive = false;
      state.pendingStart = null;
      state.lines = [];
    },
    /** Set the first point (waiting for second click) */
    setPendingStart(state, action: PayloadAction<[number, number]>) {
      state.pendingStart = action.payload;
    },
    /** Discard the pending first point without completing a line */
    cancelPending(state) {
      state.pendingStart = null;
    },
    /** Complete a measurement line and clear the pending start */
    addMeasureLine(state, action: PayloadAction<MeasureLine>) {
      state.lines.push(action.payload);
      state.pendingStart = null;
    },
    /** Remove a specific measurement line by id */
    removeMeasureLine(state, action: PayloadAction<string>) {
      state.lines = state.lines.filter((l) => l.id !== action.payload);
    },
    /** Clear all measurement lines without deactivating the tool */
    clearAllLines(state) {
      state.lines = [];
      state.pendingStart = null;
    },
  },
});

export const measureSelectors = {
  selectIsActive: (state: RootState) => state.measure.isActive,
  selectPendingStart: (state: RootState) => state.measure.pendingStart,
  selectLines: (state: RootState) => state.measure.lines,
};

export const measureActions = measureSlice.actions;

export default measureSlice.reducer;
