// API types and interfaces

// --- Shared sub-types --------------------------------------------------------

export interface ImageMetadata {
  image_id: string;
  position: number;
  filename: string;
  mime_type: string;
  uploaded_at: string;
}

export interface TurnResponse {
  turn_id: string;
  prompt: string;
  job_id: string;
  result_url: string | null;
  created_at: string;
}

// --- Sessions ----------------------------------------------------------------

// POST /sessions body is intentionally empty (server creates a new session with no input)
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface PostSessionReq {}

export interface PostSessionRes {
  session_id: string;
  created_at: string;
  images: ImageMetadata[];
  history: TurnResponse[];
}

export interface GetSessionRes {
  session_id: string;
  created_at: string;
  images: ImageMetadata[];
  history: TurnResponse[];
}

// --- Images ------------------------------------------------------------------

/** Sent as multipart/form-data — form field name must be "file" */
export interface UploadImageReq {
  file: File;
}

export interface UploadImageRes {
  image_id: string;
  position: number;
  filename: string;
}

// --- Generate ----------------------------------------------------------------

export interface SubmitGenerationReq {
  prompt: string; // required, minLength: 1
  /** Lighting key e.g. 'night_1', 'daylight_2' */
  lighting?: string | null;
  /** Style key e.g. 'wabi_sabi', 'modern' */
  style?: string | null;
  /** Scenery key e.g. 'city', 'countryside' */
  scenery?: string | null;
}

export interface SubmitGenerationRes {
  job_id: string;
  session_id: string;
  status: JobStatus;
}

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface GetJobStatusRes {
  job_id: string;
  status: JobStatus;
  result_url?: string | null;
}

/** Binary blob — use as an <img> src via URL.createObjectURL() */
export type DownloadJobResultRes = Blob;

// --- Wall extraction (Image Gen API) ----------------------------------------

export interface ExtractedWall {
  startPoint: [number, number];
  endPoint: [number, number];
  thickness: number;
  color: string;
  height: number;
}

export interface ExtractWallsRes {
  walls: ExtractedWall[];
}

// --- Errors ------------------------------------------------------------------

export interface ErrorResponse {
  error: string;
  detail?: unknown;
}

// --- Auth (House Design API) -------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
  role: string;
  createdAt: string;
  updatedAt: string;
}

export interface AuthTokensRes {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresInSec: number;
  accessTokenExpiresAt: string;
}

export interface RegisterReq {
  email: string;
  /** minLength: 6 */
  password: string;
  /** minLength: 1, maxLength: 120 */
  displayName: string;
}

export interface RegisterRes extends AuthTokensRes {
  user: AuthUser;
}

export interface LoginReq {
  email: string;
  /** minLength: 6 */
  password: string;
}

/** Identical shape to RegisterRes */
export type LoginRes = RegisterRes;

export interface RefreshTokenReq {
  /** minLength: 16 */
  refreshToken: string;
}

/** Token-only response — no user field */
export type RefreshTokenRes = AuthTokensRes;

export interface LogoutReq {
  /** minLength: 16 */
  refreshToken: string;
}

export interface LogoutRes {
  success: boolean;
  message: string;
}

export interface ChangePasswordReq {
  /** minLength: 6 */
  currentPassword: string;
  /** minLength: 6 */
  newPassword: string;
}

export interface ChangePasswordRes {
  success: boolean;
  message: string;
}

/** OpenAPI declares "Default Response" with no schema — inferred from login/register user shape */
export type GetMeRes = AuthUser;

// --- Catalog (House Design API) ----------------------------------------------

export interface CatalogCategory {
  id: string;
  parentId?: string | null;
  slug: string;
  name: string;
  nameVn?: string;
  iconUrl?: string | null;
  sortOrder?: number;
}

export interface CatalogCategoriesRes {
  categories: CatalogCategory[];
}

/**
 * A single item returned by GET /api/catalog/items.
 * The OpenAPI spec declares `items` as a plain array with no item schema;
 * these fields are inferred from the API and the legacy furniture-catalog.json.
 */
export interface CatalogListItem {
  id: string;
  name: string;
  nameVn?: string;
  description?: string;
  descriptionVn?: string;
  categoryId: string;
  slug?: string;
  /** Relative CDN path — pass to getCatalogModelUrl() to get the full URL. */
  modelUrl: string;
  placementType?: "floor" | "wall" | "ceiling";
  /** [width, height, depth] in metres */
  size?: [number, number, number];
  color?: string;
  objectRole?: string;
  /** Relative CDN path — pass to getCatalogModelUrl() to get the full URL. */
  thumbnailUrl?: string | null;
  /** Returned as a numeric string by the API (e.g. "4.5") */
  rating?: string;
  reviewCount?: number;
}

export interface CatalogItemsRes {
  limit: number;
  offset: number;
  total: number;
  category?: CatalogCategory;
  items: CatalogListItem[];
}

export interface CatalogOptionValue {
  id: string;
  name?: string;
  value: string;
  extraData?: {
    hex?: string;
    size?: [number, number, number];
    [key: string]: unknown;
  };
}

export interface CatalogOption {
  name: string; // API returns "name", not "type"
  values: CatalogOptionValue[];
}

export interface CatalogVariant {
  id: string;
  sku: string;
  priceCents: number;
  stock?: number;
  isDefault?: boolean;
  optionValueIds: string[];
}

export interface CatalogItemOptionsRes {
  catalogItemId: string;
  options: CatalogOption[];
  variants: CatalogVariant[];
  defaultVariant: {
    id: string;
    sku: string;
    priceCents: number;
    stock?: number;
    selectedOptionValueIds: string[];
  };
}

