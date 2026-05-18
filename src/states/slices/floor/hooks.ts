import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { floorActions, floorSelectors } from "./state";

export const useGlobalMaterialId = () =>
  useAppSelector(floorSelectors.selectGlobalMaterialId);

export const useRoomMaterials = () =>
  useAppSelector(floorSelectors.selectRoomMaterials);

export const useRoomNames = () =>
  useAppSelector(floorSelectors.selectRoomNames);

export const useRoomDescriptions = () =>
  useAppSelector(floorSelectors.selectRoomDescriptions);

export const useSelectedRoomKey = () =>
  useAppSelector(floorSelectors.selectSelectedRoomKey);

export const useSetGlobalMaterial = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (id: string) => dispatch(floorActions.setGlobalMaterial(id)),
    [dispatch],
  );
};

export const useSetRoomMaterial = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string, materialId: string) =>
      dispatch(floorActions.setRoomMaterial({ key, materialId })),
    [dispatch],
  );
};

export const useClearRoomMaterial = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string) => dispatch(floorActions.clearRoomMaterial(key)),
    [dispatch],
  );
};

export const useSetRoomName = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string, name: string) =>
      dispatch(floorActions.setRoomName({ key, name })),
    [dispatch],
  );
};

export const useSetRoomDescription = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string, description: string) =>
      dispatch(floorActions.setRoomDescription({ key, description })),
    [dispatch],
  );
};

export const useSetSelectedRoomKey = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (key: string | null) => dispatch(floorActions.setSelectedRoomKey(key)),
    [dispatch],
  );
};
