import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { wallsActions, wallsSelectors } from "./state";
import type { Wall } from "./types";

/**
 * Hook to get all walls from Redux state
 */
export const useWalls = () => useAppSelector(wallsSelectors.selectWalls);

/**
 * Hook to get a specific wall by ID
 */
export const useWallById = (id: string) =>
  useAppSelector(wallsSelectors.selectWallById(id));

/**
 * Hook to get the count of walls
 */
export const useWallCount = () =>
  useAppSelector(wallsSelectors.selectWallCount);

/**
 * Hook to add a new wall
 */
export const useAddWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (wall: Wall) => {
      dispatch(wallsActions.addWall(wall));
    },
    [dispatch],
  );
};

/**
 * Hook to remove a wall by ID
 */
export const useRemoveWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string) => {
      dispatch(wallsActions.removeWall(id));
    },
    [dispatch],
  );
};

/**
/**
 * Hook to update a wall's properties
 */
export const useUpdateWall = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, updates: Partial<Wall>) => {
      dispatch(wallsActions.updateWall({ id, updates }));
    },
    [dispatch],
  );
};

/**
 * Hook to update multiple walls in one dispatch.
 * Use this whenever a drag should propagate to connected walls.
 */
export const useUpdateManyWalls = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (updates: Array<{ id: string; updates: Partial<Wall> }>) => {
      dispatch(wallsActions.updateManyWalls(updates));
    },
    [dispatch],
  );
};

/**
 * Hook to replace all walls (for loading saved designs)
 */
export const useSetWalls = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (walls: Wall[]) => {
      dispatch(wallsActions.setWalls(walls));
    },
    [dispatch],
  );
};

/**
 * Push current walls to history without mutating — call at the START of a drag
 * so the entire drag gesture is a single undo step.
 */
export const useBeginWallEdit = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(wallsActions.beginWallEdit());
  }, [dispatch]);
};

export const useWallsCanUndo = () =>
  useAppSelector(wallsSelectors.selectCanUndo);

export const useWallsCanRedo = () =>
  useAppSelector(wallsSelectors.selectCanRedo);
