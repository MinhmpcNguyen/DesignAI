"use client";

import { Ruler } from "lucide-react";
import { useViewMode } from "@/states/slices/view/hooks";
import {
  useIsMeasureActive,
  useActivateMeasure,
  useDeactivateMeasure,
} from "@/states/slices/measure/hooks";
import { useCancelDrawingWall } from "@/states/slices/wallEditor/hooks";

export default function MeasureTool() {
  const viewMode = useViewMode();
  const isActive = useIsMeasureActive();
  const activate = useActivateMeasure();
  const deactivate = useDeactivateMeasure();
  const cancelDrawingWall = useCancelDrawingWall();

  // Only available in 2D floor plan mode
  if (viewMode !== "2D") return null;

  const handleClick = () => {
    if (isActive) {
      deactivate();
    } else {
      cancelDrawingWall(); // stop wall drawing if active
      activate();
    }
  };

  return (
    <button
      onClick={handleClick}
      className={
        "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer " +
        (isActive
          ? "bg-(--primary-color) text-white shadow-(--shadow-style)"
          : "bg-white text-black shadow-(--shadow-style)")
      }
      title={isActive ? "Thoát đo khoảng cách (ESC)" : "Đo khoảng cách"}
    >
      <Ruler size={14} />
      <span>Đo</span>
    </button>
  );
}
