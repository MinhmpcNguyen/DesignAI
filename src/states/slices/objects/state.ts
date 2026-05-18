import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { AppDispatch, RootState } from "@/states/store";
import { ObjectsSliceType, SceneObject } from "./types";

/** Pending drop from overlay: shape + screen coords for raycast. Cleared after processing. */
export type PendingDrop = {
  shape: "model";
  /** Display name from catalog (e.g. "Bunk Bed"). */
  name?: string;
  clientX: number;
  clientY: number;
  /** URL to a .glb model file — only set when shape === 'model' */
  modelUrl?: string;
  objectRole?: string;
  /** UUID of the catalog item — copied to SceneObject on placement. */
  catalogItemId?: string;
};

/** One entry in the undo/redo stacks. ts is used by the cross-slice thunk to pick the most-recent slice to undo. */
type HistoryEntry = { ts: number; objects: SceneObject[] };

export type ObjectsState = ObjectsSliceType & {
  pendingDrop: PendingDrop | null;
  history: HistoryEntry[];
  future: HistoryEntry[];
};

const cloneSceneObject = (object: SceneObject): SceneObject => ({
  ...object,
  position: [...object.position],
  size: [...object.size],
  ...(object.rotation ? { rotation: [...object.rotation] } : {}),
});

const MAX_HISTORY = 50;

const pushObjectsHistory = (state: ObjectsState) => {
  state.history.push({
    ts: Date.now(),
    objects: state.objects.map(cloneSceneObject),
  });
  if (state.history.length > MAX_HISTORY) state.history.shift();
  // New action invalidates the redo stack
  state.future = [];
};

const initialState: ObjectsState = {
  pendingDrop: null,
  objects: [],
  history: [],
  future: [],
};

