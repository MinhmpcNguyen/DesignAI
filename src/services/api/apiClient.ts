import axios, { AxiosError } from "axios";
import { IMAGE_GEN_BASE_URL } from "./baseUrl";
import type { ErrorResponse } from "@/types/api";

/**
 * Axios instance for the image generation service.
 * API key and base URL are read from NEXT_PUBLIC_IMAGE_GEN_API_KEY
 * and NEXT_PUBLIC_IMAGE_GEN_API_URL environment variables.
 */

const apiClient = axios.create({
  baseURL: IMAGE_GEN_BASE_URL,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": process.env.NEXT_PUBLIC_IMAGE_GEN_API_KEY ?? "",
  },
});

// Normalize every error into a plain Error with a human-readable message.
// Picks up the `error` field from the API's ErrorResponse body when available,
// falls back to the HTTP status text, then to the raw Axios message.
apiClient.interceptors.response.use(
  (response) => response,
  (err: AxiosError<ErrorResponse>) => {
    const apiMessage = err.response?.data?.error;
    const fallback = err.response?.statusText ?? err.message;
    return Promise.reject(new Error(apiMessage ?? fallback));
  },
);

export default apiClient;
