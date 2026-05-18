import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  deleteDesign,
  forkDesign,
  getBuildings,
  getCollections,
  getDesign,
  getMyDesigns,
  getTemplates,
  saveDesignHead,
} from "@/services/api/designsUrl";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import { queryKeys } from "./queryKeys";
import type {
  TBuilding,
  TDesignCollection,
  TDesignSnapshot,
  TProjectListItem,
  TTemplateListRes,
} from "@/types/api";
import type { Wall } from "@/states/slices/walls/types";
import type { SceneObject } from "@/states/slices/objects/types";
import { store } from "@/states/store";
import { wallsActions } from "@/states/slices/walls/state";
import { objectsActions } from "@/states/slices/objects/state";
import { floorActions } from "@/states/slices/floor/state";

/** GET /api/designs/collections — fetch all design collections. */
export function useCollections(options: { enabled?: boolean } = {}) {
  return useQuery<TDesignCollection[]>({
    queryKey: queryKeys.collections,
    queryFn: () => getCollections(),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  });
}

/** GET /api/designs/mine — fetch current user's designs. */
export function useMyDesigns(
  options: { enabled?: boolean; status?: string } = {},
) {
  return useQuery<TProjectListItem[]>({
    queryKey: queryKeys.myDesignsByStatus(options.status),
    queryFn: () => getMyDesigns({ status: options.status }),
    enabled: options.enabled ?? true,
  });
}

/** POST /api/designs/fork — forks a project, then refreshes current user's list. */
export function useForkDesign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { title: string; forkFromProjectId?: string }) =>
      forkDesign(payload.title, payload.forkFromProjectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myDesigns });
    },
  });
}

/** PUT /api/designs/{designId}/head — save current scene snapshot. */
export function useSaveDesign() {
  return useMutation({
    mutationFn: ({
      designId,
      payload,
    }: {
      designId: string;
      payload: TDesignSnapshot;
    }) => saveDesignHead(designId, payload),
  });
}

/** GET /api/designs/{designId} — load a design snapshot into Redux. */
export function useLoadDesign(designId: string | null | undefined) {
  const query = useQuery({
    queryKey: queryKeys.designById(designId ?? ""),
    queryFn: () => getDesign(designId as string),
    enabled: Boolean(designId),
  });

  useEffect(() => {
    if (!query.data) return;

    store.dispatch(
      wallsActions.setWalls(query.data.walls as unknown as Wall[]),
    );
    store.dispatch(
      objectsActions.updateObjectsValue({
        objects: (query.data.objects as unknown as SceneObject[]).map((o) => ({
          ...o,
          // Guarantee a stable id so React key props are never undefined
          id: o.id ?? crypto.randomUUID(),
          // Relative paths from the backend must be resolved to the CDN URL
          modelUrl:
            o.modelUrl && !o.modelUrl.startsWith("http")
              ? getCatalogModelUrl(o.modelUrl)
              : o.modelUrl,
        })),
      }),
    );
    if (query.data.rooms && query.data.rooms.length > 0) {
      store.dispatch(floorActions.loadRoomsFromSnapshot(query.data.rooms));
    }
  }, [query.data]);

  return query;
}

/** DELETE /api/designs/{designId} — delete a design and refresh the list. */
export function useDeleteDesign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (designId: string) => deleteDesign(designId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myDesigns });
    },
  });
}

/** GET /api/designs/buildings — list all buildings. Treated as static data. */
export function useBuildings() {
  return useQuery<TBuilding[]>({
    queryKey: queryKeys.buildings,
    queryFn: getBuildings,
    staleTime: Infinity,
  });
}

/** GET /api/designs/templates — fetch all active templates (limit 200). */
export function useTemplates() {
  return useQuery<TTemplateListRes>({
    queryKey: queryKeys.templates,
    queryFn: () => getTemplates({ limit: 200, offset: 0 }),
    staleTime: 5 * 60 * 1000,
  });
}
