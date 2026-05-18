import apiClient from "./apiClient";
import type {
  PostSessionReq,
  PostSessionRes,
  GetSessionRes,
  UploadImageReq,
  UploadImageRes,
  SubmitGenerationReq,
  SubmitGenerationRes,
  GetJobStatusRes,
  DownloadJobResultRes,
  ExtractWallsRes,
} from "@/types/api";

// --- Sessions ----------------------------------------------------------------

export const createSession = (body: PostSessionReq = {}) =>
  apiClient.post<PostSessionRes>("/sessions", body);

export const getSession = (sessionId: string) =>
  apiClient.get<GetSessionRes>(`/sessions/${sessionId}`);

export const deleteSession = (sessionId: string) =>
  apiClient.delete<void>(`/sessions/${sessionId}`);

// --- Images ------------------------------------------------------------------

export const uploadImage = (sessionId: string, body: UploadImageReq) => {
  const form = new FormData();
  form.append("file", body.file);

  return apiClient.post<UploadImageRes>(`/sessions/${sessionId}/images`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deleteImage = (sessionId: string, imageId: string) =>
  apiClient.delete<void>(`/sessions/${sessionId}/images/${imageId}`);

// --- Generate ----------------------------------------------------------------

export const submitGeneration = (
  sessionId: string,
  body: SubmitGenerationReq,
) =>
  apiClient.post<SubmitGenerationRes>(`/sessions/${sessionId}/generate`, body);

export const getJobStatus = (jobId: string) =>
  apiClient.get<GetJobStatusRes>(`/jobs/${jobId}`);

export const downloadJobResult = (jobId: string) =>
  apiClient.get<DownloadJobResultRes>(`/jobs/${jobId}/download`, {
    responseType: "blob",
  });

// --- Wall extraction ---------------------------------------------------------

export const extractWalls = (image: File) => {
  const form = new FormData();
  form.append("image", image);
  return apiClient.post<ExtractWallsRes>("/walls/extract", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
