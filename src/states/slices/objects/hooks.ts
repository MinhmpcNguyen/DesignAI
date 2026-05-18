import { useCallback, useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import {
  objectsActions,
  objectsSelectors,
  duplicateMultipleObjects,
  duplicateObject,
} from "./state";
import type { ObjectsSliceType, SceneObject } from "./types";
import type { PendingDrop } from "./state";

export const useObjectsValue = (): ObjectsSliceType =>
  useAppSelector(objectsSelectors.selectObjectsState);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFn = (...args: any[]) => void;

/**
 * Debounce a callback while keeping a stable identity.
 * Useful for reducing Redux dispatch frequency during high-frequency UI events (e.g. drag).
 */
function useDebouncedCallback<F extends AnyFn>(callback: F, delayMs: number) {
  const callbackRef = useRef<F>(callback);
  if (callbackRef.current !== null) {
    callbackRef.current = callback;
  }

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return useCallback(
    (...args: Parameters<F>) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, delayMs);
    },
    [delayMs],
  );
}

export const useUpdateObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (update: Partial<ObjectsSliceType>) => {
      dispatch(objectsActions.updateObjectsValue(update));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateObjects = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (next: Partial<ObjectsSliceType>) => {
      dispatch(objectsActions.updateObjectsValue(next));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const useAddObject = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (obj: SceneObject) => {
      dispatch(objectsActions.addObject(obj));
    },
    [dispatch],
  );
};

export const useRemoveObject = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string) => {
      dispatch(objectsActions.removeObject(id));
    },
    [dispatch],
  );
};

export const useDuplicateObject = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string) => {
      dispatch(duplicateObject(id));
    },
    [dispatch],
  );
};

export const useUpdateObjectPosition = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, position: [number, number, number]) => {
      dispatch(objectsActions.updateObjectPosition({ id, position }));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateObjectPosition = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (id: string, position: [number, number, number]) => {
      dispatch(objectsActions.updateObjectPosition({ id, position }));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const useUpdateObjectRotation = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, rotation: [number, number, number, number]) => {
      dispatch(objectsActions.updateObjectRotation({ id, rotation }));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateObjectRotation = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (id: string, rotation: [number, number, number, number]) => {
      dispatch(objectsActions.updateObjectRotation({ id, rotation }));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const useUpdateObjectSize = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, size: [number, number, number]) => {
      dispatch(objectsActions.updateObjectSize({ id, size }));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateObjectSize = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (id: string, size: [number, number, number]) => {
      dispatch(objectsActions.updateObjectSize({ id, size }));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const usePendingDrop = (): PendingDrop | null =>
  useAppSelector(objectsSelectors.selectPendingDrop);

export const useSetPendingDrop = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (pending: PendingDrop | null) => {
      dispatch(objectsActions.setPendingDrop(pending));
    },
    [dispatch],
  );
};

// Multi-object hooks
export const useRemoveMultipleObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (ids: Set<string>) => {
      dispatch(objectsActions.removeMultipleObjects(ids));
    },
    [dispatch],
  );
};

export const useDuplicateMultipleObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (ids: Set<string>) => {
      return dispatch(duplicateMultipleObjects(ids));
    },
    [dispatch],
  );
};

export const useAddMultipleObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (newObjects: SceneObject[]) => {
      dispatch(objectsActions.addMultipleObjects(newObjects));
    },
    [dispatch],
  );
};

