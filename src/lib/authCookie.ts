const COOKIE_NAME = "house_design_session";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export function setAuthCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE_NAME}=1; path=/; SameSite=Lax; max-age=${MAX_AGE}`;
}

export function clearAuthCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE_NAME}=; path=/; SameSite=Lax; max-age=0`;
}
