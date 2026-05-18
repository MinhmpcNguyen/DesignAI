/**
 * Snapping System Hooks
 *
 * Custom React hooks for accessing snapping state and performing snap calculations.
 * Following the project's pattern of wrapping Jotai atoms in hooks for better DX.
 */

import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { snappingActions, snappingSelectors } from "./state";
import { calculateSnap, canSnap, getSnapDistance } from "./utils";
import type { SnapResult, RoomDimensions } from "./types";
import { useWalls } from "@/states/slices/walls/hooks";

/**
 * Hook: Get current snap threshold
 */
export function useSnapThreshold(): number {
  return useAppSelector(snappingSelectors.selectSnapThreshold);
}

/**
 * Hook: Get snap indicators visibility setting
 */
export function useShowSnapIndicators(): boolean {
  return useAppSelector(snappingSelectors.selectShowSnapIndicators);
}

/**
 * Hook: Get room dimensions
 */
export function useRoomDimensions(): RoomDimensions {
  return useAppSelector(snappingSelectors.selectRoomDimensions);
}

/**
 * Hook: Get wall thickness
 */
export function useWallThickness(): number {
  return useAppSelector(snappingSelectors.selectWallThickness);
}

/**
 * Hook: Get complete snapping configuration
 */
export function useSnappingConfig() {
  return useAppSelector(snappingSelectors.selectSnappingConfig);
}

/**
 * Hook: Update snap threshold
 */
export function useUpdateSnapThreshold() {
  const dispatch = useAppDispatch();
  return useCallback(
    (threshold: number) => {
      dispatch(snappingActions.setSnapThreshold(threshold));
    },
    [dispatch],
  );
}

/**
 * Hook: Update room dimensions
 */
export function useUpdateRoomDimensions() {
  const dispatch = useAppDispatch();
  return useCallback(
    (dimensions: Partial<RoomDimensions>) => {
      dispatch(snappingActions.setRoomDimensions(dimensions));
    },
    [dispatch],
  );
}

/**
 * Hook: Calculate snap with current settings
 *
 * Returns a memoized function that calculates snap position/rotation
 * for a given furniture type and position.
 *
 * Performance: Memoized function prevents recreation on every render
 */
export function useCalculateSnap() {
  const walls = useWalls();
  const snapThreshold = useSnapThreshold();

  return useCallback(
    (
      furnitureType: string,
      position: [number, number, number],
      objectSize?: [number, number, number],
      placementTypeOverride?: "floor" | "wall" | "ceiling",
      wallSnapThresholdOverride?: number,
    ): SnapResult => {
      return calculateSnap(
        furnitureType,
        position,
        walls,
        snapThreshold,
        objectSize,
        placementTypeOverride,
        wallSnapThresholdOverride,
      );
    },
    [walls, snapThreshold],
  );
}

/**
 * Hook: Check if position can snap
 *
 * Returns a memoized validation function.
 * Useful for showing warnings when wall objects are too far from walls.
 */
export function useCanSnap() {
  const walls = useWalls();
  const snapThreshold = useSnapThreshold();

  return useCallback(
    (furnitureType: string, position: [number, number, number]): boolean => {
      return canSnap(furnitureType, position, walls, snapThreshold);
    },
    [walls, snapThreshold],
  );
}

/**
 * Hook: Get distance to nearest snap target
 *
 * Returns a memoized function for calculating snap distance.
 * Useful for visual feedback (e.g., color intensity based on distance).
 */
export function useGetSnapDistance() {
  const walls = useWalls();

  return useCallback(
    (
      furnitureType: string,
      position: [number, number, number],
      objectSize?: [number, number, number],
    ): number => {
      return getSnapDistance(furnitureType, position, walls, objectSize);
    },
    [walls],
  );
}
