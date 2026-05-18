import { AUTO_FILL_ROOM_FURNITURE_BASE_URL } from "./baseUrl";
import type {
  AutoFillResult,
  NormalizeRunJobResponse,
  NormalizeRunStatusResponse,
} from "@/types/api";

class ApiResponseError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiResponseError";
  }
}

const DEFAULT_NORMALIZE_RUN_TIMEOUT_MS = 30 * 60 * 1_000;

function formatTimeoutMinutes(timeoutMs: number): string {
  const minutes = Math.max(1, Math.round(timeoutMs / 60_000));
  return `${minutes} phút`;
}

async function checkResponse(res: Response): Promise<void> {
  if (!res.ok) {
    let msg = `Lỗi ${res.status}: ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail?.message) msg = body.detail.message;
      else if (body?.message) msg = body.message;
      else if (typeof body?.detail === "string") msg = body.detail;
    } catch {
      // ignore
    }
    throw new ApiResponseError(msg, res.status);
  }
}

export async function startNormalizeRun(
  payload: unknown,
): Promise<NormalizeRunJobResponse> {
  const res = await fetch(
    `${AUTO_FILL_ROOM_FURNITURE_BASE_URL}/pipeline/normalize-run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  await checkResponse(res);
  return res.json() as Promise<NormalizeRunJobResponse>;
}

export async function getNormalizeRunStatus(
  jobId: string,
): Promise<NormalizeRunStatusResponse> {
  const res = await fetch(
    `${AUTO_FILL_ROOM_FURNITURE_BASE_URL}/pipeline/normalize-run/${encodeURIComponent(jobId)}/status`,
  );
  await checkResponse(res);
  return res.json() as Promise<NormalizeRunStatusResponse>;
}

export async function getNormalizeRunResult(
  jobId: string,
): Promise<AutoFillResult> {
  const res = await fetch(
    `${AUTO_FILL_ROOM_FURNITURE_BASE_URL}/pipeline/normalize-run/${encodeURIComponent(jobId)}/result`,
  );
  await checkResponse(res);
  return res.json() as Promise<AutoFillResult>;
}

/** Poll status until ready/error, then fetch result. */
export async function pollNormalizeRunUntilReady(
  jobId: string,
  onProgress: (status: NormalizeRunStatusResponse) => void,
  intervalMs = 2_000,
  timeoutMs = DEFAULT_NORMALIZE_RUN_TIMEOUT_MS,
): Promise<AutoFillResult> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    let status: NormalizeRunStatusResponse;
    try {
      status = await getNormalizeRunStatus(jobId);
    } catch (err) {
      // 404 means the job record hasn't been flushed to disk yet
      // (Docker Desktop macOS filesystem sync latency). Treat as transient
      // and retry after the normal interval.
      if (err instanceof ApiResponseError && err.status === 404) {
        await new Promise<void>((r) => setTimeout(r, intervalMs));
        continue;
      }
      throw err;
    }
    onProgress(status);
    if (status.status === "ready") {
      return getNormalizeRunResult(jobId);
    }
    if (status.status === "error") {
      throw new Error(status.message ?? "Pipeline thất bại.");
    }
    await new Promise<void>((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Timeout sau ${formatTimeoutMinutes(timeoutMs)} chờ pipeline.`);
}
