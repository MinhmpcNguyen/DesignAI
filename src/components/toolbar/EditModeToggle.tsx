"use client";

import { BrickWall, Pyramid } from "lucide-react";
import {
  useEditMode,
  useToggleEditMode,
} from "@/states/slices/wallEditor/hooks";
import { useViewMode } from "@/states/slices/view/hooks";

export default function EditModeToggle() {
  const viewMode = useViewMode();
  const editMode = useEditMode();
  const toggleEditMode = useToggleEditMode();

  if (viewMode !== "2D") return null;

  const isWallEditMode = editMode === "walls";

  const activeClass =
    "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-(--primary-color) text-white transition-all";
  const inactiveClass =
    "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-black hover:text-black transition-all";

  return (
    <div className="flex items-center bg-white border border-zinc-200 rounded-xl shadow-sm p-1">
      <button
        onClick={() => !isWallEditMode && toggleEditMode()}
        className={isWallEditMode ? activeClass : inactiveClass}
        title="Chỉnh sửa tường"
      >
        <BrickWall size={14} />
      </button>
      <button
        onClick={() => isWallEditMode && toggleEditMode()}
        className={!isWallEditMode ? activeClass : inactiveClass}
        title="Đặt vật thể"
      >
        <Pyramid size={14} />
      </button>
    </div>
  );
}
