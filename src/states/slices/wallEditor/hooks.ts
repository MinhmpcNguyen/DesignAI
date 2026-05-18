import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { wallEditorActions, wallEditorSelectors } from "./state";
import type { EditMode } from "./types";

/**
 * Hook to get the current edit mode
 */
export const useEditMode = () =>
  useAppSelector(wallEditorSelectors.selectEditMode);

/**
 * Hook to check if in wall edit mode
 */
export const useIsWallEditMode = () =>
  useAppSelector(wallEditorSelectors.selectIsWallEditMode);

/**
 * Hook to get the selected wall ID
 */
export const useSelectedWallId = () =>
  useAppSelector(wallEditorSelectors.selectSelectedWallId);

/**
 * Hook to set the edit mode
 */
export const useSetEditMode = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (mode: EditMode) => {
      dispatch(wallEditorActions.setEditMode(mode));
    },
    [dispatch],
  );
};

/**
 * Hook to toggle between objects and walls edit mode
 */
export const useToggleEditMode = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallEditorActions.toggleEditMode());
  }, [dispatch]);
};

/**
 * Hook to select a wall
 */
export const useSelectWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (wallId: string | null) => {
      dispatch(wallEditorActions.selectWall(wallId));
    },
    [dispatch],
  );
};

/**
 * Hook to start dragging a wall endpoint
 */
export const useStartDraggingWallEndpoint = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (wallId: string, endpoint: "start" | "end") => {
      dispatch(
        wallEditorActions.startDraggingWallEndpoint({ wallId, endpoint }),
      );
    },
    [dispatch],
  );
};

/**
 * Hook to stop dragging wall endpoint
 */
export const useStopDraggingWallEndpoint = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallEditorActions.stopDraggingWallEndpoint());
  }, [dispatch]);
};

/**
 * Hook to start dragging wall midpoint
 */
export const useStartDraggingWallMidpoint = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (wallId: string) => {
      dispatch(wallEditorActions.startDraggingWallMidpoint(wallId));
    },
    [dispatch],
  );
};

/**
 * Hook to stop dragging wall midpoint
 */
export const useStopDraggingWallMidpoint = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallEditorActions.stopDraggingWallMidpoint());
  }, [dispatch]);
};

/**
 * Hook to check if currently drawing a wall
 */
export const useIsDrawing = () =>
  useAppSelector(wallEditorSelectors.selectIsDrawing);

/**
 * Hook to get the wall drawing start point
 */
export const useDrawingStartPoint = () =>
  useAppSelector(wallEditorSelectors.selectDrawingStartPoint);

/**
 * Hook to start drawing a new wall
 */
export const useStartDrawingWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (startPoint: [number, number]) => {
      dispatch(wallEditorActions.startDrawingWall(startPoint));
    },
    [dispatch],
  );
};

/**
 * Hook to cancel wall drawing
 */
export const useCancelDrawingWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallEditorActions.cancelDrawingWall());
  }, [dispatch]);
};

/**
 * Hook to complete wall drawing (after wall added)
 */
export const useCompleteDrawingWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallEditorActions.completeDrawingWall());
  }, [dispatch]);
};

/**
 * Hook to read the default height/thickness for newly drawn walls
 */
export const useWallDefaults = () =>
  useAppSelector(wallEditorSelectors.selectWallDefaults);

/**
 * Hook to update the default height/thickness for newly drawn walls
 */
export const useSetWallDefaults = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (defaults: { height?: number; thickness?: number }) => {
      dispatch(wallEditorActions.setWallDefaults(defaults));
    },
    [dispatch],
  );
};
