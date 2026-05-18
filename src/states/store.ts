import { configureStore } from "@reduxjs/toolkit";
import { enableMapSet } from "immer";

enableMapSet();

import objectsReducer from "./slices/objects/state";
import dragReducer from "./slices/drag/state";
import snappingReducer from "./slices/snapping/state";
import selectionReducer from "./slices/selection/state";
import groupsReducer from "./slices/groups/state";
import clipboardReducer from "./slices/clipboard/state";
import viewReducer from "./slices/view/state";
import wallsReducer from "./slices/walls/state";
import wallEditorReducer from "./slices/wallEditor/state";
import favoritesReducer from "./slices/favorites/state";
import floorReducer from "./slices/floor/state";
import authReducer from "./slices/auth/state";
import projectFiltersReducer from "./slices/projectFilters/state";
import measureReducer from "./slices/measure/state";

export const store = configureStore({
  reducer: {
    objects: objectsReducer,
    drag: dragReducer,
    snapping: snappingReducer,
    selection: selectionReducer,
    groups: groupsReducer,
    clipboard: clipboardReducer,
    view: viewReducer,
    walls: wallsReducer,
    wallEditor: wallEditorReducer,
    favorites: favoritesReducer,
    floor: floorReducer,
    auth: authReducer,
    projectFilters: projectFiltersReducer,
    measure: measureReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      // We intentionally keep some non-serializable values (e.g. Set in selection)
      // to preserve the existing API behavior with minimal component changes.
      serializableCheck: false,
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export type AppStore = typeof store;
