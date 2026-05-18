import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSession,
  deleteSession,
  getSession,
} from "@/services/api/apiUrl";
import { queryKeys } from "./queryKeys";

/** POST /sessions — creates a new session and pre-populates the cache. */
export const useCreateSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSession,
    onSuccess: (res) => {
      queryClient.setQueryData(
        queryKeys.session(res.data.session_id),
        res.data,
      );
    },
  });
};

/** GET /sessions/{session_id} */
export const useGetSession = (sessionId: string) =>
  useQuery({
    queryKey: queryKeys.session(sessionId),
    queryFn: () => getSession(sessionId).then((r) => r.data),
    enabled: !!sessionId,
  });

/** DELETE /sessions/{session_id} — also removes the session from cache. */
export const useDeleteSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: (_res, sessionId) => {
      queryClient.removeQueries({ queryKey: queryKeys.session(sessionId) });
    },
  });
};
