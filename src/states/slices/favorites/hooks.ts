import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { favoritesActions, favoritesSelectors } from "./state";

export const useFavoritesValue = () =>
  useAppSelector(favoritesSelectors.selectFavorites);

export const useInitFavorites = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(favoritesActions.initFavorites());
  }, [dispatch]);
};

export const useToggleFavorite = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string) => {
      dispatch(favoritesActions.toggleFavoriteKey(key));
    },
    [dispatch],
  );
};
