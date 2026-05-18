import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { DragSliceType, DraggingShape } from "./types";

const initialState: DragSliceType = {
  isDragging: false,
  draggingShape: null,
};

const dragSlice = createSlice({
  name: "drag",
  initialState,
  reducers: {
    updateDragValue(state, action: PayloadAction<Partial<DragSliceType>>) {
      Object.assign(state, action.payload);
    },
    setIsDragging(state, action: PayloadAction<boolean>) {
      state.isDragging = action.payload;
    },
    setDraggingShape(state, action: PayloadAction<DraggingShape | null>) {
      state.draggingShape = action.payload;
    },
  },
});

export const dragSelectors = {
  selectDrag: (state: RootState) => state.drag,
};

export const dragActions = dragSlice.actions;

export default dragSlice.reducer;
