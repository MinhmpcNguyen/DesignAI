export const queryKeys = {
  session: (id: string) => ["session", id] as const,
  job: (id: string) => ["job", id] as const,
  me: ["me"] as const,
  catalogCategories: ["catalog", "categories"] as const,
  catalogItems: (categoryId: string) =>
    ["catalog", "items", categoryId] as const,
  catalogItemById: (id: string) => ["catalog", "item", id] as const,
  catalogItemOptions: (itemId: string) =>
    ["catalog", "item-options", itemId] as const,
  catalogItemOptionsByIds: (ids: string[]) =>
    ["catalog", "item-options", "batch", ...ids] as const,
  catalogItemDetailsByIds: (ids: string[]) =>
    ["catalog", "item-details", "batch", ...ids] as const,
  catalogAllItems: (search: string) =>
    ["catalog", "items", "all", search] as const,
  catalogFloors: ["catalog", "floors"] as const,
  myDesigns: ["designs", "mine"] as const,
  myDesignsByStatus: (status?: string) =>
    ["designs", "mine", status ?? "all"] as const,
  designById: (id: string) => ["designs", id] as const,
  buildings: ["designs", "buildings"] as const,
  templates: ["designs", "templates"] as const,
  collections: ["designs", "collections"] as const,
};
