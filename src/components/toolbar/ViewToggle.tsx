"use client";

import { useViewMode, useToggleViewMode } from "@/states/slices/view/hooks";

export default function ViewToggle() {
  const viewMode = useViewMode();
  const toggleViewMode = useToggleViewMode();

  const is2D = viewMode === "2D";

  const activeClass =
    "flex items-center gap-1.5 px-2 py-1 rounded-xl bg-(--primary-color) text-white transition-all";
  const inactiveClass =
    "flex items-center gap-1.5 px-2 py-1 text-(--primary-color) transition-all";

  return (
    <div className="flex items-center bg-[#CFA86629] border border-[#807668] rounded-xl p-1">
      <button
        onClick={() => !is2D && toggleViewMode()}
        className={is2D ? activeClass : inactiveClass}
        title="Góc nhìn 2D"
      >
        <span className="text-[12px] font-light">2D</span>
      </button>
      <button
        onClick={() => is2D && toggleViewMode()}
        className={!is2D ? activeClass : inactiveClass}
        title="Góc nhìn 3D"
      >
        <span className="text-[12px] font-light">3D</span>
      </button>
    </div>
  );
}
