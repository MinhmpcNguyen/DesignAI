export interface Group {
  id: string;
  name: string;
  objectIds: string[];
  color: string; // Hex color for group visual distinction
  createdAt: number;
}

export type GroupsSliceType = {
  groups: Group[];
  objectToGroupMap: Record<string, string>; // objectId -> groupId
  history: {
    ts: number;
    groups: Group[];
    objectToGroupMap: Record<string, string>;
  }[];
  future: {
    ts: number;
    groups: Group[];
    objectToGroupMap: Record<string, string>;
  }[];
};
