import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { Wall, WallsSliceType } from "./types";

const MAX_WALL_HISTORY = 50;

type WallHistoryEntry = { ts: number; walls: Wall[] };

const cloneWalls = (walls: Wall[]): Wall[] =>
  walls.map((w) => ({
    ...w,
    startPoint: [...w.startPoint] as [number, number],
    endPoint: [...w.endPoint] as [number, number],
  }));

const pushWallHistory = (state: WallsSliceType) => {
  (state.history as WallHistoryEntry[]).push({
    ts: Date.now(),
    walls: cloneWalls(state.walls),
  });
  if (state.history.length > MAX_WALL_HISTORY) state.history.shift();
  state.future = [];
};

/**
 * Initial state with a default 5x5m rectangular room
 * Room is centered at origin (0, 0) with walls at ±2.5m
 *
 */
const initialState: WallsSliceType = {
  walls: [
    // North wall (back, -Z direction)
    {
      id: "wall-1",
      startPoint: [-2.5, -2.5],
      endPoint: [2.5, -2.5],
      thickness: 0.2,
      height: 3,
      color: "#e0e0e0",
    },
    // East wall (right, +X direction)
    {
      id: "wall-2",
      startPoint: [2.5, -2.5],
      endPoint: [2.5, 2.5],
      thickness: 0.2,
      height: 3,
      color: "#e0e0e0",
    },
    // South wall (front, +Z direction)
    {
      id: "wall-3",
      startPoint: [2.5, 2.5],
      endPoint: [-2.5, 2.5],
      thickness: 0.2,
      height: 3,
      color: "#e0e0e0",
    },
    // West wall (left, -X direction)
    {
      id: "wall-4",
      startPoint: [-2.5, 2.5],
      endPoint: [-2.5, -2.5],
      thickness: 0.2,
      height: 3,
      color: "#e0e0e0",
    },
  ],
  history: [],
  future: [],
};

const wallsSlice = createSlice({
  name: "walls",
  initialState,
  reducers: {
    /**
     * Add a new wall to the room
     */
    addWall(state, action: PayloadAction<Wall>) {
      pushWallHistory(state);
      state.walls.push(action.payload);
    },
    /**
     * Remove a wall by ID
     */
    removeWall(state, action: PayloadAction<string>) {
      pushWallHistory(state);
      state.walls = state.walls.filter((w) => w.id !== action.payload);
    },
    /**
     * Update a wall's properties (live — does NOT push history; caller owns history via beginWallEdit)
     */
    updateWall(
      state,
      action: PayloadAction<{ id: string; updates: Partial<Wall> }>,
    ) {
      const wall = state.walls.find((w) => w.id === action.payload.id);
      if (wall) {
        Object.assign(wall, action.payload.updates);
      }
    },
    /**
     * Update multiple walls in a single dispatch (live — no history push)
     */
    updateManyWalls(
      state,
      action: PayloadAction<Array<{ id: string; updates: Partial<Wall> }>>,
    ) {
      for (const { id, updates } of action.payload) {
        const wall = state.walls.find((w) => w.id === id);
        if (wall) {
          Object.assign(wall, updates);
        }
      }
    },
    /**
     * Push the current walls to history without mutating them.
     * Call this at the START of a wall drag so the drag's final position
     * is a single undo step.
     */
    beginWallEdit(state) {
      pushWallHistory(state);
    },
    /**
     * Replace all walls (for loading saved designs — no history)
     */
    setWalls(state, action: PayloadAction<Wall[]>) {
      state.walls = action.payload;
    },
    undo(state) {
      const entry = state.history.pop() as WallHistoryEntry | undefined;
      if (!entry) return;
      (state.future as WallHistoryEntry[]).push({
        ts: entry.ts,
        walls: cloneWalls(state.walls),
      });
      if (state.future.length > MAX_WALL_HISTORY) state.future.shift();
      state.walls = entry.walls;
    },
    redo(state) {
      const entry = state.future.pop() as WallHistoryEntry | undefined;
      if (!entry) return;
      (state.history as WallHistoryEntry[]).push({
        ts: entry.ts,
        walls: cloneWalls(state.walls),
      });
      if (state.history.length > MAX_WALL_HISTORY) state.history.shift();
      state.walls = entry.walls;
    },
  },
});

/**
 * Selectors for accessing wall state
 */
export const wallsSelectors = {
  /** Get all walls */
  selectWalls: (state: RootState) => state.walls.walls,
  /** Get a specific wall by ID */
  selectWallById: (id: string) => (state: RootState) =>
    state.walls.walls.find((w) => w.id === id),
  /** Get count of walls */
  selectWallCount: (state: RootState) => state.walls.walls.length,
  selectLastHistoryTs: (state: RootState) =>
    state.walls.history.length > 0
      ? state.walls.history[state.walls.history.length - 1].ts
      : -Infinity,
  selectLastFutureTs: (state: RootState) =>
    state.walls.future.length > 0
      ? state.walls.future[state.walls.future.length - 1].ts
      : -Infinity,
  selectCanUndo: (state: RootState) => state.walls.history.length > 0,
  selectCanRedo: (state: RootState) => state.walls.future.length > 0,
};

export const wallsActions = wallsSlice.actions;

export default wallsSlice.reducer;
