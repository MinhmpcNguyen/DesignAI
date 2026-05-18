"use client";

import { Check, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import type { CameraAnglePreset } from "@/types/global";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface CameraAnglesPanelProps {
  cameraAngles: CameraAnglePreset[];
  activeAngleIdx: number;
  onNavigate?: (delta: -1 | 1) => void;
  onToggleSelect?: (idx: number) => void;
}

export default function CameraAnglesPanel({
  cameraAngles,
  activeAngleIdx,
  onNavigate,
  onToggleSelect,
}: CameraAnglesPanelProps) {
  return (
    <Collapsible defaultOpen className="bg-white rounded-md p-4 mb-1.5">
      <CollapsibleTrigger asChild>
        <span className="group text-sm font-semibold mb-2 cursor-pointer flex items-center justify-between w-full">
          <span>Góc chụp</span>
          <ChevronDown className="h-4 w-4 transition-transform duration-200 group-data-[state=open]:rotate-180" />
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="border border-gray-200 rounded-md p-2">
          {/* Navigation row */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => onNavigate?.(-1)}
              className="p-1 rounded hover:bg-gray-100 transition-colors cursor-pointer"
              aria-label="Góc trước"
            >
              <ChevronLeft className="w-4 h-4 text-(--secondary-color)" />
            </button>

            <div className="flex flex-col items-center gap-0.5 text-center">
              <span className="text-[10px] text-(--sub-color) font-mono">
                {activeAngleIdx + 1} / {cameraAngles.length}
              </span>
              <span className="text-xs font-semibold text-(--secondary-color) leading-tight">
                {cameraAngles[activeAngleIdx]?.label}
              </span>
            </div>

            <button
              onClick={() => onNavigate?.(1)}
              className="p-1 rounded hover:bg-gray-100 transition-colors cursor-pointer"
              aria-label="Góc tiếp"
            >
              <ChevronRight className="w-4 h-4 text-(--secondary-color)" />
            </button>

            {/* Checkmark toggle */}
            <button
              onClick={() => onToggleSelect?.(activeAngleIdx)}
              title={
                cameraAngles[activeAngleIdx]?.selected
                  ? "Bỏ chọn"
                  : "Chọn góc này"
              }
              className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold border transition-colors cursor-pointer ${
                cameraAngles[activeAngleIdx]?.selected
                  ? "bg-(--primary-color) border-(--primary-color) text-white"
                  : "border-gray-300 text-(--sub-color) hover:border-(--primary-color) hover:text-(--primary-color)"
              }`}
            >
              <Check className="w-3 h-3" />
              Chọn
            </button>
          </div>

          {/* Dot indicators */}
          <div className="flex justify-center gap-1.5 mt-2">
            {cameraAngles.map((angle, i) => (
              <button
                key={angle.id}
                onClick={() => {
                  const delta =
                    (i - activeAngleIdx + cameraAngles.length) %
                    cameraAngles.length;
                  if (delta !== 0)
                    onNavigate?.(delta <= cameraAngles.length / 2 ? 1 : -1);
                }}
                title={angle.label}
                className="cursor-pointer"
                aria-label={angle.label}
              >
                <div
                  className={`rounded-full transition-all ${
                    i === activeAngleIdx
                      ? "w-2.5 h-2.5 border-2 border-(--primary-color) " +
                        (angle.selected ? "bg-(--primary-color)" : "bg-white")
                      : angle.selected
                        ? "w-2 h-2 bg-(--primary-color)"
                        : "w-2 h-2 bg-gray-300"
                  }`}
                />
              </button>
            ))}
          </div>

          {/* Selection count hint */}
          {cameraAngles.some((a) => a.selected) && (
            <p className="text-[9px] text-center text-(--sub-color) mt-1.5">
              {cameraAngles.filter((a) => a.selected).length} góc được chọn để
              tạo ảnh
            </p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
