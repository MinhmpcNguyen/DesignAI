import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { FavoritesSliceType } from "./types";

const STORAGE_KEY = "furniture-favorites";

function loadFromStorage(): Set<string> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? new Set<string>(JSON.parse(stored)) : new Set<string>();
  } catch {
    return new Set<string>();
  }
}

function saveToStorage(keys: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...keys]));
  } catch {}
}

const initialState: FavoritesSliceType = {
  favoriteKeys: new Set<string>(),
};

const favoritesSlice = createSlice({
  name: "favorites",
  initialState,
  reducers: {
    initFavorites(state) {
      state.favoriteKeys = loadFromStorage();
    },
    toggleFavoriteKey(state, action: PayloadAction<string>) {
      const key = action.payload;
      const next = new Set(state.favoriteKeys);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      state.favoriteKeys = next;
      saveToStorage(next);
    },
  },
});

export const favoritesActions = favoritesSlice.actions;

export const favoritesSelectors = {
  selectFavorites: (state: RootState) => state.favorites,
};

export default favoritesSlice.reducer;
