import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { AppDispatch } from "@/states/store";
import { GroupsSliceType, Group } from "./types";

const MAX_GROUPS_HISTORY = 50;

type GroupsHistoryEntry = {
  ts: number;
  groups: Group[];
  objectToGroupMap: Record<string, string>;
};

const cloneGroupsState = (
  state: GroupsSliceType,
): { groups: Group[]; objectToGroupMap: Record<string, string> } => ({
  groups: state.groups.map((g) => ({ ...g, objectIds: [...g.objectIds] })),
  objectToGroupMap: { ...state.objectToGroupMap },
});

const pushGroupsHistory = (state: GroupsSliceType) => {
  (state.history as GroupsHistoryEntry[]).push({
    ts: Date.now(),
    ...cloneGroupsState(state),
  });
  if (state.history.length > MAX_GROUPS_HISTORY) state.history.shift();
  state.future = [];
};

const initialState: GroupsSliceType = {
  groups: [],
  objectToGroupMap: {},
  history: [],
  future: [],
};

// Group color palette for visual distinction
const GROUP_COLORS = [
  "#3b82f6", // Blue
  "#10b981", // Green
  "#8b5cf6", // Purple
  "#f59e0b", // Amber
  "#ef4444", // Red
  "#06b6d4", // Cyan
  "#ec4899", // Pink
  "#84cc16", // Lime
  "#f97316", // Orange
  "#6366f1", // Indigo
];

let groupCounter = 1;

// Helper function to get next available group color
function getNextGroupColor(existingGroups: Group[]): string {
  const usedColors = new Set(existingGroups.map((g) => g.color));
  const availableColor = GROUP_COLORS.find((color) => !usedColors.has(color));
  return (
    availableColor || GROUP_COLORS[existingGroups.length % GROUP_COLORS.length]
  );
}

// Create a new group from selected objects
function createGroupReducer(
  state: GroupsSliceType,
  payload: { objectIds: string[]; id: string; createdAt: number },
) {
  const { objectIds, id, createdAt } = payload;
  if (objectIds.length < 2) {
    console.warn("⚠️ Cannot create group with less than 2 objects");
    return null;
  }

  const { groups, objectToGroupMap } = state;

  // Remove objects from existing groups
  const newObjectToGroupMap = { ...objectToGroupMap };
  const affectedGroupIds = new Set<string>();

  objectIds.forEach((objectId) => {
    if (newObjectToGroupMap[objectId]) {
      affectedGroupIds.add(newObjectToGroupMap[objectId]);
      delete newObjectToGroupMap[objectId];
    }
  });

  // Remove affected groups if they're now empty or have only 1 member
  let updatedGroups = groups
    .map((group) => {
      if (affectedGroupIds.has(group.id)) {
        const remainingMembers = group.objectIds.filter(
          (id) => !objectIds.includes(id),
        );
        if (remainingMembers.length < 2) {
          // Dissolve this group
          remainingMembers.forEach((id) => delete newObjectToGroupMap[id]);
          return null; // Mark for removal
        } else {
          // Update group with remaining members (immutable)
          return { ...group, objectIds: remainingMembers };
        }
      }
      return group;
    })
    .filter((group) => group !== null) as Group[];

  // Create new group
  const newGroup: Group = {
    id,
    name: `Group ${groupCounter++}`,
    objectIds: [...objectIds],
    color: getNextGroupColor(updatedGroups),
    createdAt,
  };

  updatedGroups = [...updatedGroups, newGroup];

  // Update object to group map
  objectIds.forEach((objectId) => {
    newObjectToGroupMap[objectId] = newGroup.id;
  });

  state.groups = updatedGroups;
  state.objectToGroupMap = newObjectToGroupMap;

  return newGroup.id;
}

// Ungroup (dissolve) a group by ID
function ungroupReducer(state: GroupsSliceType, groupId: string) {
  const { groups, objectToGroupMap } = state;

  const groupToRemove = groups.find((g) => g.id === groupId);
  if (!groupToRemove) {
    console.warn("⚠️ Group not found:", groupId);
    return;
  }

  // Remove group
  const updatedGroups = groups.filter((g) => g.id !== groupId);

  // Remove objects from map
  const newObjectToGroupMap = { ...objectToGroupMap };
  groupToRemove.objectIds.forEach((objectId) => {
    delete newObjectToGroupMap[objectId];
  });

  state.groups = updatedGroups;
  state.objectToGroupMap = newObjectToGroupMap;
}

// Ungroup multiple groups at once
function ungroupMultipleReducer(state: GroupsSliceType, groupIds: string[]) {
  const { groups, objectToGroupMap } = state;

  const groupsToRemove = groups.filter((g) => groupIds.includes(g.id));
  const updatedGroups = groups.filter((g) => !groupIds.includes(g.id));

  const newObjectToGroupMap = { ...objectToGroupMap };
  groupsToRemove.forEach((group) => {
    group.objectIds.forEach((objectId) => {
      delete newObjectToGroupMap[objectId];
    });
  });

  state.groups = updatedGroups;
  state.objectToGroupMap = newObjectToGroupMap;
}

