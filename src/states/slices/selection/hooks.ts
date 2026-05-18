import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import {
  selectionActions,
  selectionSelectors,
  selectObjectOrGroup,
  toggleObjectOrGroup,
} from "./state";
import type { SelectionSliceType } from "./types";

export const useSelectionValue = (): SelectionSliceType =>
  useAppSelector(selectionSelectors.selectSelection);

export const useUpdateSelection = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (update: Partial<SelectionSliceType>) => {
      dispatch(selectionActions.updateSelectionValue(update));
    },
    [dispatch],
  );
};

export const useSetSelectedId = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (selectedId: string | null) => {
      dispatch(selectionActions.setSelectedId(selectedId));
    },
    [dispatch],
  );
};

export const useToggleSelection = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectId: string) => {
      dispatch(selectionActions.toggleSelection(objectId));
    },
    [dispatch],
  );
};

export const useSelectAllObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectIds: string[]) => {
      dispatch(selectionActions.selectAllObjects(objectIds));
    },
    [dispatch],
  );
};

export const useClearSelection = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(selectionActions.clearSelection());
  }, [dispatch]);
};

export const useSetCtrlPressed = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (isPressed: boolean) => {
      dispatch(selectionActions.setCtrlPressed(isPressed));
    },
    [dispatch],
  );
};

export const useSelectObjectOrGroup = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectId: string) => {
      dispatch(selectObjectOrGroup(objectId));
    },
    [dispatch],
  );
};

export const useToggleObjectOrGroup = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectId: string) => {
      dispatch(toggleObjectOrGroup(objectId));
    },
    [dispatch],
  );
};

/** Returns true only when this specific object is in the selection set. */
export const useIsObjectSelected = (id: string): boolean =>
  useAppSelector((state) => state.selection.selectedIds.has(id));

/** Returns the current Ctrl-key pressed state. */
export const useIsCtrlPressed = (): boolean =>
  useAppSelector((state) => state.selection.isCtrlPressed);

/** Returns true only when this specific object is the primary selection. */
export const useIsPrimarySelected = (id: string): boolean =>
  useAppSelector((state) => state.selection.primarySelectedId === id);
