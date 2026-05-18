import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  login,
  register,
  logout,
  changePassword,
  getMe,
} from "@/services/api/authUrl";
import { authActions } from "@/states/slices/auth/state";
import { useAppDispatch } from "@/states/reduxHooks";
import { queryKeys } from "./queryKeys";
import { setAuthCookie, clearAuthCookie } from "@/lib/authCookie";
import type {
  ChangePasswordReq,
  LoginReq,
  LogoutReq,
  RegisterReq,
} from "@/types/api";

/** POST /api/auth/login — stores credentials in Redux + localStorage on success. */
export const useLogin = () => {
  const dispatch = useAppDispatch();
  return useMutation({
    mutationFn: (body: LoginReq) => login(body).then((r) => r.data),
    onSuccess: (data) => {
      dispatch(
        authActions.setCredentials({
          user: data.user,
          accessToken: data.accessToken,
          refreshToken: data.refreshToken,
        }),
      );
      setAuthCookie();
    },
  });
};

/** POST /api/auth/register — stores credentials in Redux + localStorage on success. */
export const useRegister = () => {
  const dispatch = useAppDispatch();
  return useMutation({
    mutationFn: (body: RegisterReq) => register(body).then((r) => r.data),
    onSuccess: (data) => {
      dispatch(
        authActions.setCredentials({
          user: data.user,
          accessToken: data.accessToken,
          refreshToken: data.refreshToken,
        }),
      );
      setAuthCookie();
    },
  });
};

/** POST /api/auth/logout — clears credentials immediately, then revokes the token server-side. */
export const useLogout = () => {
  const dispatch = useAppDispatch();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LogoutReq) => logout(body).then((r) => r.data),
    onMutate: () => {
      dispatch(authActions.clearCredentials());
      clearAuthCookie();
    },
    onSettled: () => {
      queryClient.clear();
    },
  });
};

/** POST /api/auth/change-password */
export const useChangePassword = () =>
  useMutation({
    mutationFn: (body: ChangePasswordReq) =>
      changePassword(body).then((r) => r.data),
  });

/** GET /api/auth/me — fetches the current authenticated user profile. */
export const useCurrentUser = (enabled = true) =>
  useQuery({
    queryKey: queryKeys.me,
    queryFn: () => getMe().then((r) => r.data),
    enabled,
  });
