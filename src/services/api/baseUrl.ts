export const IMAGE_GEN_BASE_URL =
  process.env.NEXT_PUBLIC_IMAGE_GEN_API_URL ?? "http://131.153.239.187:5101";
export const HOUSE_DESIGN_BASE_URL =
  process.env.NEXT_PUBLIC_HOUSE_DESIGN_API_URL ?? "http://128.199.87.51:3000";

export const CATALOG_CDN_BASE_URL =
  process.env.NEXT_PUBLIC_CATALOG_CDN_URL ?? "https://storage.mazig.io";

export const AUTO_FILL_ROOM_FURNITURE_BASE_URL =
  process.env.NEXT_PUBLIC_AUTO_FILL_ROOM_FURNITURE_API_URL ??
  "http://localhost:8000";

/**
 * Build a full CDN URL from a relative model path returned by the catalog API.
 * e.g. "catalog/models/organic_wood_bookcase.glb" → "http://storage.mazig.io/catalog/models/organic_wood_bookcase.glb"
 */
export function getCatalogModelUrl(relative: string): string {
  return `${CATALOG_CDN_BASE_URL}/${relative.replace(/^\//, "")}`;
}
