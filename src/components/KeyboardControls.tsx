"use client";

import { useEffect, useState } from "react";
import {
  useSelectionValue,
  useSetSelectedId,
  useClearSelection,
  useSelectAllObjects,
  useSetCtrlPressed,
} from "@/states/slices/selection/hooks";
import {
  useRemoveObject,
  useDuplicateObject,
  useObjectsValue,
  useRemoveMultipleObjects,
  useDuplicateMultipleObjects,
} from "@/states/slices/objects/hooks";
import {
  useClipboardValue,
  useSetCopiedObjects,
  useSetIsPasting,
} from "@/states/slices/clipboard/hooks";
import {
  useGroupsValue,
  useCreateGroup,
  useUngroup,
  useRemoveObjectsFromGroups,
} from "@/states/slices/groups/hooks";
import {
  useIsWallEditMode,
  useIsDrawing,
  useCancelDrawingWall,
  useSelectedWallId,
  useSelectWall,
} from "@/states/slices/wallEditor/hooks";
import { useRemoveWall } from "@/states/slices/walls/hooks";

/**
 * Global keyboard controls for object manipulation and wall editing
 * Handles: Delete, Escape, Duplicate, Copy/Paste, Multi-select, Group/Ungroup, and other shortcuts
 */
export default function KeyboardControls() {
  const { selectedIds } = useSelectionValue();
  const setSelectedId = useSetSelectedId();
  const clearSelection = useClearSelection();
  const selectAllObjects = useSelectAllObjects();
  const setCtrlPressed = useSetCtrlPressed();

  // Track Shift key state for Ctrl+Shift+G
  const [, setIsShiftPressed] = useState(false);

  // Single object operations
  const removeObject = useRemoveObject();
  const duplicateObject = useDuplicateObject();

  // Multi-object operations
  const removeMultipleObjects = useRemoveMultipleObjects();
  const duplicateMultipleObjects = useDuplicateMultipleObjects();

  // Copy/Paste functionality
  const { objects } = useObjectsValue();
  const { isPasting } = useClipboardValue();
  const setCopiedObjects = useSetCopiedObjects();
  const setIsPasting = useSetIsPasting();

  // Group operations
  const { objectToGroupMap, groups } = useGroupsValue();
  const createGroup = useCreateGroup();
  const ungroup = useUngroup();
  const removeObjectsFromGroups = useRemoveObjectsFromGroups();

  // Wall editor operations
  const isWallEditMode = useIsWallEditMode();
  const isDrawing = useIsDrawing();
  const cancelDrawingWall = useCancelDrawingWall();
  const selectedWallId = useSelectedWallId();
  const selectWall = useSelectWall();
  const removeWall = useRemoveWall();

  // Track Ctrl and Shift key states for multi-select and grouping
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Control" || e.key === "Meta") {
        setCtrlPressed(true);
      }
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Control" || e.key === "Meta") {
        setCtrlPressed(false);
      }
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    // Handle window blur (user switches tabs) - reset key states
    const handleBlur = () => {
      setCtrlPressed(false);
      setIsShiftPressed(false);
    };
    window.addEventListener("blur", handleBlur);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, [setCtrlPressed]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const hasSelection = selectedIds.size > 0;
      const hasMultipleSelection = selectedIds.size > 1;

      // Delete selected wall in wall edit mode
      if (
        (e.key === "Delete" || e.key === "Backspace") &&
        isWallEditMode &&
        selectedWallId
      ) {
        e.preventDefault();
        removeWall(selectedWallId);
        selectWall(null); // Clear wall selection after delete
        return; // Exit early, don't process object deletion
      }

      // Delete selected object(s) (Delete or Backspace)
      if ((e.key === "Delete" || e.key === "Backspace") && hasSelection) {
        e.preventDefault(); // Prevent browser back navigation

        // Check if any selected objects are in groups
        const groupedObjects = Array.from(selectedIds).filter(
          (objectId) => objectToGroupMap[objectId],
        );

        if (groupedObjects.length > 0) {
          // Objects are in groups - ungroup them instead of deleting
          const groupsToUngroup = new Set<string>();
          groupedObjects.forEach((objectId) => {
            const groupId = objectToGroupMap[objectId];
            if (groupId) {
              groupsToUngroup.add(groupId);
            }
          });

          groupsToUngroup.forEach((groupId) => {
            ungroup(groupId);
          });

          return; // Don't delete objects, just ungroup
        }

        // Objects are not in groups - proceed with deletion
        if (hasMultipleSelection) {
          removeMultipleObjects(selectedIds);
        } else {
          const singleId = Array.from(selectedIds)[0];
          removeObject(singleId);
        }
        clearSelection(); // Clear selection after delete
      }

      // Duplicate selected object(s) (Ctrl+D)
      if ((e.ctrlKey || e.metaKey) && e.key === "d" && hasSelection) {
        e.preventDefault(); // Prevent browser bookmark action

        if (hasMultipleSelection) {
          duplicateMultipleObjects(selectedIds);
        } else {
          const singleId = Array.from(selectedIds)[0];
          duplicateObject(singleId);
        }
      }

      // Copy selected object(s) (Ctrl+C)
      if ((e.ctrlKey || e.metaKey) && e.key === "c" && hasSelection) {
        e.preventDefault();

        const objectsToCopy = objects.filter((obj) => selectedIds.has(obj.id));

        if (objectsToCopy.length > 0) {
          setCopiedObjects(objectsToCopy);
        }
      }

      // Paste copied object(s) (Ctrl+V)
      if ((e.ctrlKey || e.metaKey) && e.key === "v") {
        e.preventDefault();
        setIsPasting(true);
      }

      // Select all objects (Ctrl+A)
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        e.preventDefault(); // Prevent browser select all
        const allObjectIds = objects.map((obj) => obj.id);
        selectAllObjects(allObjectIds);
      }

      // Create group from selection (Ctrl+G)
      if (
        (e.ctrlKey || e.metaKey) &&
        e.key === "g" &&
        !e.shiftKey &&
        hasSelection
      ) {
        e.preventDefault();
        if (selectedIds.size < 2) {
          console.warn("⚠️ Select at least 2 objects to create a group");
          return;
        }
        createGroup(Array.from(selectedIds));
      }

      // Ungroup selected groups (Ctrl+Shift+G)
      if (
        (e.ctrlKey || e.metaKey) &&
        e.key === "G" &&
        e.shiftKey &&
        hasSelection
      ) {
        e.preventDefault();

        // Find all groups that contain any of the selected objects
        const groupsToUngroup = new Set<string>();
        Array.from(selectedIds).forEach((objectId) => {
          const groupId = objectToGroupMap[objectId];
          if (groupId) {
            groupsToUngroup.add(groupId);
          }
        });

        if (groupsToUngroup.size === 0) {
          console.warn("⚠️ No grouped objects in selection");
          return;
        }

        // Ungroup all affected groups
        groupsToUngroup.forEach((groupId) => {
          ungroup(groupId);
        });
      }

      // Deselect with Escape key or cancel paste mode
      if (e.key === "Escape") {
        if (isDrawing) {
          cancelDrawingWall();
        } else if (isPasting) {
          setIsPasting(false);
        } else if (isWallEditMode && selectedWallId) {
          selectWall(null);
        } else if (hasSelection) {
          clearSelection();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedIds,
    removeObject,
    removeMultipleObjects,
    clearSelection,
    setSelectedId,
    duplicateObject,
    duplicateMultipleObjects,
    objects,
    setCopiedObjects,
    setIsPasting,
    isPasting,
    isDrawing,
    cancelDrawingWall,
    selectAllObjects,
    createGroup,
    ungroup,
    objectToGroupMap,
    groups,
    removeObjectsFromGroups,
    isWallEditMode,
    selectedWallId,
    selectWall,
    removeWall,
  ]);

  return null; // This component doesn't render anything
}
