import axios, { AxiosError } from "axios";
import { HOUSE_DESIGN_BASE_URL } from "./baseUrl";
import type { ErrorResponse, RefreshTokenRes } from "@/types/api";
import { store } from "@/states/store";
import { authActions } from "@/states/slices/auth/state";
import { clearAuthCookie } from "@/lib/authCookie";

/**
 * Axios instance for the House Design API.
 * Bearer token is injected automatically via the request interceptor.
 * 401 responses trigger a silent token refresh; on failure, credentials are cleared.
 */

const houseDesignClient = axios.create({
  baseURL: HOUSE_DESIGN_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ---------- Token injection --------------------------------------------------

houseDesignClient.interceptors.request.use((config) => {
  const token = store.getState().auth.accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------- 401 silent refresh -----------------------------------------------

let isRefreshing = false;
type QueueEntry = {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
};
let failedQueue: QueueEntry[] = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((entry) => {
    if (error) entry.reject(error);
    else entry.resolve(token!);
  });
  failedQueue = [];
}

houseDesignClient.interceptors.response.use(
  (response) => response,
  async (err: AxiosError<ErrorResponse>) => {
    const originalRequest = err.config as typeof err.config & {
      _retry?: boolean;
    };

    if (err.response?.status !== 401 || originalRequest?._retry) {
      const data = err.response?.data as Record<string, unknown> | undefined;
      const apiMessage =
        (data?.error as string | undefined) ??
        (data?.message as string | undefined);
      const fallback = err.response?.statusText ?? err.message;
      return Promise.reject(new Error(apiMessage ?? fallback));
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({
          resolve: (token) => {
            originalRequest!.headers!.Authorization = `Bearer ${token}`;
            resolve(houseDesignClient(originalRequest!));
          },
          reject,
        });
      });
    }

    originalRequest!._retry = true;
    isRefreshing = true;

    const storedRefreshToken = store.getState().auth.refreshToken;

    try {
      const res = await axios.post<RefreshTokenRes>(
        `${HOUSE_DESIGN_BASE_URL}/api/auth/refresh`,
        { refreshToken: storedRefreshToken },
      );
      const { accessToken, refreshToken } = res.data;

      store.dispatch(authActions.setTokens({ accessToken, refreshToken }));
      processQueue(null, accessToken);

      originalRequest!.headers!.Authorization = `Bearer ${accessToken}`;
      return houseDesignClient(originalRequest!);
    } catch (refreshErr) {
      store.dispatch(authActions.clearCredentials());
      clearAuthCookie();
      processQueue(refreshErr, null);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      return Promise.reject(refreshErr);
    } finally {
      isRefreshing = false;
    }
  },
);

export default houseDesignClient;
