/**
 * Resize configuration — single source of truth for:
 *   1. Which furniture types show drag-resize corner handles (keyword whitelist)
 *   2. Price multipliers per color / material
 *   3. The drag-resize price formula
 *
 * How to update:
 *   • Allow a new furniture type  → add its keyword to RESIZABLE_KEYWORDS
 *   • Disallow a type             → remove its keyword
 *   • Adjust price per color      → add/edit an entry in COLOR_PRICE_MULTIPLIERS
 *   • Adjust price per material   → add/edit an entry in MATERIAL_PRICE_MULTIPLIERS
 *   • Change the formula          → edit calcResizePrice
 */

// ─── Resize whitelist ──────────────────────────────────────────────────────────

/**
 * Object names that contain any of these substrings (case-insensitive) will show
 * drag-resize corner handles. Edit freely — no other file needs to change.
 */
export const RESIZABLE_KEYWORDS: string[] = ["tủ", "bàn", "rèm"];

/**
 * Returns `true` if the object's display name matches a resizable furniture type.
 */
export function isResizable(name?: string): boolean {
  if (!name) return false;
  const lower = name.toLowerCase();
  return RESIZABLE_KEYWORDS.some((kw) => lower.includes(kw));
}

// ─── Price multipliers ─────────────────────────────────────────────────────────

/**
 * Multiply the base price by this factor for a given color option value name.
 * Keys are matched case-insensitively. Missing keys default to 1.0 (no change).
 *
 * Example:
 *   "Vàng đồng": 1.15  → 15 % more expensive when gold color is active
 */
export const COLOR_PRICE_MULTIPLIERS: Record<string, number> = {
  // Add entries here, e.g.:
  // "Trắng": 1.0,
  // "Đen": 1.05,
  // "Vàng đồng": 1.15,
};

/**
 * Multiply the base price by this factor for a given material option value name.
 * Keys are matched case-insensitively. Missing keys default to 1.0.
 *
 * Example:
 *   "Gỗ tự nhiên": 1.3  → 30 % more expensive for solid wood
 */
export const MATERIAL_PRICE_MULTIPLIERS: Record<string, number> = {
  // Add entries here, e.g.:
  // "Gỗ tự nhiên": 1.3,
  // "Gỗ công nghiệp": 1.0,
  // "Nhựa": 0.8,
};

// ─── Price formula ─────────────────────────────────────────────────────────────

/**
 * Mockup formula — calculates a new price in cents after the user drag-resizes an object.
 *
 * Formula:
 *   price = basePriceCents × (newVolume / baseVolume) × colorMultiplier × materialMultiplier
 *
 * @param basePriceCents  Base price in cents, taken from the catalog defaultVariant.
 * @param originalSize    [w, h, d] in meters — the default/original size of the object.
 * @param newSize         [w, h, d] in meters — the size after drag-resize.
 * @param colorName       Active color option value name (optional).
 * @param materialName    Active material option value name (optional).
 * @returns               New price in cents, rounded to nearest integer (minimum 0).
 */
export function calcResizePrice(
  basePriceCents: number,
  originalSize: [number, number, number],
  newSize: [number, number, number],
  colorName?: string,
  materialName?: string,
): number {
  const baseVolume = originalSize[0] * originalSize[1] * originalSize[2];
  const newVolume = newSize[0] * newSize[1] * newSize[2];
  const volumeRatio = baseVolume > 0 ? newVolume / baseVolume : 1;

  const colorKey = colorName?.toLowerCase() ?? "";
  const colorMul =
    Object.entries(COLOR_PRICE_MULTIPLIERS).find(
      ([k]) => k.toLowerCase() === colorKey,
    )?.[1] ?? 1.0;

  const materialKey = materialName?.toLowerCase() ?? "";
  const materialMul =
    Object.entries(MATERIAL_PRICE_MULTIPLIERS).find(
      ([k]) => k.toLowerCase() === materialKey,
    )?.[1] ?? 1.0;

  return Math.max(
    0,
    Math.round(basePriceCents * volumeRatio * colorMul * materialMul),
  );
}
