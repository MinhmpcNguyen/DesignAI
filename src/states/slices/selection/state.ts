import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { AppDispatch, RootState } from "@/states/store";
import type { SelectionSliceType } from "./types";

const initialState: SelectionSliceType = {
  selectedIds: new Set<string>(),
  isCtrlPressed: false,
  primarySelectedId: null,
};

const selectionSlice = createSlice({
  name: "selection",
  initialState,
  reducers: {
    updateSelectionValue(
      state,
      action: PayloadAction<Partial<SelectionSliceType>>,
    ) {
      Object.assign(state, action.payload);
    },
    setSelectedId(state, action: PayloadAction<string | null>) {
      const selectedId = action.payload;
      if (selectedId === null) {
        state.selectedIds = new Set<string>();
        state.primarySelectedId = null;
      } else {
        state.selectedIds = new Set([selectedId]);
        state.primarySelectedId = selectedId;
      }
    },
    toggleSelection(state, action: PayloadAction<string>) {
      const objectId = action.payload;
      const newSelection = new Set(state.selectedIds);

      if (newSelection.has(objectId)) {
        newSelection.delete(objectId);
        const newPrimary =
          newSelection.size > 0 ? Array.from(newSelection)[0] : null;
        state.selectedIds = newSelection;
        state.primarySelectedId = newPrimary;
      } else {
        newSelection.add(objectId);
        state.selectedIds = newSelection;
        state.primarySelectedId = objectId;
      }
    },
    selectAllObjects(state, action: PayloadAction<string[]>) {
      const objectIds = action.payload;
      state.selectedIds = new Set(objectIds);
      state.primarySelectedId = objectIds.length > 0 ? objectIds[0] : null;
    },
    clearSelection(state) {
      state.selectedIds = new Set<string>();
      state.primarySelectedId = null;
    },
    setCtrlPressed(state, action: PayloadAction<boolean>) {
      state.isCtrlPressed = action.payload;
    },
  },
});

export const selectionSelectors = {
  selectSelection: (state: RootState) => state.selection,
};

export const selectionActions = selectionSlice.actions;

export const selectObjectOrGroup =
  (objectId: string) => (dispatch: AppDispatch, getState: () => RootState) => {
    const { objectToGroupMap, groups } = getState().groups;
    const groupId = objectToGroupMap[objectId];

    if (groupId) {
      const group = groups.find((g) => g.id === groupId);
      if (group) {
        dispatch(
          selectionActions.updateSelectionValue({
            selectedIds: new Set(group.objectIds),
            primarySelectedId: objectId,
          }),
        );
        return;
      }
    }

    dispatch(
      selectionActions.updateSelectionValue({
        selectedIds: new Set([objectId]),
        primarySelectedId: objectId,
      }),
    );
  };

export const toggleObjectOrGroup =
  (objectId: string) => (dispatch: AppDispatch, getState: () => RootState) => {
    const { selectedIds } = getState().selection;
    const { objectToGroupMap, groups } = getState().groups;
    const groupId = objectToGroupMap[objectId];

    if (groupId) {
      const group = groups.find((g) => g.id === groupId);
      if (group) {
        const newSelection = new Set(selectedIds);
        const isGroupSelected = group.objectIds.every((id) =>
          newSelection.has(id),
        );

        if (isGroupSelected) {
          group.objectIds.forEach((id) => newSelection.delete(id));
          const newPrimary =
            newSelection.size > 0 ? Array.from(newSelection)[0] : null;
          dispatch(
            selectionActions.updateSelectionValue({
              selectedIds: newSelection,
              primarySelectedId: newPrimary,
            }),
          );
        } else {
          group.objectIds.forEach((id) => newSelection.add(id));
          dispatch(
            selectionActions.updateSelectionValue({
              selectedIds: newSelection,
              primarySelectedId: objectId,
            }),
          );
        }
        return;
      }
    }

    dispatch(selectionActions.toggleSelection(objectId));
  };

export default selectionSlice.reducer;
