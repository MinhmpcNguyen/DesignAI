export type SelectionSliceType = {
  selectedIds: Set<string>;
  isCtrlPressed: boolean; // Track Ctrl key state for multi-select
  primarySelectedId: string | null; // The object that was clicked (shows handle)
};
