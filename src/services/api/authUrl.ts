import houseDesignClient from "./houseDesignClient";
import type {
  RegisterReq,
  RegisterRes,
  LoginReq,
  LoginRes,
  RefreshTokenReq,
  RefreshTokenRes,
  LogoutReq,
  LogoutRes,
  ChangePasswordReq,
  ChangePasswordRes,
  GetMeRes,
} from "@/types/api";

// --- Auth --------------------------------------------------------------------

export const register = (body: RegisterReq) =>
  houseDesignClient.post<RegisterRes>("/api/auth/register", body);

export const login = (body: LoginReq) =>
  houseDesignClient.post<LoginRes>("/api/auth/login", body);

/** Requires a valid access token — injected automatically by the request interceptor. */
export const getMe = () => houseDesignClient.get<GetMeRes>("/api/auth/me");

export const refreshToken = (body: RefreshTokenReq) =>
  houseDesignClient.post<RefreshTokenRes>("/api/auth/refresh", body);

export const logout = (body: LogoutReq) =>
  houseDesignClient.post<LogoutRes>("/api/auth/logout", body);

/** Requires a valid access token — injected automatically by the request interceptor. */
export const changePassword = (body: ChangePasswordReq) =>
  houseDesignClient.post<ChangePasswordRes>("/api/auth/change-password", body);