// Rename a group
function renameGroupReducer(
  state: GroupsSliceType,
  payload: { groupId: string; newName: string },
) {
  const { groupId, newName } = payload;
  const { groups, objectToGroupMap } = state;

  const updatedGroups = groups.map((group) =>
    group.id === groupId ? { ...group, name: newName } : group,
  );

  state.groups = updatedGroups;
  state.objectToGroupMap = objectToGroupMap;
}

// Remove objects from their groups (when objects are deleted)
function removeObjectsFromGroupsReducer(
  state: GroupsSliceType,
  objectIds: string[],
) {
  const { groups, objectToGroupMap } = state;

  const newObjectToGroupMap = { ...objectToGroupMap };
  const affectedGroupIds = new Set<string>();

  objectIds.forEach((objectId) => {
    if (newObjectToGroupMap[objectId]) {
      affectedGroupIds.add(newObjectToGroupMap[objectId]);
      delete newObjectToGroupMap[objectId];
    }
  });

  // Update groups and dissolve any with < 2 members
  const updatedGroups = groups
    .map((group) => {
      if (affectedGroupIds.has(group.id)) {
        const remainingMembers = group.objectIds.filter(
          (id) => !objectIds.includes(id),
        );
        return { ...group, objectIds: remainingMembers };
      }
      return group;
    })
    .filter((group) => {
      if (group.objectIds.length < 2) {
        // Dissolve group
        group.objectIds.forEach((id) => delete newObjectToGroupMap[id]);
        return false;
      }
      return true;
    });

  state.groups = updatedGroups;
  state.objectToGroupMap = newObjectToGroupMap;
}

const groupsSlice = createSlice({
  name: "groups",
  initialState,
  reducers: {
    updateGroupsValue(state, action: PayloadAction<Partial<GroupsSliceType>>) {
      Object.assign(state, action.payload);
    },
    createGroup(
      state,
      action: PayloadAction<{
        objectIds: string[];
        id: string;
        createdAt: number;
      }>,
    ) {
      pushGroupsHistory(state);
      createGroupReducer(state, action.payload);
    },
    ungroup(state, action: PayloadAction<string>) {
      pushGroupsHistory(state);
      ungroupReducer(state, action.payload);
    },
    ungroupMultiple(state, action: PayloadAction<string[]>) {
      pushGroupsHistory(state);
      ungroupMultipleReducer(state, action.payload);
    },
    renameGroup(
      state,
      action: PayloadAction<{ groupId: string; newName: string }>,
    ) {
      renameGroupReducer(state, action.payload);
    },
    removeObjectsFromGroups(state, action: PayloadAction<string[]>) {
      removeObjectsFromGroupsReducer(state, action.payload);
    },
    undo(state) {
      const entry = state.history.pop() as GroupsHistoryEntry | undefined;
      if (!entry) return;
      (state.future as GroupsHistoryEntry[]).push({
        ts: entry.ts,
        ...cloneGroupsState(state),
      });
      if (state.future.length > MAX_GROUPS_HISTORY) state.future.shift();
      state.groups = entry.groups;
      state.objectToGroupMap = entry.objectToGroupMap;
    },
    redo(state) {
      const entry = state.future.pop() as GroupsHistoryEntry | undefined;
      if (!entry) return;
      (state.history as GroupsHistoryEntry[]).push({
        ts: entry.ts,
        ...cloneGroupsState(state),
      });
      if (state.history.length > MAX_GROUPS_HISTORY) state.history.shift();
      state.groups = entry.groups;
      state.objectToGroupMap = entry.objectToGroupMap;
    },
  },
});

export const groupsSelectors = {
  selectGroups: (state: RootState) => state.groups,
  selectObjectGroupId:
    (objectId: string) =>
    (state: RootState): string | null =>
      state.groups.objectToGroupMap[objectId] || null,
  selectGroupById:
    (groupId: string) =>
    (state: RootState): Group | null =>
      state.groups.groups.find((g) => g.id === groupId) || null,
  selectLastHistoryTs: (state: RootState) =>
    state.groups.history.length > 0
      ? state.groups.history[state.groups.history.length - 1].ts
      : -Infinity,
  selectLastFutureTs: (state: RootState) =>
    state.groups.future.length > 0
      ? state.groups.future[state.groups.future.length - 1].ts
      : -Infinity,
  selectCanUndo: (state: RootState) => state.groups.history.length > 0,
  selectCanRedo: (state: RootState) => state.groups.future.length > 0,
};

export const groupsActions = groupsSlice.actions;

export const createGroup = (objectIds: string[]) => (dispatch: AppDispatch) => {
  const id = `group-${Date.now()}`;
  const createdAt = Date.now();
  dispatch(groupsActions.createGroup({ objectIds, id, createdAt }));
  return id;
};

export default groupsSlice.reducer;
