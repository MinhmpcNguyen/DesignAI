"use client";

import { useEffect, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { Vector3 } from "three";
import {
  useSelectionValue,
  useUpdateSelection,
} from "@/states/slices/selection/hooks";
import { useObjectsValue } from "@/states/slices/objects/hooks";
import { useGroupsValue } from "@/states/slices/groups/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import { useIsWallEditMode } from "@/states/slices/wallEditor/hooks";
import { useDragValue } from "@/states/slices/drag/hooks";
import { useClipboardValue } from "@/states/slices/clipboard/hooks";
import { objectInteractionFlag } from "@/states/objectInteractionFlag";
import type { SceneObject } from "@/states/slices/objects/types";
import type { SelectionSliceType } from "@/states/slices/selection/types";
import type { GroupsSliceType } from "@/states/slices/groups/types";

/** Minimum pixel distance the mouse must travel before a drag is recognised (vs. a click). */
const DRAG_THRESHOLD_PX = 5;

/**
 * Invisible R3F component that implements marquee (rubber-band) drag-to-select.
 *
 * - Active only in **2D** view mode and when not in wall-edit, paste, or catalog-drag mode.
 * - Draws a blue dashed rectangle DOM overlay while dragging.
 * - On release, selects every SceneObject whose XZ center-point projects inside the rectangle.
 * - Group-aware: selecting any member of a group selects the entire group.
 * - Ctrl+drag: adds to current selection; plain drag: replaces selection.
 */
export default function MouseDragSelect() {
  const { camera, gl } = useThree();
  const viewMode = useViewMode();
  const isWallEditMode = useIsWallEditMode();
  const { draggingShape } = useDragValue();
  const { isPasting } = useClipboardValue();

  const { objects } = useObjectsValue();
  const groupsState = useGroupsValue();
  const selectionState = useSelectionValue();
  const updateSelection = useUpdateSelection();

  // Keep latest values in refs so mousedown/mousemove/mouseup closures always
  // read fresh data without needing to re-register the mousedown listener.
  const objectsRef = useRef<SceneObject[]>(objects);
  const groupsRef = useRef<GroupsSliceType>(groupsState);
  const selectionRef = useRef<SelectionSliceType>(selectionState);

  useEffect(() => {
    objectsRef.current = objects;
  }, [objects]);
  useEffect(() => {
    groupsRef.current = groupsState;
  }, [groupsState]);
  useEffect(() => {
    selectionRef.current = selectionState;
  }, [selectionState]);

  // Is this component active for the current interaction state?
  const isActive =
    viewMode === "2D" &&
    !isWallEditMode &&
    draggingShape === null &&
    !isPasting;

  const isActiveRef = useRef(isActive);
  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  useEffect(() => {
    const canvas = gl.domElement;

    // --- DOM marquee rectangle ---
    // Appended to document.body with position:fixed so we don't need to
    // mutate the container's style (which triggers the hooks mutation lint rule).
    const marquee = document.createElement("div");
    marquee.style.cssText = [
      "position:fixed",
      "pointer-events:none",
      "display:none",
      "z-index:9999",
      "border:2px dashed #3b82f6",
      "background:rgba(59,130,246,0.08)",
      "border-radius:2px",
    ].join(";");
    document.body.appendChild(marquee);

    // --- Drag state ---
    let startX = 0;
    let startY = 0; // client coords
    let dragStarted = false;
    const removeMoveUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    // showMarquee uses clientX/clientY directly (fixed-position coordinates)
    const showMarquee = (x1: number, y1: number, x2: number, y2: number) => {
      const left = Math.min(x1, x2);
      const top = Math.min(y1, y2);
      const width = Math.abs(x2 - x1);
      const height = Math.abs(y2 - y1);
      marquee.style.left = `${left}px`;
      marquee.style.top = `${top}px`;
      marquee.style.width = `${width}px`;
      marquee.style.height = `${height}px`;
      marquee.style.display = "block";
    };

    const hideMarquee = () => {
      marquee.style.display = "none";
    };

    // --- Mouse handlers ---
    const onMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return; // left button only
      if (!isActiveRef.current) return;
      if (objectInteractionFlag.active) return; // started on an object

      startX = e.clientX;
      startY = e.clientY;
      dragStarted = false;

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    };

    const onMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      if (!dragStarted) {
        if (
          Math.abs(dx) < DRAG_THRESHOLD_PX &&
          Math.abs(dy) < DRAG_THRESHOLD_PX
        )
          return;
        // If by the time the threshold is crossed a pivot drag is already
        // active, abort — the user is dragging a PivotControls handle, not
        // drawing a marquee.
        if (objectInteractionFlag.active) {
          removeMoveUp();
          dragStarted = false;
          return;
        }
        dragStarted = true;
      }

      // Use raw clientX/clientY — marquee is position:fixed
      showMarquee(startX, startY, e.clientX, e.clientY);
    };

    const onMouseUp = (e: MouseEvent) => {
      removeMoveUp();
      hideMarquee();

      if (!dragStarted) return;

      const rect = canvas.getBoundingClientRect();
      const W = rect.width;
      const H = rect.height;

      // Canvas-local pixel bounds of the marquee (normalised to min/max)
      const rawX1 = startX - rect.left;
      const rawY1 = startY - rect.top;
      const rawX2 = e.clientX - rect.left;
      const rawY2 = e.clientY - rect.top;
      const boxLeft = Math.min(rawX1, rawX2);
      const boxTop = Math.min(rawY1, rawY2);
      const boxRight = Math.max(rawX1, rawX2);
      const boxBottom = Math.max(rawY1, rawY2);

      // Project each object's world position into screen pixels
      const vec = new Vector3();
      const matchedIds = new Set<string>();

      for (const obj of objectsRef.current) {
        vec.set(obj.position[0], obj.position[1], obj.position[2]);
        vec.project(camera);
        // NDC → canvas pixels (Y is flipped: NDC +1 = top, canvas 0 = top)
        const screenX = ((vec.x + 1) / 2) * W;
        const screenY = ((-vec.y + 1) / 2) * H;

        if (
          screenX >= boxLeft &&
          screenX <= boxRight &&
          screenY >= boxTop &&
          screenY <= boxBottom
        ) {
          matchedIds.add(obj.id);
        }
      }

      if (matchedIds.size === 0) {
        // Drag on empty space: clear selection (consistent with click-on-empty)
        if (!e.ctrlKey) {
          updateSelection({ selectedIds: new Set(), primarySelectedId: null });
        }
        return;
      }

      // Group expansion: if a matched object belongs to a group, include all siblings
      const { objectToGroupMap, groups } = groupsRef.current;
      const expanded = new Set<string>(matchedIds);

      for (const id of matchedIds) {
        const groupId = objectToGroupMap[id];
        if (groupId) {
          const grp = groups.find((g) => g.id === groupId);
          if (grp) {
            for (const sibId of grp.objectIds) {
              expanded.add(sibId);
            }
          }
        }
      }

      // Ctrl: add to existing selection; plain drag: replace
      let finalIds: Set<string>;
      if (e.ctrlKey) {
        finalIds = new Set([...selectionRef.current.selectedIds, ...expanded]);
      } else {
        finalIds = expanded;
      }

      const firstId = Array.from(finalIds)[0] ?? null;
      updateSelection({
        selectedIds: finalIds,
        primarySelectedId: firstId,
      });
    };

    canvas.addEventListener("mousedown", onMouseDown);

    return () => {
      canvas.removeEventListener("mousedown", onMouseDown);
      removeMoveUp();
      hideMarquee();
      if (document.body.contains(marquee)) {
        document.body.removeChild(marquee);
      }
    };
  }, [camera, gl, updateSelection]);

  return null;
}
