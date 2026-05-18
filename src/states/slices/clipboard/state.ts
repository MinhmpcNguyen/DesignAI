import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { ClipboardSliceType } from "./types";
import type { SceneObject } from "../objects/types";

const initialState: ClipboardSliceType = {
  copiedObjects: [],
  isPasting: false,
};

const clipboardSlice = createSlice({
  name: "clipboard",
  initialState,
  reducers: {
    updateClipboardValue(state, action: PayloadAction<Partial<ClipboardSliceType>>) {
      Object.assign(state, action.payload);
    },
    setCopiedObjects(state, action: PayloadAction<SceneObject[]>) {
      state.copiedObjects = action.payload;
    },
    setIsPasting(state, action: PayloadAction<boolean>) {
      state.isPasting = action.payload;
    },
  },
});

export const clipboardSelectors = {
  selectClipboard: (state: RootState) => state.clipboard,
};

export const clipboardActions = clipboardSlice.actions;

export default clipboardSlice.reducer;
