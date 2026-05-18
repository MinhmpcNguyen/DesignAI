import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { viewActions, viewSelectors } from "./state";
import type { ViewSliceType, ViewMode } from "./types";

export const useViewValue = (): ViewSliceType =>
  useAppSelector(viewSelectors.selectView);

export const useViewMode = (): ViewMode =>
  useAppSelector(viewSelectors.selectViewMode);

export const useToggleViewMode = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(viewActions.toggleViewMode());
  }, [dispatch]);
};

export const useSetViewMode = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (mode: ViewMode) => {
      dispatch(viewActions.setViewMode(mode));
    },
    [dispatch],
  );
};

export const useIsAIGenMode = (): boolean =>
  useAppSelector(viewSelectors.selectIsAIGenMode);

export const useSetIsAIGenMode = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (value: boolean) => {
      dispatch(viewActions.setIsAIGenMode(value));
    },
    [dispatch],
  );
};
