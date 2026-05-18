import { useQuery, useQueries, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
  getCategories,
  getCatalogItems,
  getCatalogItemOptions,
  getCatalogItemOptionsByIds,
  getFloorMaterials,
} from "@/services/api/catalogUrl";
import type {
  CatalogCategoriesRes,
  CatalogItemsRes,
  CatalogItemOptionsRes,
  CatalogListItem,
  TCatalogItemDetail,
} from "@/types/api";
import type { FloorMaterial } from "@/types/global";

/** Fetch all catalog categories. Treated as effectively static data. */
export function useCatalogCategories() {
  return useQuery<CatalogCategoriesRes>({
    queryKey: queryKeys.catalogCategories,
    queryFn: getCategories,
    staleTime: Infinity,
  });
}

/**
 * Fetch items for a specific category.
 * Pass `enabled: false` to skip the request until the accordion section is opened.
 */
export function useCatalogItems(
  categoryId: string,
  options: { enabled?: boolean } = {},
) {
  const queryClient = useQueryClient();
  return useQuery<CatalogItemsRes>({
    queryKey: queryKeys.catalogItems(categoryId),
    queryFn: async () => {
      const data = await getCatalogItems({ categoryId, limit: 100, offset: 0 });
      // Seed individual item caches so useCatalogItem hits cache on first select — no extra request
      data.items.forEach((item) => {
        queryClient.setQueryData(queryKeys.catalogItemById(item.id), item);
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: options.enabled ?? true,
  });
}

/**
 * Fetch variant options for a specific catalog item.
 * Pass `enabled: false` to defer the request (e.g. until an object is selected).
 */
export function useCatalogItemOptions(
  itemId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery<CatalogItemOptionsRes>({
    queryKey: queryKeys.catalogItemOptions(itemId),
    queryFn: () => getCatalogItemOptions(itemId),
    staleTime: 10 * 60 * 1000,
    enabled: options.enabled ?? true,
  });
}

/**
 * Fetch variant options for multiple catalog items in a single request.
 * Returns a map keyed by catalogItemId for easy lookup in views.
 */
export function useCatalogItemOptionsByIds(
  ids: string[],
  options: { enabled?: boolean } = {},
) {
  const stableIds = [...new Set(ids.filter(Boolean))].sort();

  return useQuery<Map<string, number>>({
    queryKey: queryKeys.catalogItemOptionsByIds(stableIds),
    queryFn: async () => {
      if (stableIds.length === 0) return new Map();
      const response = await getCatalogItemOptionsByIds(stableIds);
      const priceByCatalogItemId = new Map<string, number>();
      response.forEach((itemOptions) => {
        priceByCatalogItemId.set(itemOptions.id, itemOptions.priceCents);
      });
      return priceByCatalogItemId;
    },
    staleTime: 5 * 60 * 1000,
    enabled: (options.enabled ?? true) && stableIds.length > 0,
  });
}

/**
 * Fetch all catalog items (no category filter) for cross-category search.
 * Only enabled when a search query is active.
 */
export function useCatalogAllItems(
  options: { search?: string; enabled?: boolean } = {},
) {
  const { search = "", enabled } = options;
  const queryClient = useQueryClient();
  return useQuery<CatalogItemsRes>({
    queryKey: queryKeys.catalogAllItems(search),
    queryFn: async () => {
      const data = await getCatalogItems({
        search: search || undefined,
        limit: 200,
        offset: 0,
      });
      data.items.forEach((item) => {
        queryClient.setQueryData(queryKeys.catalogItemById(item.id), item);
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: enabled ?? true,
  });
}

/** Fetch a single catalog item by UUID. */
export function useCatalogItem(
  id: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery<CatalogListItem | null>({
    queryKey: queryKeys.catalogItemById(id),
    queryFn: () =>
      getCatalogItems({ id, limit: 1, offset: 0 }).then(
        (res) => res.items[0] ?? null,
      ),
    staleTime: 5 * 60 * 1000,
    enabled: (options.enabled ?? true) && !!id,
  });
}

/**
 * Fetch a batch of catalog items by UUID (used for the Favorites tab).
 * Issues one query per ID in parallel via useQueries.
 */
export function useCatalogItemsBatch(ids: string[]) {
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.catalogItemById(id),
      queryFn: () =>
        getCatalogItems({ id, limit: 1, offset: 0 }).then(
          (res) => res.items[0] ?? null,
        ),
      staleTime: 5 * 60 * 1000,
      enabled: !!id,
    })),
  });

  return results;
}

/**
 * Fetch full catalog item details for multiple items in a single batch request.
 * Returns a map keyed by catalogItemId for easy lookup.
 */
export function useCatalogItemDetailsByIds(
  ids: string[],
  options: { enabled?: boolean } = {},
) {
  const stableIds = [...new Set(ids.filter(Boolean))].sort();

  return useQuery<Map<string, TCatalogItemDetail>>({
    queryKey: queryKeys.catalogItemDetailsByIds(stableIds),
    queryFn: async () => {
      if (stableIds.length === 0) return new Map();
      const response = await getCatalogItemOptionsByIds(stableIds);
      const map = new Map<string, TCatalogItemDetail>();
      response.forEach((item) => map.set(item.id, item));
      return map;
    },
    staleTime: 5 * 60 * 1000,
    enabled: (options.enabled ?? true) && stableIds.length > 0,
  });
}

/** Fetch all floor materials from the catalog. Treated as effectively static data. */
export function useFloorMaterials() {
  const { data, isLoading, isError } = useQuery<FloorMaterial[]>({
    queryKey: queryKeys.catalogFloors,
    queryFn: getFloorMaterials,
    staleTime: Infinity,
  });
  return { floorMaterials: data ?? [], isLoading, isError };
}