export const useUpdateMultipleObjectPositions = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (updates: Array<{ id: string; position: [number, number, number] }>) => {
      dispatch(objectsActions.updateMultipleObjectPositions(updates));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateMultipleObjectPositions = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (updates: Array<{ id: string; position: [number, number, number] }>) => {
      dispatch(objectsActions.updateMultipleObjectPositions(updates));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const useUpdateGroupPositionsByDelta = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: { objectIds: string[]; delta: [number, number, number] }) => {
      dispatch(objectsActions.updateGroupPositionsByDelta(params));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateGroupPositionsByDelta = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pendingRef = useRef<{
    objectIdsKey: string;
    objectIds: string[];
    delta: [number, number, number];
  } | null>(null);

  const flush = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    dispatch(
      objectsActions.updateGroupPositionsByDelta({
        objectIds: pending.objectIds,
        delta: pending.delta,
      }),
    );
  }, [dispatch]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return useCallback(
    (params: { objectIds: string[]; delta: [number, number, number] }) => {
      const key = [...params.objectIds].sort().join("|");

      if (!pendingRef.current || pendingRef.current.objectIdsKey !== key) {
        pendingRef.current = {
          objectIdsKey: key,
          objectIds: params.objectIds,
          delta: [...params.delta] as [number, number, number],
        };
      } else {
        // Delta is additive, so we can safely accumulate and dispatch once.
        pendingRef.current.delta = [
          pendingRef.current.delta[0] + params.delta[0],
          pendingRef.current.delta[1] + params.delta[1],
          pendingRef.current.delta[2] + params.delta[2],
        ];
      }

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(flush, delayMs);
    },
    [delayMs, flush],
  );
};

export const useUpdateObjectSnapMetadata = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: {
      id: string;
      placementType?: "floor" | "wall" | "ceiling";
      snappedToWall?: string;
    }) => {
      dispatch(objectsActions.updateObjectSnapMetadata(params));
    },
    [dispatch],
  );
};

export const useDebouncedUpdateObjectSnapMetadata = (delayMs = 16) => {
  const dispatch = useAppDispatch();
  const update = useCallback(
    (params: {
      id: string;
      placementType?: "floor" | "wall" | "ceiling";
      snappedToWall?: string;
    }) => {
      dispatch(objectsActions.updateObjectSnapMetadata(params));
    },
    [dispatch],
  );
  return useDebouncedCallback(update, delayMs);
};

export const useReplaceAllObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objects: SceneObject[]) => {
      dispatch(objectsActions.replaceAllObjects(objects));
    },
    [dispatch],
  );
};

// ------------------------------------------------------------------
// Live-move hooks — no history push; use during drag frames
// ------------------------------------------------------------------
export const useMoveObjectLive = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, position: [number, number, number]) => {
      dispatch(objectsActions.moveObjectLive({ id, position }));
    },
    [dispatch],
  );
};

export const useMoveObjectRotationLive = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string, rotation: [number, number, number, number]) => {
      dispatch(objectsActions.moveObjectRotationLive({ id, rotation }));
    },
    [dispatch],
  );
};

export const useMoveGroupPositionsLive = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: { objectIds: string[]; delta: [number, number, number] }) => {
      dispatch(objectsActions.moveGroupPositionsLive(params));
    },
    [dispatch],
  );
};

/** Live update — writes resolved color/material/price display values without pushing to history. */
export const useSetObjectDisplayOptions = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (payload: {
      id: string;
      selectedColorHex?: string;
      selectedColorName?: string;
      selectedMaterialName?: string;
      variantPriceCents?: number;
    }) => {
      dispatch(objectsActions.setObjectDisplayOptions(payload));
    },
    [dispatch],
  );
};

/** Commits the final state of a drag in a single history push. Call from onDragEnd. */
export const useCommitObjectAfterDrag = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: {
      id: string;
      position: [number, number, number];
      rotation?: [number, number, number, number];
      placementType?: "floor" | "wall" | "ceiling";
      snappedToWall?: string;
    }) => {
      dispatch(objectsActions.commitObjectAfterDrag(params));
    },
    [dispatch],
  );
};

// ------------------------------------------------------------------
// Undo / redo info
// ------------------------------------------------------------------
export const useObjectsCanUndo = () =>
  useAppSelector(objectsSelectors.selectCanUndo);

export const useObjectsCanRedo = () =>
  useAppSelector(objectsSelectors.selectCanRedo);

// ------------------------------------------------------------------
// Resize hooks — live (no history) + commit (single history entry)
// ------------------------------------------------------------------
export const useResizeAndRepositionLive = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: {
      id: string;
      size: [number, number, number];
      position: [number, number, number];
    }) => {
      dispatch(objectsActions.resizeAndRepositionLive(params));
    },
    [dispatch],
  );
};

export const useCommitResizeAfterDrag = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (params: {
      id: string;
      size: [number, number, number];
      position: [number, number, number];
    }) => {
      dispatch(objectsActions.commitResizeAfterDrag(params));
    },
    [dispatch],
  );
};
