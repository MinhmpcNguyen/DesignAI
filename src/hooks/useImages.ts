import { useMutation } from "@tanstack/react-query";
import { deleteImage, uploadImage } from "@/services/api/apiUrl";
import type { UploadImageReq } from "@/types/api";

/** POST /sessions/{session_id}/images — uploads an image as multipart/form-data. */
export const useUploadImage = () =>
  useMutation({
    mutationFn: ({
      sessionId,
      body,
    }: {
      sessionId: string;
      body: UploadImageReq;
    }) => uploadImage(sessionId, body).then((r) => r.data),
  });

/** DELETE /sessions/{session_id}/images/{image_id} */
export const useDeleteImage = () =>
  useMutation({
    mutationFn: ({
      sessionId,
      imageId,
    }: {
      sessionId: string;
      imageId: string;
    }) => deleteImage(sessionId, imageId),
  });
