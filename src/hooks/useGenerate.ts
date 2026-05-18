import { useMutation, useQuery } from "@tanstack/react-query";
import {
  downloadJobResult,
  getJobStatus,
  submitGeneration,
} from "@/services/api/apiUrl";
import type { SubmitGenerationReq } from "@/types/api";
import { queryKeys } from "./queryKeys";

/** POST /sessions/{session_id}/generate — submits the generation job. */
export const useSubmitGeneration = () =>
  useMutation({
    mutationFn: ({
      sessionId,
      body,
    }: {
      sessionId: string;
      body: SubmitGenerationReq;
    }) => submitGeneration(sessionId, body).then((r) => r.data),
  });

/**
 * GET /jobs/{job_id} — polls every 2 s until status is "completed" or "failed".
 * Pass `jobId: undefined` to keep the query disabled.
 */
export const useJobStatus = (jobId: string | undefined) =>
  useQuery({
    queryKey: queryKeys.job(jobId ?? ""),
    queryFn: () => getJobStatus(jobId!).then((r) => r.data),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2_000;
    },
  });

/**
 * GET /jobs/{job_id}/download — fetches the result blob once the job is completed.
 * Use alongside useJobStatus: pass `completed={job?.status === "completed"}`.
 */
export const useDownloadJobResult = (
  jobId: string | undefined,
  completed: boolean,
) =>
  useQuery({
    queryKey: [...queryKeys.job(jobId ?? ""), "download"],
    queryFn: () => downloadJobResult(jobId!).then((r) => r.data),
    enabled: !!jobId && completed,
    staleTime: Infinity,
  });
