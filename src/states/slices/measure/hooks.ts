import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { measureActions, measureSelectors } from "./state";
import type { MeasureLine } from "./types";

export const useIsMeasureActive = () =>
  useAppSelector(measureSelectors.selectIsActive);

export const useMeasurePendingStart = () =>
  useAppSelector(measureSelectors.selectPendingStart);

export const useMeasureLines = () =>
  useAppSelector(measureSelectors.selectLines);

export const useActivateMeasure = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(measureActions.activateMeasure());
  }, [dispatch]);
};

export const useDeactivateMeasure = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(measureActions.deactivateMeasure());
  }, [dispatch]);
};

export const useSetMeasurePendingStart = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (point: [number, number]) => {
      dispatch(measureActions.setPendingStart(point));
    },
    [dispatch],
  );
};

export const useCancelMeasurePending = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(measureActions.cancelPending());
  }, [dispatch]);
};

export const useAddMeasureLine = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (line: MeasureLine) => {
      dispatch(measureActions.addMeasureLine(line));
    },
    [dispatch],
  );
};

export const useRemoveMeasureLine = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string) => {
      dispatch(measureActions.removeMeasureLine(id));
    },
    [dispatch],
  );
};

export const useClearAllMeasureLines = () => {
  const dispatch = useAppDispatch();
  return useCallback(() => {
    dispatch(measureActions.clearAllLines());
  }, [dispatch]);
};
