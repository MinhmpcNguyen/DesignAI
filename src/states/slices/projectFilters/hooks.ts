import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { projectFiltersActions, projectFiltersSelectors } from "./state";

export const useProjectFiltersValue = () =>
  useAppSelector(projectFiltersSelectors.selectProjectFilters);

export const useSetProjectType = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (value: string) => {
      dispatch(projectFiltersActions.setProjectType(value));
    },
    [dispatch],
  );
};

export const useSetAreaRange = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (value: string) => {
      dispatch(projectFiltersActions.setAreaRange(value));
    },
    [dispatch],
  );
};

export const useSetModifiedDate = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (value: string) => {
      dispatch(projectFiltersActions.setModifiedDate(value));
    },
    [dispatch],
  );
};
