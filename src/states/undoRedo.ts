/**
 * Cross-slice undo / redo thunks.
 *
 * Each slice maintains its own independent history stack. When the user presses
 * Ctrl+Z we pick the slice whose most-recent history entry has the highest
 * timestamp (i.e. the action that happened last) and undo only that slice.
 * This keeps object, wall, and group history correctly interleaved without a
 * single monolithic history.
 *
 * canUndo / canRedo helpers aggregate across all three slices so the toolbar
 * buttons can show a unified disabled state.
 */

import type { AppDispatch, RootState } from "./store";
import { objectsActions, objectsSelectors } from "./slices/objects/state";
import { wallsActions, wallsSelectors } from "./slices/walls/state";
import { groupsActions, groupsSelectors } from "./slices/groups/state";

// ---------------------------------------------------------------------------
// appUndo
// ---------------------------------------------------------------------------
export const appUndo =
  () => (dispatch: AppDispatch, getState: () => RootState) => {
    const state = getState();

    const objTs = objectsSelectors.selectLastHistoryTs(state);
    const wallTs = wallsSelectors.selectLastHistoryTs(state);
    const grpTs = groupsSelectors.selectLastHistoryTs(state);

    const maxTs = Math.max(objTs, wallTs, grpTs);
    if (maxTs === -Infinity) return; // nothing to undo

    // Undo every slice that shares the latest timestamp (within 5ms tolerance
    // to handle simultaneous dispatches like createGroup + addObject).
    const TOLERANCE = 5;
    if (objTs >= maxTs - TOLERANCE) dispatch(objectsActions.undo());
    if (wallTs >= maxTs - TOLERANCE) dispatch(wallsActions.undo());
    if (grpTs >= maxTs - TOLERANCE) dispatch(groupsActions.undo());
  };

// ---------------------------------------------------------------------------
// appRedo
// ---------------------------------------------------------------------------
export const appRedo =
  () => (dispatch: AppDispatch, getState: () => RootState) => {
    const state = getState();

    const objFutureTs = objectsSelectors.selectLastFutureTs(state);
    const wallFutureTs = wallsSelectors.selectLastFutureTs(state);
    const grpFutureTs = groupsSelectors.selectLastFutureTs(state);

    const maxTs = Math.max(objFutureTs, wallFutureTs, grpFutureTs);
    if (maxTs === -Infinity) return; // nothing to redo

    const TOLERANCE = 5;
    if (objFutureTs >= maxTs - TOLERANCE) dispatch(objectsActions.redo());
    if (wallFutureTs >= maxTs - TOLERANCE) dispatch(wallsActions.redo());
    if (grpFutureTs >= maxTs - TOLERANCE) dispatch(groupsActions.redo());
  };

// ---------------------------------------------------------------------------
// Selectors — used by UndoRedoControls for disabled state
// ---------------------------------------------------------------------------
export const selectCanUndo = (state: RootState): boolean =>
  objectsSelectors.selectCanUndo(state) ||
  wallsSelectors.selectCanUndo(state) ||
  groupsSelectors.selectCanUndo(state);

export const selectCanRedo = (state: RootState): boolean =>
  objectsSelectors.selectCanRedo(state) ||
  wallsSelectors.selectCanRedo(state) ||
  groupsSelectors.selectCanRedo(state);
