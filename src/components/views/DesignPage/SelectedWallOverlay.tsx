"use client";

import React, { useState } from "react";
import { X, Info } from "lucide-react";
import { useWalls, useUpdateWall } from "@/states/slices/walls/hooks";
import {
  useIsWallEditMode,
  useSelectedWallId,
  useSelectWall,
  useWallDefaults,
  useSetWallDefaults,
} from "@/states/slices/wallEditor/hooks";

interface NumberInputProps {
  label: string;
  live: number;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onCommit: (value: number) => void;
}

function NumberInput({
  label,
  live,
  min,
  max,
  step = 0.1,
  unit,
  onCommit,
}: NumberInputProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const displayValue = editing ? draft : live.toFixed(2);
  const isDirty = editing && draft !== live.toFixed(2);

  const commit = () => {
    const parsed = parseFloat(draft);
    if (!isNaN(parsed)) {
      const clamped =
        min !== undefined && max !== undefined
          ? Math.min(max, Math.max(min, parsed))
          : parsed;
      if (clamped !== live) onCommit(clamped);
    }
    setEditing(false);
  };

  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-(--secondary-color) last:border-0">
      <span className="text-[11px] shrink-0">{label}</span>
      <div className="flex items-center gap-1">
        <input
          type="number"
          step={step}
          min={min}
          max={max}
          value={displayValue}
          onChange={(e) => {
            if (editing) setDraft(e.target.value);
          }}
          onFocus={() => {
            setDraft(live.toFixed(2));
            setEditing(true);
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") {
              commit();
              e.currentTarget.blur();
            } else if (e.key === "Escape") {
              setEditing(false);
              e.currentTarget.blur();
            }
          }}
          className={
            "w-16 bg-transparent border-b font-mono text-[11px] outline-none text-right pr-0.5 " +
            (isDirty
              ? "border-(--primary-color) text--primary-color)"
              : "border-transparent text-(--primary-color)/80 hover:border-(--primary-color) focus:border-(--primary-color)")
          }
        />
        {unit && <span className="text-zinc-400 text-[10px] w-4">{unit}</span>}
      </div>
    </div>
  );
}

