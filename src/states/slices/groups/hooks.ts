import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import { createGroup, groupsActions, groupsSelectors } from "./state";
import type { GroupsSliceType, Group } from "./types";

export const useGroupsValue = (): GroupsSliceType =>
  useAppSelector(groupsSelectors.selectGroups);

export const useUpdateGroups = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (update: Partial<GroupsSliceType>) => {
      dispatch(groupsActions.updateGroupsValue(update));
    },
    [dispatch],
  );
};

export const useCreateGroup = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectIds: string[]) => {
      return dispatch(createGroup(objectIds));
    },
    [dispatch],
  );
};

export const useUngroup = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (groupId: string) => {
      dispatch(groupsActions.ungroup(groupId));
    },
    [dispatch],
  );
};

export const useUngroupMultiple = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (groupIds: string[]) => {
      dispatch(groupsActions.ungroupMultiple(groupIds));
    },
    [dispatch],
  );
};

export const useRenameGroup = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (payload: { groupId: string; newName: string }) => {
      dispatch(groupsActions.renameGroup(payload));
    },
    [dispatch],
  );
};

export const useGetObjectGroupId = () => {
  const { objectToGroupMap } = useGroupsValue();
  return useCallback(
    (objectId: string): string | null => objectToGroupMap[objectId] || null,
    [objectToGroupMap],
  );
};

export const useGetGroupById = () => {
  const { groups } = useGroupsValue();
  return useCallback(
    (groupId: string): Group | null =>
      groups.find((g) => g.id === groupId) || null,
    [groups],
  );
};

export const useRemoveObjectsFromGroups = () => {
  const dispatch = useAppDispatch();
  return useCallback(
    (objectIds: string[]) => {
      dispatch(groupsActions.removeObjectsFromGroups(objectIds));
    },
    [dispatch],
  );
};

/** Returns the group ID that this object belongs to, or null. */
export const useObjectGroupId = (objectId: string): string | null =>
  useAppSelector((state) => state.groups.objectToGroupMap[objectId] ?? null);

/** Returns the Group object for a given groupId, or null. Stable ref when group is unchanged. */
export const useGroupById = (groupId: string | null) =>
  useAppSelector((state) =>
    groupId
      ? (state.groups.groups.find((g) => g.id === groupId) ?? null)
      : null,
  );

/** Returns true when all members of the group are currently selected. */
export const useIsGroupFullySelected = (groupId: string | null): boolean =>
  useAppSelector((state) => {
    if (!groupId) return false;
    const group = state.groups.groups.find((g) => g.id === groupId);
    if (!group) return false;
    return group.objectIds.every((objId) =>
      state.selection.selectedIds.has(objId),
    );
  });

export const useGroupsCanUndo = () =>
  useAppSelector(groupsSelectors.selectCanUndo);

export const useGroupsCanRedo = () =>
  useAppSelector(groupsSelectors.selectCanRedo);