export type TCatalogItemDetail = {
  id: string;
  slug: string;
  skuSlug: string;
  categoryId: string;
  name: string;
  nameVn: string;
  description: string;
  descriptionVn: string;
  modelUrl: string;
  thumbnailUrl: string | null;
  shapeType: string;
  placementType: string;
  size: number[];
  colorDefault: string;
  brand: string;
  rating: string;
  reviewCount: number;
  priceCents: number;
  currency: string;
  defaultVariantSku: string;
};

export type TProjectListItem = {
  id: string;
  title: string;
  roomCounts: {
    bedrooms: number;
    living: number;
    bathrooms: number;
  };
  designStyle: string;
  visibility: string;
  isTemplate: boolean;
  forkedFromProjectId: string | null;
  updatedAt: string;
  status: string;
};

export interface TRoomInfo {
  key: string;
  name: string;
  polygons: [number, number][];
  materialId: string;
  description: string;
  materialLabel: string;
}

/** Snapshot payload for GET /api/designs/{designId} and PUT /api/designs/{designId}/head */
export interface TDesignSnapshot {
  walls: Record<string, unknown>[];
  objects: Record<string, unknown>[];
  area?: number;
  polygon?: [number, number][][];
  rooms?: TRoomInfo[];
}

// --- Buildings & Templates ---------------------------------------------------

export interface TBuilding {
  id: string;
  name: string;
  location: string;
}

export interface TBuildingListRes {
  items: TBuilding[];
}

export interface TTemplateListItem {
  id: string;
  slug: string;
  name: string;
  description: string;
  buildingId: string | null;
  roomCounts: {
    bedrooms: number;
    living: number;
    bathrooms: number;
  };
  designStyle: string;
  updatedAt: string;
  status: string;
  /** All interior room polygons — one per enclosed room. Preferred over polygon for multi-room previews. For 2D previews, use polygon. */
  polygon?: [number, number][][];
}

export interface TTemplateListRes {
  limit: number;
  offset: number;
  total: number;
  count: number;
  items: TTemplateListItem[];
  page: number;
  pageSize: number;
  totalPages: number;
}

// --- Collections -------------------------------------------------------------

export interface TCollectionFloor {
  id: string;
  label: string;
  url_image: string;
  note: string | null;
  color: string | null;
  tile_size: number;
}

export interface TDesignCollection {
  id: string;
  name: string;
  image1Url: string;
  image2Url: string;
  note: string | null;
  /** Schema-free scene objects stored in this collection. */
  objects: Record<string, unknown>[];
  floorId: string | null;
  floor: TCollectionFloor | null;
  createdAt: string;
  updatedAt: string;
}

export interface TDesignCollectionsRes {
  limit: number;
  offset: number;
  total: number;
  count: number;
  items: TDesignCollection[];
}

// --- Auto-fill room furniture -------------------------------------------------

export type AutoFillCollisionLayer =
  | "floor_solid"
  | "floor_underlay"
  | "surface_child"
  | "wall_mounted"
  | "ceiling";

export interface AutoFillPlaceOn {
  target_instance_id: string;
  method: "on_top" | "hang_on" | "lean_on" | "floor";
}

export interface AutoFillObjectResult {
  id?: string;
  name: string;
  size: [number, number, number];
  type: "model";
  color: string;
  modelUrl: string;
  position: { x: number; y: number; z: number } | [number, number, number];
  rotation:
    | { x: number; y: number; z: number; w: number }
    | [number, number, number, number];
  objectRole: string | null;
  catalogItemId: string;
  placementType?: "floor" | "wall" | "ceiling";
  snappedToWall?: string;
  collisionLayer?: AutoFillCollisionLayer;
  placeOn?: AutoFillPlaceOn | null;
}

export interface AutoFillOption {
  optionId: string;
  label: string | null;
  layoutScore: number | null;
  hardValid: boolean | null;
  complete: boolean | null;
  coverageRatio: number | null;
  disabledReason?: string | null;
  objects: AutoFillObjectResult[];
  openings: AutoFillObjectResult[];
}

export interface AutoFillDebugSplitWall {
  id: string;
  startPoint: [number, number];
  endPoint: [number, number];
  height?: number | null;
  thickness?: number | null;
  source?: string | null;
}

export interface AutoFillDebugZone {
  roomId: string;
  roomType: string;
  areaM2?: number | null;
  polygon: [number, number][];
}

export interface AutoFillResult {
  objects: AutoFillObjectResult[];
  openings: AutoFillObjectResult[];
  selectedOptionId: string | null;
  options: AutoFillOption[];
  debugSplitWall?: AutoFillDebugSplitWall | null;
  debugZones?: AutoFillDebugZone[];
}

// --- Normalize-run async job (backend pipeline) --------------------------------

export type NormalizeRunJobStatus = "queued" | "running" | "ready" | "error";

export interface NormalizeRunJobResponse {
  id: string;
  status: NormalizeRunJobStatus;
  statusUrl: string;
  resultUrl: string;
}

export interface NormalizeRunApiError {
  reason: string;
  message: string;
  context?: Record<string, unknown> | null;
}

export interface NormalizeRunStatusResponse {
  id: string;
  status: NormalizeRunJobStatus;
  stage?: string | null;
  message?: string | null;
  progressCurrent?: number | null;
  progressTotal?: number | null;
  error?: NormalizeRunApiError | null;
  statusUrl: string;
  resultUrl: string;
}
