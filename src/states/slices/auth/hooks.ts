import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { authActions, authSelectors } from "./state";
import type { AuthUser } from "@/types/api";

export const useAuthValue = () => useAppSelector(authSelectors.selectAuth);
export const useAuthUser = () => useAppSelector(authSelectors.selectUser);
export const useAccessToken = () =>
  useAppSelector(authSelectors.selectAccessToken);

export const useInitAuth = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(authActions.initAuth());
  }, [dispatch]);
};

export const useSetCredentials = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (payload: {
      user: AuthUser;
      accessToken: string;
      refreshToken: string;
    }) => {
      dispatch(authActions.setCredentials(payload));
    },
    [dispatch],
  );
};

export const useClearCredentials = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(authActions.clearCredentials());
  }, [dispatch]);
};

export const useIsHydrated = () =>
  useAppSelector(authSelectors.selectIsHydrated);