export default function SelectedWallOverlay() {
  const [open, setOpen] = useState(true);
  const isWallEditMode = useIsWallEditMode();
  const selectedWallId = useSelectedWallId();
  const selectWall = useSelectWall();
  const walls = useWalls();
  const updateWall = useUpdateWall();
  const wallDefaults = useWallDefaults();
  const setWallDefaults = useSetWallDefaults();

  // Reset open state when a different wall is selected
  const [lastWallId, setLastWallId] = useState<string | null>(null);
  if (selectedWallId !== lastWallId) {
    setLastWallId(selectedWallId);
    if (selectedWallId !== null) setOpen(true);
  }

  if (!isWallEditMode) return null;

  // No wall selected → show the drawing defaults panel
  if (!selectedWallId) {
    return (
      <div
        className={
          "bg-white rounded-xl shadow-(--shadow-style) transition-all duration-300 overflow-hidden " +
          (open ? "w-60" : "w-11 h-11 flex items-center justify-center")
        }
        style={{ border: "var(--border-style)" }}
      >
        {open ? (
          <div className="p-4">
            <div className="flex items-start justify-between mb-1">
              <div>
                <h2 className="text-sm font-semibold text-(--secondary-color) leading-tight">
                  Tường mặc định
                </h2>
                <p className="text-[10px] mt-0.5 text-(--secondary-color)/60">
                  Áp dụng cho tường vẽ tiếp theo
                </p>
              </div>
              <button
                aria-label="Collapse defaults"
                onClick={() => setOpen(false)}
                className="ml-2 p-1 rounded-md text-(--secondary-color) hover:text-white hover:bg-(--primary-color) transition-colors"
              >
                <X size={13} />
              </button>
            </div>
            <div className="border-t border-(--secondary-color)/20 mt-2 pt-3 space-y-0">
              <NumberInput
                label="Độ dày"
                live={wallDefaults.thickness}
                min={0.1}
                max={1.0}
                step={0.05}
                unit="m"
                onCommit={(v) => setWallDefaults({ thickness: v })}
              />
              <NumberInput
                label="Chiều cao"
                live={wallDefaults.height}
                min={2.0}
                max={5.0}
                step={0.1}
                unit="m"
                onCommit={(v) => setWallDefaults({ height: v })}
              />
            </div>
            <p className="mt-3 text-[9px] text-(--secondary-color)/50 text-center">
              Enter hoặc Tab để xác nhận · Esc để hoàn tác
            </p>
          </div>
        ) : (
          <button
            aria-label="Expand defaults"
            onClick={() => setOpen(true)}
            className="w-full h-full flex items-center justify-center text-(--secondary-color) hover:text-white hover:bg-(--primary-color) rounded-xl transition-colors"
          >
            <Info size={14} />
          </button>
        )}
      </div>
    );
  }

  const wall = walls.find((w) => w.id === selectedWallId);
  if (!wall) return null;

  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const length = Math.sqrt((ex - sx) ** 2 + (ez - sz) ** 2);

  return (
    <div>
      <div
        className={
          "bg-white rounded-xl shadow-(--shadow-style) transition-all duration-300 overflow-hidden " +
          (open ? "w-60" : "w-11 h-11 flex items-center justify-center")
        }
        style={{ border: "var(--border-style)" }}
      >
        {open ? (
          <div className="p-4">
            {/* Header */}
            <div className="flex items-start justify-between mb-1">
              <div>
                <h2 className="text-sm font-semibold text-(--secondary-color) leading-tight">
                  Tường
                </h2>
                <p className="text-[10px] mt-0.5">{length.toFixed(2)} m</p>
              </div>
              <button
                aria-label="Collapse wall details"
                onClick={() => setOpen(false)}
                className="ml-2 p-1 rounded-md text-(--secondary-color) hover:text-white hover:bg-(--primary-color) transition-colors"
              >
                <X size={13} />
              </button>
            </div>

            <div className="border-t border-(--secondary-color)/20 mt-2 pt-3 space-y-0">
              {/* Color */}
              <div className="flex items-center justify-between py-1.5 border-b border-(--secondary-color)">
                <span className="text-[11px]">Màu sắc</span>
                <label className="cursor-pointer flex items-center gap-2">
                  <span
                    className="inline-block w-5 h-5 rounded-md shadow-(--shadow-style)"
                    style={{
                      backgroundColor: wall.color,
                      border: "var(--border-style)",
                    }}
                  />
                  <input
                    type="color"
                    value={wall.color}
                    onChange={(e) =>
                      updateWall(wall.id, { color: e.target.value })
                    }
                    className="sr-only"
                  />
                  <span className="text-[10px] font-mono text-black">
                    {wall.color}
                  </span>
                </label>
              </div>

              {/* Length */}
              <NumberInput
                label="Chiều dài"
                live={length}
                min={0.1}
                step={0.1}
                unit="m"
                onCommit={(newLength) => {
                  const [sx, sz] = wall.startPoint;
                  const [ex, ez] = wall.endPoint;
                  const dx = ex - sx;
                  const dz = ez - sz;
                  const ratio = newLength / length;
                  updateWall(wall.id, {
                    endPoint: [sx + dx * ratio, sz + dz * ratio],
                  });
                }}
              />

              {/* Thickness & Height */}
              <NumberInput
                label="Độ dày"
                live={wall.thickness}
                min={0.1}
                max={1.0}
                step={0.05}
                unit="m"
                onCommit={(v) => updateWall(wall.id, { thickness: v })}
              />
              <NumberInput
                label="Chiều cao"
                live={wall.height}
                min={2.0}
                max={5.0}
                step={0.1}
                unit="m"
                onCommit={(v) => updateWall(wall.id, { height: v })}
              />
            </div>

            <p className="mt-3 text-[9px] text-(--secondary-color)/50 text-center">
              Enter hoặc Tab để xác nhận · Esc để hoàn tác
            </p>

            {/* Deselect */}
            <div className="mt-2 pt-2 border-t border-(--secondary-color)/20">
              <button
                onClick={() => selectWall(null)}
                className="w-full text-[11px] text-(--secondary-color) hover:text-(--primary-color) transition-colors text-center py-0.5"
              >
                Bỏ chọn
              </button>
            </div>
          </div>
        ) : (
          <button
            aria-label="Expand wall details"
            onClick={() => setOpen(true)}
            className="w-full h-full flex items-center justify-center text-(--secondary-color) hover:text-white hover:bg-(--primary-color) rounded-xl transition-colors"
          >
            <Info size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
