import type {
  TBuilding,
  TDesignCollection,
  TDesignCollectionsRes,
  TDesignSnapshot,
  TProjectListItem,
  TTemplateListRes,
} from "@/types/api";
import houseDesignClient from "./houseDesignClient";

/** Get current user's designs/projects. */
export async function getMyDesigns(params?: {
  status?: string;
}): Promise<TProjectListItem[]> {
  const res = await houseDesignClient.get<{ items: TProjectListItem[] }>(
    "/api/designs/mine",
    { params },
  );

  return res.data.items;
}

/** Fork an existing design by id. */
export async function forkDesign(
  title: string,
  forkFromProjectId?: string,
): Promise<TProjectListItem> {
  const body = forkFromProjectId
    ? {
        title,
        forkFromProjectId,
      }
    : {
        title,
      };

  const res = await houseDesignClient.post<
    TProjectListItem | { design: TProjectListItem }
  >("/api/designs/fork", body);

  // OpenAPI 201 wraps result in { design: ... }; handle both shapes
  const data = res.data as { design?: TProjectListItem } & TProjectListItem;
  return data.design ?? data;
}

/** GET /api/designs/{designId} — load latest project snapshot. */
export async function getDesign(designId: string): Promise<TDesignSnapshot> {
  const res = await houseDesignClient.get<TDesignSnapshot>(
    `/api/designs/${designId}`,
  );
  return res.data;
}

/** PUT /api/designs/{designId}/head — save current project snapshot. */
export async function saveDesignHead(
  designId: string,
  payload: TDesignSnapshot,
): Promise<TDesignSnapshot> {
  const res = await houseDesignClient.put<TDesignSnapshot>(
    `/api/designs/${designId}/head`,
    payload,
  );
  return res.data;
}

/** DELETE /api/designs/{designId} — permanently delete a design. */
export async function deleteDesign(designId: string): Promise<void> {
  await houseDesignClient.delete(`/api/designs/${designId}`);
}

/** GET /api/designs/buildings — list all buildings. */
export async function getBuildings(): Promise<TBuilding[]> {
  const res = await houseDesignClient.get<{ items: TBuilding[] }>(
    "/api/designs/buildings",
  );
  return res.data.items;
}

/** GET /api/designs/collections — list all design collections. */
export async function getCollections(params?: {
  limit?: number;
  offset?: number;
}): Promise<TDesignCollection[]> {
  const res = await houseDesignClient.get<TDesignCollectionsRes>(
    "/api/designs/collections",
    { params },
  );
  return res.data.items;
}

/** GET /api/designs/templates — list active room templates. */
export async function getTemplates(params?: {
  limit?: number;
  offset?: number;
  buildingId?: string;
}): Promise<TTemplateListRes> {
  const res = await houseDesignClient.get<TTemplateListRes>(
    "/api/designs/templates",
    { params },
  );
  return res.data;
}
