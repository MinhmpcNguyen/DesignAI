import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { AuthUser } from "@/types/api";
import type { AuthSliceType } from "./types";

const STORAGE_KEY = "house-design-auth";

interface StoredAuth {
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
}

function loadFromStorage(): Partial<StoredAuth> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredAuth) : {};
  } catch {
    return {};
  }
}

function saveToStorage(data: StoredAuth) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {}
}

function clearFromStorage() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

const initialState: AuthSliceType = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isHydrated: false,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    initAuth(state) {
      const stored = loadFromStorage();
      state.user = stored.user ?? null;
      state.accessToken = stored.accessToken ?? null;
      state.refreshToken = stored.refreshToken ?? null;
      state.isHydrated = true;
    },
    setCredentials(
      state,
      action: PayloadAction<{
        user: AuthUser;
        accessToken: string;
        refreshToken: string;
      }>,
    ) {
      const { user, accessToken, refreshToken } = action.payload;
      state.user = user;
      state.accessToken = accessToken;
      state.refreshToken = refreshToken;
      saveToStorage({ user, accessToken, refreshToken });
    },
    setTokens(
      state,
      action: PayloadAction<{ accessToken: string; refreshToken: string }>,
    ) {
      const { accessToken, refreshToken } = action.payload;
      state.accessToken = accessToken;
      state.refreshToken = refreshToken;
      if (state.user) {
        saveToStorage({ user: state.user, accessToken, refreshToken });
      }
    },
    clearCredentials(state) {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      state.isHydrated = true;
      clearFromStorage();
    },
  },
});

export const authActions = authSlice.actions;

export const authSelectors = {
  selectAuth: (state: RootState) => state.auth,
  selectAccessToken: (state: RootState) => state.auth.accessToken,
  selectRefreshToken: (state: RootState) => state.auth.refreshToken,
  selectUser: (state: RootState) => state.auth.user,
  selectIsHydrated: (state: RootState) => state.auth.isHydrated,
};

export default authSlice.reducer;
