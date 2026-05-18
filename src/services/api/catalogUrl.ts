import houseDesignClient from "./houseDesignClient";
import { getCatalogModelUrl } from "./baseUrl";
import type {
  CatalogCategoriesRes,
  CatalogItemsRes,
  CatalogItemOptionsRes,
  TCatalogItemDetail,
} from "@/types/api";
import type { FloorMaterial } from "@/types/global";

/** Fetch all catalog categories. Result is stable — staleTime=Infinity recommended. */
export async function getCategories(): Promise<CatalogCategoriesRes> {
  const res = await houseDesignClient.get<CatalogCategoriesRes>(
    "/api/catalog/categories",
  );
  return res.data;
}

export interface GetCatalogItemsParams {
  categoryId?: string;
  /** Fetch a single item by UUID */
  id?: string;
  /** Substring match on item name/nameVn (case-insensitive) */
  search?: string;
  limit?: number;
  offset?: number;
}

/** Fetch catalog items, optionally filtered by categoryId or a single id. */
export async function getCatalogItems(
  params: GetCatalogItemsParams = {},
): Promise<CatalogItemsRes> {
  const { categoryId, id, search, limit = 100, offset = 0 } = params;
  const res = await houseDesignClient.get<CatalogItemsRes>(
    "/api/catalog/items",
    {
      params: {
        ...(categoryId !== undefined && { categoryId }),
        ...(id !== undefined && { id }),
        ...(search !== undefined && { search }),
        limit,
        offset,
      },
    },
  );
  return res.data;
}

/** Fetch variant options for a specific catalog item. */
export async function getCatalogItemOptions(
  catalogItemId: string,
): Promise<CatalogItemOptionsRes> {
  const res = await houseDesignClient.get<CatalogItemOptionsRes>(
    `/api/catalog/items/${encodeURIComponent(catalogItemId)}/options`,
  );
  return res.data;
}

export async function getCatalogItemOptionsByIds(
  catalogItemIds: string[],
): Promise<TCatalogItemDetail[]> {
  const res = await houseDesignClient.post<{ items: TCatalogItemDetail[] }>(
    `/api/catalog/items/batch`,
    { ids: catalogItemIds },
  );
  return res.data.items;
}

interface FloorMaterialApiItem {
  id: string;
  label: string;
  url_image: string;
  note: string | null;
  color: string;
  tile_size: number;
}

/** Fetch all floor materials from the catalog. Result is stable — staleTime=Infinity recommended. */
export async function getFloorMaterials(): Promise<FloorMaterial[]> {
  const res = await houseDesignClient.get<{ floors: FloorMaterialApiItem[] }>(
    "/api/catalog/floors",
  );
  return res.data.floors.map((f) => ({
    id: f.id,
    label: f.label,
    color: f.color,
    textureUrl: getCatalogModelUrl(f.url_image),
    tileSize: f.tile_size,
  }));
}