const objectsSlice = createSlice({
  name: "objects",
  initialState,
  reducers: {
    updateObjectsValue(
      state,
      action: PayloadAction<Partial<ObjectsSliceType>>,
    ) {
      if (action.payload.objects) {
        pushObjectsHistory(state);
      }
      Object.assign(state, action.payload);
    },
    setPendingDrop(state, action: PayloadAction<PendingDrop | null>) {
      state.pendingDrop = action.payload;
    },
    addObject(state, action: PayloadAction<SceneObject>) {
      pushObjectsHistory(state);
      state.objects.push(action.payload);
    },
    removeObject(state, action: PayloadAction<string>) {
      const hasObject = state.objects.some((o) => o.id === action.payload);
      if (!hasObject) return;
      pushObjectsHistory(state);
      state.objects = state.objects.filter((o) => o.id !== action.payload);
    },
    updateObjectPosition(
      state,
      action: PayloadAction<{
        id: string;
        position: [number, number, number];
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.position = action.payload.position;
    },
    updateObjectRotation(
      state,
      action: PayloadAction<{
        id: string;
        rotation: [number, number, number, number];
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.rotation = action.payload.rotation;
    },
    removeMultipleObjects(state, action: PayloadAction<Set<string>>) {
      const hasAnyMatch = state.objects.some((o) => action.payload.has(o.id));
      if (!hasAnyMatch) return;
      pushObjectsHistory(state);
      state.objects = state.objects.filter((o) => !action.payload.has(o.id));
    },
    addMultipleObjects(state, action: PayloadAction<SceneObject[]>) {
      if (action.payload.length === 0) return;
      pushObjectsHistory(state);
      state.objects.push(...action.payload);
    },
    updateMultipleObjectPositions(
      state,
      action: PayloadAction<
        Array<{ id: string; position: [number, number, number] }>
      >,
    ) {
      const updateMap = new Map(
        action.payload.map((u) => [u.id, u.position] as const),
      );
      const hasAnyMatch = state.objects.some((o) => updateMap.has(o.id));
      if (!hasAnyMatch) return;
      pushObjectsHistory(state);
      state.objects.forEach((o) => {
        const next = updateMap.get(o.id);
        if (next) o.position = next;
      });
    },
    updateGroupPositionsByDelta(
      state,
      action: PayloadAction<{
        objectIds: string[];
        delta: [number, number, number];
      }>,
    ) {
      const objectIdSet = new Set(action.payload.objectIds);
      const [dx, dy, dz] = action.payload.delta;
      const hasAnyMatch = state.objects.some((o) => objectIdSet.has(o.id));
      if (!hasAnyMatch) return;
      pushObjectsHistory(state);
      state.objects.forEach((o) => {
        if (!objectIdSet.has(o.id)) return;
        o.position = [
          o.position[0] + dx,
          o.position[1] + dy,
          o.position[2] + dz,
        ];
      });
    },
    updateObjectSnapMetadata(
      state,
      action: PayloadAction<{
        id: string;
        placementType?: "floor" | "wall" | "ceiling";
        snappedToWall?: string;
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.placementType = action.payload.placementType;
      obj.snappedToWall = action.payload.snappedToWall;
    },
    // ------------------------------------------------------------------
    // Live-move reducers: update state WITHOUT pushing to history.
    // Used during drag frames so undo captures only the final resting
    // position rather than hundreds of intermediate positions.
    // ------------------------------------------------------------------
    moveObjectLive(
      state,
      action: PayloadAction<{ id: string; position: [number, number, number] }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (obj) obj.position = action.payload.position;
    },
    moveObjectRotationLive(
      state,
      action: PayloadAction<{
        id: string;
        rotation: [number, number, number, number];
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (obj) obj.rotation = action.payload.rotation;
    },
    moveGroupPositionsLive(
      state,
      action: PayloadAction<{
        objectIds: string[];
        delta: [number, number, number];
      }>,
    ) {
      const idSet = new Set(action.payload.objectIds);
      const [dx, dy, dz] = action.payload.delta;
      state.objects.forEach((o) => {
        if (!idSet.has(o.id)) return;
        o.position = [
          o.position[0] + dx,
          o.position[1] + dy,
          o.position[2] + dz,
        ];
      });
    },
    /** Live update — writes resolved color/material/price display values WITHOUT pushing to history. */
    setObjectDisplayOptions(
      state,
      action: PayloadAction<{
        id: string;
        selectedColorHex?: string;
        selectedColorName?: string;
        selectedMaterialName?: string;
        variantPriceCents?: number;
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      obj.selectedColorHex = action.payload.selectedColorHex;
      obj.selectedColorName = action.payload.selectedColorName;
      obj.selectedMaterialName = action.payload.selectedMaterialName;
      if (action.payload.variantPriceCents !== undefined)
        obj.variantPriceCents = action.payload.variantPriceCents;
    },
    /** Called once at onDragEnd — commits position + rotation + snap in a single history push. */
    commitObjectAfterDrag(
      state,
      action: PayloadAction<{
        id: string;
        position: [number, number, number];
        rotation?: [number, number, number, number];
        placementType?: "floor" | "wall" | "ceiling";
        snappedToWall?: string;
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.position = action.payload.position;
      if (action.payload.rotation) obj.rotation = action.payload.rotation;
      if (action.payload.placementType !== undefined)
        obj.placementType = action.payload.placementType;
      if (action.payload.snappedToWall !== undefined)
        obj.snappedToWall = action.payload.snappedToWall;
    },
    addObjects(state, action: PayloadAction<SceneObject[]>) {
      if (action.payload.length === 0) return;
      pushObjectsHistory(state);
      state.objects.push(...action.payload);
    },
    replaceAllObjects(state, action: PayloadAction<SceneObject[]>) {
      pushObjectsHistory(state);
      state.objects = action.payload.map(cloneSceneObject);
    },
    updateObjectSize(
      state,
      action: PayloadAction<{ id: string; size: [number, number, number] }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.size = action.payload.size;
    },
    /** Live resize — updates size + position every drag frame WITHOUT pushing to history. */
    resizeAndRepositionLive(
      state,
      action: PayloadAction<{
        id: string;
        size: [number, number, number];
        position: [number, number, number];
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      obj.size = action.payload.size;
      obj.position = action.payload.position;
    },
    /** Commits the final size + position of a resize drag in a single history push. */
    commitResizeAfterDrag(
      state,
      action: PayloadAction<{
        id: string;
        size: [number, number, number];
        position: [number, number, number];
      }>,
    ) {
      const obj = state.objects.find((o) => o.id === action.payload.id);
      if (!obj) return;
      pushObjectsHistory(state);
      obj.size = action.payload.size;
      obj.position = action.payload.position;
    },
    undo(state) {
      const entry = state.history.pop();
      if (!entry) return;
      state.future.push({
        ts: entry.ts,
        objects: state.objects.map(cloneSceneObject),
      });
      if (state.future.length > MAX_HISTORY) state.future.shift();
      state.objects = entry.objects.map(cloneSceneObject);
    },
    redo(state) {
      const entry = state.future.pop();
      if (!entry) return;
      state.history.push({
        ts: entry.ts,
        objects: state.objects.map(cloneSceneObject),
      });
      if (state.history.length > MAX_HISTORY) state.history.shift();
      state.objects = entry.objects.map(cloneSceneObject);
    },
  },
});

export const objectsSelectors = {
  selectObjectsState: (state: RootState) => state.objects,
  selectObjects: (state: RootState) => state.objects.objects,
  selectPendingDrop: (state: RootState) => state.objects.pendingDrop,
  selectLastHistoryTs: (state: RootState) =>
    state.objects.history.length > 0
      ? state.objects.history[state.objects.history.length - 1].ts
      : -Infinity,
  selectLastFutureTs: (state: RootState) =>
    state.objects.future.length > 0
      ? state.objects.future[state.objects.future.length - 1].ts
      : -Infinity,
  selectCanUndo: (state: RootState) => state.objects.history.length > 0,
  selectCanRedo: (state: RootState) => state.objects.future.length > 0,
};

export const objectsActions = objectsSlice.actions;

export const duplicateObject =
  (id: string) => (dispatch: AppDispatch, getState: () => RootState) => {
    const { objects } = objectsSelectors.selectObjectsState(getState());
    const original = objects.find((o) => o.id === id);
    if (!original) return;

    const newObj: SceneObject = {
      ...original,
      id: `${Date.now()}`,
      position: [
        original.position[0] + 1,
        original.position[1],
        original.position[2] + 1,
      ],
    };
    dispatch(objectsActions.addObject(newObj));
  };

export const duplicateMultipleObjects =
  (ids: Set<string>) => (dispatch: AppDispatch, getState: () => RootState) => {
    const { objects } = objectsSelectors.selectObjectsState(getState());
    const objectsToDuplicate = objects.filter((o) => ids.has(o.id));

    const duplicates: SceneObject[] = objectsToDuplicate.map((original) => ({
      ...original,
      id: `${Date.now()}-${Math.random()}`,
      position: [
        original.position[0] + 1,
        original.position[1],
        original.position[2] + 1,
      ],
    }));

    dispatch(objectsActions.addObjects(duplicates));
    return duplicates;
  };

export default objectsSlice.reducer;
