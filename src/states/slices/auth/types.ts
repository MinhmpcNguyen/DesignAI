import type { AuthUser } from "@/types/api";

export interface AuthSliceType {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isHydrated: boolean;
}
