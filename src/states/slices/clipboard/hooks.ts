import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { clipboardActions, clipboardSelectors } from "./state";
import type { ClipboardSliceType } from "./types";
import type { SceneObject } from "../objects/types";

export const useClipboardValue = (): ClipboardSliceType =>
  useAppSelector(clipboardSelectors.selectClipboard);

export const useUpdateClipboard = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (update: Partial<ClipboardSliceType>) => {
      dispatch(clipboardActions.updateClipboardValue(update));
    },
    [dispatch],
  );
};

export const useSetCopiedObjects = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objects: SceneObject[]) => {
      dispatch(clipboardActions.setCopiedObjects(objects));
    },
    [dispatch],
  );
};

export const useSetIsPasting = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (isPasting: boolean) => {
      dispatch(clipboardActions.setIsPasting(isPasting));
    },
    [dispatch],
  );
};
