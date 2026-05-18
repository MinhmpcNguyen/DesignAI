// ── Minimap constants ────────────────────────────────────────────────────────
export const SVG_SIZE = 200;
export const WALL_PAD = 0.2; // 20% padding inside the minimap SVG
export const FOV_LENGTH_PX = 68; // length of the FOV cone in SVG pixels
export const MIN_HEIGHT = 0;
export const MAX_HEIGHT = 3; // metres
export const FOV_MIN = 20; // telephoto
export const FOV_MAX = 100; // ultra wide-angle
export const FOV_STANDARD = 60; // normal perspective

// ── Side-profile constants ───────────────────────────────────────────────────
export const PROFILE_AXIS_X = 155; // x of height axis
export const PROFILE_AXIS_TOP = 14; // y of top tick (MAX_HEIGHT)
export const PROFILE_AXIS_BOT = 146; // y of bottom tick (0mm)
export const PROFILE_CONE_LEN = 90; // elevation cone ray length px
export const PROFILE_CONE_HALF = (20 * Math.PI) / 180; // cosmetic half-angle of cone
