import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { dragActions, dragSelectors } from "./state";
import type { DragSliceType, DraggingShape } from "./types";

export const useDragValue = (): DragSliceType =>
  useAppSelector(dragSelectors.selectDrag);

export const useUpdateDrag = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (update: Partial<DragSliceType>) => {
      dispatch(dragActions.updateDragValue(update));
    },
    [dispatch],
  );
};

export const useSetIsDragging = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (isDragging: boolean) => {
      dispatch(dragActions.setIsDragging(isDragging));
    },
    [dispatch],
  );
};

export const useSetDraggingShape = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (shape: DraggingShape | null) => {
      dispatch(dragActions.setDraggingShape(shape));
    },
    [dispatch],
  );
};
