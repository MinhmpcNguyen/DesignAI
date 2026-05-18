"use client";

import {
  useIsWallEditMode,
  useIsDrawing,
  useCancelDrawingWall,
  useStartDrawingWall,
} from "@/states/slices/wallEditor/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import { useDeactivateMeasure } from "@/states/slices/measure/hooks";
import { Pencil } from "lucide-react";

/**
 * DrawWallButton - Button to start/cancel wall drawing mode
 * Only visible in 2D wall edit mode
 */
export default function DrawWallButton() {
  const viewMode = useViewMode();
  const isWallEditMode = useIsWallEditMode();
  const isDrawing = useIsDrawing();
  const startDrawingWall = useStartDrawingWall();
  const cancelDrawingWall = useCancelDrawingWall();
  const deactivateMeasure = useDeactivateMeasure();

  // Only show in 2D wall edit mode
  if (viewMode !== "2D" || !isWallEditMode) {
    return null;
  }

  const handleClick = () => {
    if (isDrawing) {
      // Cancel drawing mode
      cancelDrawingWall();
    } else {
      deactivateMeasure(); // stop measure tool if active
      // Enter drawing mode (but don't set start point yet - that happens on first floor click)
      // Pass null array to indicate "ready to draw" state
      startDrawingWall([0, 0]); // Will be overwritten on first click
    }
  };

  return (
    <button
      onClick={handleClick}
      className={
        "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer " +
        (isDrawing
          ? "bg-(--primary-color) text-white shadow-(--shadow-style)"
          : "bg-(--primary-color) text-white shadow-(--shadow-style)")
      }
      title={
        isDrawing
          ? "Cancel Drawing (or press ESC)"
          : "Start Drawing New Wall (click floor twice)"
      }
    >
      {isDrawing ? (
        <>
          <span className="text-sm leading-none">✕</span>
          <span>Huỷ</span>
        </>
      ) : (
        <>
          <Pencil size={14} />
          <span>Vẽ Tường</span>
        </>
      )}
    </button>
  );
}
