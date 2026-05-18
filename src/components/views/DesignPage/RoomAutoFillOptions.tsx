"use client";

import { X } from "lucide-react";
import {
  useAddMultipleObjects,
  useObjectsValue,
  useRemoveMultipleObjects,
} from "@/states/slices/objects/hooks";
import type { SceneObject } from "@/states/slices/objects/types";
import { useWalls } from "@/states/slices/walls/hooks";
import {
  centroidKey,
  findRoomPolygons,
  isPointInPolygon,
} from "@/lib/roomPolygons";
import type {
  AutoFillOption,
  AutoFillObjectResult,
  AutoFillResult,
} from "@/types/api";

// ---------------------------------------------------------------------------
// Shared helpers — exported so FloorStylePanel can use them for initial placement
// ---------------------------------------------------------------------------
function toPos(
  p: { x: number; y: number; z: number } | [number, number, number],
): [number, number, number] {
  return Array.isArray(p) ? p : [p.x, p.y, p.z];
}

function toRot(
  r:
    | { x: number; y: number; z: number; w: number }
    | [number, number, number, number],
): [number, number, number, number] {
  return Array.isArray(r) ? r : [r.x, r.y, r.z, r.w];
}

export function mapAutoFillItems(
  items: AutoFillObjectResult[],
  roomKey: string,
  prefix: string,
): SceneObject[] {
  const ts = Date.now();
  return items.map((item, i) => ({
    id: `autofill-${roomKey}-${prefix}-${i}-${ts}`,
    name: item.name,
    type: "model" as const,
    position: toPos(item.position),
    rotation: toRot(item.rotation),
    color: item.color,
    size: item.size,
    modelUrl: item.modelUrl,
    placementType:
      item.placementType ??
      (item.objectRole === "door" || item.objectRole === "window"
        ? "wall"
        : "floor"),
    snappedToWall: item.snappedToWall,
    catalogItemId: item.catalogItemId,
    objectRole: item.objectRole ?? undefined,
    collisionLayer: item.collisionLayer,
    placeOn: item.placeOn ?? undefined,
  }));
}

export function canApplyAutoFillOption(option: AutoFillOption): boolean {
  return (
    option.hardValid !== false &&
    option.complete !== false &&
    !option.disabledReason &&
    option.objects.length > 0
  );
}

export type FillRoomState = {
  loading: boolean;
  error: string | null;
  result: AutoFillResult | null;
  placedIds: string[];
  selectedOptionId: string | null;
  panelVisible: boolean;
  stage?: string | null;
  message?: string | null;
};

// ---------------------------------------------------------------------------
// RoomAutoFillOptions
// ---------------------------------------------------------------------------
interface RoomAutoFillOptionsProps {
  roomKey: string;
  fillRoomState: FillRoomState;
  onApplied: (placedIds: string[], selectedOptionId: string) => void;
  onClose: () => void;
}

export default function RoomAutoFillOptions({
  roomKey,
  fillRoomState,
  onApplied,
  onClose,
}: RoomAutoFillOptionsProps) {
  const addMultipleObjects = useAddMultipleObjects();
  const removeMultipleObjects = useRemoveMultipleObjects();
  const { objects } = useObjectsValue();
  const walls = useWalls();

  const handleApplyOption = (option: AutoFillOption) => {
    if (!canApplyAutoFillOption(option)) {
      return;
    }
    const polygons = findRoomPolygons(walls);
    const roomPolygon = polygons.find((p) => centroidKey(p) === roomKey);
    const idsToRemove = roomPolygon
      ? new Set(
          objects
            .filter(
              (o) =>
                o.objectRole !== "door" &&
                o.objectRole !== "window" &&
                isPointInPolygon(o.position[0], o.position[2], roomPolygon),
            )
            .map((o) => o.id),
        )
      : new Set(fillRoomState.placedIds);
    if (idsToRemove.size > 0) {
      removeMultipleObjects(idsToRemove);
    }

    const newObjects = mapAutoFillItems(option.objects, roomKey, "obj");
    const newOpenings = mapAutoFillItems(option.openings, roomKey, "opn");
    const allPlaced = [...newObjects, ...newOpenings];
    addMultipleObjects(allPlaced);

    onApplied(
      allPlaced.map((o) => o.id),
      option.optionId,
    );
  };

  if (!fillRoomState.result) return null;
  const options = fillRoomState.result.options;

  return (
    <div
      className="ml-2 w-64 h-full bg-white rounded-2xl flex flex-col overflow-hidden shadow-(--shadow-style)"
      style={{ border: "var(--border-style)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
        <span className="font-semibold text-sm text-zinc-800">
          Gợi ý nội thất
        </span>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
          aria-label="Đóng"
        >
          <X size={16} />
        </button>
      </div>

      {/* Options list */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {options.length === 0 && (
          <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-3">
            <p className="text-xs font-medium text-zinc-700">
              Chưa có phương án hợp lệ
            </p>
            <p className="mt-1 text-[11px] leading-4 text-zinc-500">
              Các bố cục bị chồng đồ hoặc thiếu vùng thao tác đã bị loại.
            </p>
          </div>
        )}
        {options.map((option) => {
          const isActive = fillRoomState.selectedOptionId === option.optionId;
          const canApply = canApplyAutoFillOption(option);
          const statusLabel = canApply
            ? isActive
              ? "Đang dùng"
              : "Hợp lệ"
            : "Bị loại";
          return (
            <div
              key={option.optionId}
              className={`rounded-xl border-2 p-3 transition-all duration-150 ${
                isActive
                  ? "border-(--primary-color,#C8A882) bg-[#fdf6ee]"
                  : canApply
                    ? "border-zinc-100 bg-zinc-50 hover:border-zinc-200"
                    : "border-zinc-100 bg-zinc-50 opacity-80"
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="text-xs font-semibold text-zinc-800">
                  {option.label ?? option.optionId}
                </span>
                <span
                  className={`text-[10px] font-medium rounded-full px-1.5 py-0.5 shrink-0 ${
                    canApply
                      ? "text-white bg-(--primary-color,#C8A882)"
                      : "text-zinc-500 bg-zinc-200"
                  }`}
                >
                  {statusLabel}
                </span>
              </div>
              <div className="mb-2 flex items-center justify-between text-[10px] text-zinc-500">
                <span>
                  Điểm:{" "}
                  {option.layoutScore !== null && option.layoutScore !== undefined
                    ? option.layoutScore
                    : "--"}
                </span>
                <span>{option.objects.length} món</span>
              </div>
              {!canApply && (
                <p className="mb-2 text-[11px] leading-4 text-zinc-500">
                  {option.disabledReason ??
                    "Phương án này không đạt kiểm tra bố cục."}
                </p>
              )}
              {!isActive && (
                <button
                  type="button"
                  onClick={() => handleApplyOption(option)}
                  disabled={!canApply}
                  className="w-full text-[11px] font-medium rounded-lg py-1.5 bg-(--primary-color,#C8A882) text-white hover:opacity-90 active:scale-95 transition-all duration-150 disabled:bg-zinc-200 disabled:text-zinc-500 disabled:cursor-not-allowed disabled:active:scale-100"
                >
                  {canApply ? "Áp dụng" : "Không thể áp dụng"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
