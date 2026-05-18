"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  X,
  Pencil,
  Check,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useFloorMaterials } from "@/hooks/useCatalog";
import type { FloorMaterial } from "@/types/global";
import {
  useGlobalMaterialId,
  useRoomMaterials,
  useRoomNames,
  useSelectedRoomKey,
  useSetGlobalMaterial,
  useSetRoomMaterial,
  useClearRoomMaterial,
  useSetSelectedRoomKey,
  useSetRoomName,
  useRoomDescriptions,
  useSetRoomDescription,
} from "@/states/slices/floor/hooks";
import { useWalls } from "@/states/slices/walls/hooks";
import {
  useObjectsValue,
  useAddMultipleObjects,
  useRemoveMultipleObjects,
} from "@/states/slices/objects/hooks";
import {
  startNormalizeRun,
  pollNormalizeRunUntilReady,
} from "@/services/api/autoFillUrl";
import type { NormalizeRunStatusResponse } from "@/types/api";
import RoomAutoFillOptions, {
  FillRoomState,
  canApplyAutoFillOption,
  mapAutoFillItems,
} from "./RoomAutoFillOptions";
import {
  findRoomPolygons,
  centroidKey,
  isPointInPolygon,
} from "@/lib/roomPolygons";

interface FloorStylePanelProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// MaterialSwatch — shows texture preview image (or color fallback)
// ---------------------------------------------------------------------------
function MaterialSwatch({
  material,
  isActive,
  onClick,
}: {
  material: FloorMaterial;
  isActive: boolean;
  onClick: () => void;
}) {
  const [imgFailed, setImgFailed] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-1.5 p-1.5 rounded-xl border-2 transition-all duration-150 cursor-pointer
        ${isActive ? "border-(--primary-color,#C8A882) shadow-md scale-105" : "border-transparent hover:border-zinc-200"}`}
    >
      <div className="w-12 h-12 rounded-lg shadow-sm overflow-hidden">
        {material.textureUrl && !imgFailed ? (
          <div className="relative w-full h-full">
            <Image
              src={material.textureUrl}
              alt={material.label}
              fill
              unoptimized
              className="object-cover"
              onError={() => setImgFailed(true)}
            />
          </div>
        ) : (
          <div
            className="w-full h-full"
            style={{ backgroundColor: material.color }}
          />
        )}
      </div>
      <span className="text-[10px] font-medium text-zinc-600 leading-none text-center">
        {material.label}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// RoomRow — a single room in the list with inline rename and description accordion
// ---------------------------------------------------------------------------
function RoomRow({
  label,
  isSelected,
  materialLabel,
  isGlobal,
  area,
  description,
  onSelect,
  onRename,
  onDescriptionChange,
  onSend,
  isSending,
  sendMessage,
  sendError,
  hasOptions,
  onShowOptions,
}: {
  label: string;
  isSelected: boolean;
  materialLabel: string;
  isGlobal: boolean;
  area: number;
  description: string;
  onSelect: () => void;
  onRename: (name: string) => void;
  onDescriptionChange: (description: string) => void;
  onSend: () => void;
  isSending?: boolean;
  sendMessage?: string | null;
  sendError?: string | null;
  hasOptions?: boolean;
  onShowOptions?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(label);
  const [expanded, setExpanded] = useState(false);

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed) onRename(trimmed);
    else setDraft(label);
    setEditing(false);
  };

  return (
    <div
      className={`rounded-lg transition-colors ${
        isSelected ? "bg-[#eee0d0]" : "hover:bg-zinc-50"
      }`}
    >
      {/* Row header */}
      <div
        className="flex items-center gap-2 px-2 py-1.5 cursor-pointer"
        onClick={() => !editing && onSelect()}
      >
        {/* Selection dot */}
        <div
          className={`w-2 h-2 rounded-full shrink-0 transition-colors ${
            isSelected ? "bg-(--primary-color,#C8A882)" : "bg-zinc-200"
          }`}
        />

        {/* Name / input */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") commit();
                if (e.key === "Escape") {
                  setDraft(label);
                  setEditing(false);
                }
              }}
              onBlur={commit}
              onClick={(e) => e.stopPropagation()}
              className="w-full text-xs font-medium border-b border-zinc-400 bg-transparent outline-none py-0.5"
            />
          ) : (
            <span className="text-xs font-medium text-zinc-800 truncate block">
              {label}
            </span>
          )}
          <span className="text-[10px] text-zinc-400 flex items-center justify-between gap-1">
            <span className="truncate">
              {isGlobal ? "Sàn mặc định" : materialLabel}
            </span>
            <span className="shrink-0">{area.toFixed(1)} m²</span>
          </span>
        </div>

        {/* Rename / confirm button */}
        {editing ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              commit();
            }}
            className="p-1 text-zinc-500 hover:text-zinc-800"
          >
            <Check size={13} />
          </button>
        ) : (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setDraft(label);
              setEditing(true);
            }}
            className="p-1 text-black opacity-0 group-hover:opacity-100 transition-opacity"
            title="Đổi tên"
          >
            <Pencil size={13} />
          </button>
        )}

        {/* Accordion toggle */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((v) => !v);
          }}
          className="p-1 text-zinc-400 hover:text-zinc-700 transition-colors"
          title={expanded ? "Ẩn mô tả" : "Hiện mô tả"}
        >
          <ChevronDown
            size={13}
            className={`transition-transform duration-200 ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </button>
      </div>

      {/* Accordion body — description textarea */}
      {expanded && (
        <div className="px-2 pb-2">
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            onKeyDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            placeholder="Mô tả phòng..."
            rows={3}
            className="w-full text-xs text-zinc-700 bg-white border border-zinc-200 rounded-lg px-2 py-1.5 resize-none outline-none focus:border-(--primary-color,#C8A882) placeholder-zinc-400"
          />
          <div className="mt-1.5 flex gap-1.5">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSend();
              }}
              disabled={isSending}
              className={`${hasOptions ? "flex-1" : "w-full"} text-xs font-medium rounded-lg py-1.5 bg-(--primary-color,#C8A882) text-white hover:opacity-90 active:scale-95 transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-1.5`}
            >
              {isSending ? (
                <>
                  <Loader2 size={12} className="animate-spin" />
                  {sendMessage ?? "Đang xử lý..."}
                </>
              ) : (
                "Gửi dữ liệu phòng"
              )}
            </button>
            {hasOptions && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onShowOptions?.();
                }}
                className="shrink-0 text-xs font-medium rounded-lg py-1.5 px-2.5 border border-(--primary-color,#C8A882) text-[--primary-color,#C8A882] hover:bg-[#fdf6ee] active:scale-95 transition-all duration-150"
              >
                Các lựa chọn
              </button>
            )}
          </div>
          {sendError && (
            <p className="mt-1 flex items-center gap-1 text-[11px] text-red-500">
              <AlertCircle size={11} />
              {sendError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FloorStylePanel
// ---------------------------------------------------------------------------
export default function FloorStylePanel({
  open: openProp,
  onOpenChange,
}: FloorStylePanelProps = {}) {
  const [openLocal, setOpenLocal] = useState(true);
  const open = openProp !== undefined ? openProp : openLocal;
  const setOpen = (value: boolean) => {
    setOpenLocal(value);
    if (!value) setSelectedRoomKey(null);
    onOpenChange?.(value);
  };

  const walls = useWalls();
  const { objects } = useObjectsValue();
  const globalMaterialId = useGlobalMaterialId();
  const roomMaterials = useRoomMaterials();
  const roomNames = useRoomNames();
  const selectedRoomKey = useSelectedRoomKey();
  const setGlobalMaterial = useSetGlobalMaterial();
  const setRoomMaterial = useSetRoomMaterial();
  const clearRoomMaterial = useClearRoomMaterial();
  const setSelectedRoomKey = useSetSelectedRoomKey();
  const setRoomName = useSetRoomName();
  const roomDescriptions = useRoomDescriptions();
  const setRoomDescription = useSetRoomDescription();
  const addMultipleObjects = useAddMultipleObjects();
  const removeMultipleObjects = useRemoveMultipleObjects();
  const {
    floorMaterials,
    isLoading: floorsLoading,
    isError: floorsError,
  } = useFloorMaterials();

  const [fillState, setFillState] = useState<Record<string, FillRoomState>>({});

  // Detect all current room polygons — same pure function as Floor.tsx
  const roomPolygons = useMemo(() => findRoomPolygons(walls), [walls]);
  const roomKeys = useMemo(
    () => roomPolygons.map((p) => centroidKey(p)),
    [roomPolygons],
  );
  const roomAreas = useMemo(
    () =>
      roomPolygons.map((poly) => {
        let area = 0;
        for (let i = 0; i < poly.length; i++) {
          const [x0, z0] = poly[i];
          const [x1, z1] = poly[(i + 1) % poly.length];
          area += x0 * z1 - x1 * z0;
        }
        return Math.abs(area / 2);
      }),
    [roomPolygons],
  );

  // Auto-name: rooms without a user name get "Phòng 1", "Phòng 2"...
  const getRoomLabel = (key: string, index: number) =>
    roomNames[key] ?? `Phòng ${index + 1}`;

  // The active material id for the picker — room override or global
  const activeMaterialId = selectedRoomKey
    ? (roomMaterials[selectedRoomKey] ?? globalMaterialId)
    : globalMaterialId;

  const handleSwatchClick = (materialId: string) => {
    if (selectedRoomKey) {
      setRoomMaterial(selectedRoomKey, materialId);
    } else {
      setGlobalMaterial(materialId);
    }
  };

  // const selectedRoomLabel = selectedRoomKey
  //   ? getRoomLabel(selectedRoomKey, roomKeys.indexOf(selectedRoomKey))
  //   : null;

  // TODO: this is where you'd send the room data to AI api to get furniture suggestions based on the room's shape, size, and description. Check room-furniture-placement.md file in docs folder for more details.
  const sendRoomData = async (key: string, index: number) => {
    const materialId = roomMaterials[key] ?? globalMaterialId;
    const mat = floorMaterials.find((m) => m.id === materialId);
    const poly = roomPolygons[index] ?? [];
    const roomData = {
      key,
      name: getRoomLabel(key, index),
      polygons: poly,
      materialId,
      description: roomDescriptions[key] ?? "",
      materialLabel: mat?.label ?? "",
    };

    const EPSILON = 0.05;
    const ptKey = (x: number, z: number) =>
      `${Math.round(x / EPSILON)},${Math.round(z / EPSILON)}`;
    const edgeSet = new Set<string>();
    for (let i = 0; i < poly.length; i++) {
      const [x0, z0] = poly[i];
      const [x1, z1] = poly[(i + 1) % poly.length];
      edgeSet.add(`${ptKey(x0, z0)}|${ptKey(x1, z1)}`);
      edgeSet.add(`${ptKey(x1, z1)}|${ptKey(x0, z0)}`);
    }
    const wallData = walls.filter((w) =>
      edgeSet.has(
        `${ptKey(w.startPoint[0], w.startPoint[1])}|${ptKey(w.endPoint[0], w.endPoint[1])}`,
      ),
    );
    const roomWallIds = new Set(wallData.map((w) => w.id));
    const openings = objects.filter(
      (o) =>
        o.placementType === "wall" &&
        (o.objectRole === "door" || o.objectRole === "window") &&
        o.snappedToWall !== undefined &&
        roomWallIds.has(o.snappedToWall),
    );

    const payload = { room: roomData, walls: wallData, openings };

    setFillState((prev) => ({
      ...prev,
      [key]: {
        loading: true,
        error: null,
        result: null,
        placedIds: [],
        selectedOptionId: null,
        panelVisible: false,
      },
    }));

    try {
      // Bước 1: start job
      const job = await startNormalizeRun(payload);

      // Bước 2: poll cho đến khi ready, cập nhật stage/message cho UI
      const data = await pollNormalizeRunUntilReady(
        job.id,
        (status: NormalizeRunStatusResponse) => {
          setFillState((prev) => ({
            ...prev,
            [key]: {
              ...prev[key],
              stage: status.stage ?? null,
              message: status.message ?? null,
            },
          }));
        },
      );

      // Bước 3: place best valid option only
      const bestOption =
        data.options.find(
          (option) =>
            option.optionId === data.selectedOptionId &&
            canApplyAutoFillOption(option),
        ) ?? data.options.find(canApplyAutoFillOption);
      const legacyObjects = data.options.length === 0 ? data.objects : [];
      const legacyOpenings = data.options.length === 0 ? data.openings : [];
      const bestObjects = mapAutoFillItems(
        bestOption?.objects ?? legacyObjects,
        key,
        "obj",
      );
      const bestOpenings = mapAutoFillItems(
        bestOption?.openings ?? legacyOpenings,
        key,
        "opn",
      );
      const allPlaced = [...bestObjects, ...bestOpenings];
      if (allPlaced.length > 0) {
        const idsToRemove = new Set(
          objects
            .filter(
              (o) =>
                o.objectRole !== "door" &&
                o.objectRole !== "window" &&
                isPointInPolygon(o.position[0], o.position[2], poly),
            )
            .map((o) => o.id),
        );
        if (idsToRemove.size > 0) {
          removeMultipleObjects(idsToRemove);
        }
        addMultipleObjects(allPlaced);
      }

      setFillState((prev) => ({
        ...prev,
        [key]: {
          loading: false,
          error: null,
          result: data,
          placedIds: allPlaced.map((o) => o.id),
          selectedOptionId:
            bestOption?.optionId ??
            (data.options.length === 0 ? data.selectedOptionId : null),
          panelVisible: true,
          stage: null,
          message: null,
        },
      }));
    } catch (err) {
      setFillState((prev) => ({
        ...prev,
        [key]: {
          loading: false,
          error: err instanceof Error ? err.message : "Đã xảy ra lỗi",
          result: null,
          placedIds: [],
          selectedOptionId: null,
          panelVisible: false,
          stage: null,
          message: null,
        },
      }));
    }
  };

  return (
    <div
      className={`absolute top-14 left-22 h-[calc(100%-3.5rem)] z-55 transition-transform duration-300 ease-in-out ${
        open ? "translate-x-0" : "-translate-x-102"
      }`}
    >
      <div className="relative h-full flex items-stretch">
        {/* Panel body */}
        <div
          className="w-80 h-full bg-white shadow-(--shadow-style) rounded-2xl flex flex-col overflow-hidden"
          style={{ border: "var(--border-style)" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
            <span className="font-semibold text-sm text-zinc-800">
              Vật liệu sàn
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
                aria-label="Đóng bảng"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto flex flex-col">
            {/* ── Material picker ───────────────────────────────────── */}
            <section className="px-3 pt-3 pb-4 sticky top-0 bg-white z-10 border-b border-zinc-100">
              {/* Context label */}
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                  Sàn mặc định
                </p>
                {selectedRoomKey && roomMaterials[selectedRoomKey] && (
                  <button
                    type="button"
                    onClick={() => clearRoomMaterial(selectedRoomKey)}
                    className="text-[10px] text-zinc-400 hover:text-zinc-700 transition-colors"
                    title="Xóa ghi đè, dùng sàn mặc định"
                  >
                    Dùng mặc định
                  </button>
                )}
              </div>

              <div className="grid grid-cols-3 gap-1">
                {floorsLoading ? (
                  <p className="col-span-3 text-[11px] text-zinc-400 py-2 text-center">
                    Đang tải...
                  </p>
                ) : floorsError ? (
                  <p className="col-span-3 text-[11px] text-red-400 py-2 text-center">
                    Không thể tải vật liệu sàn
                  </p>
                ) : (
                  floorMaterials.map((mat) => (
                    <MaterialSwatch
                      key={mat.id}
                      material={mat}
                      isActive={mat.id === activeMaterialId}
                      onClick={() => handleSwatchClick(mat.id)}
                    />
                  ))
                )}
              </div>
            </section>

            {/* ── Rooms list ────────────────────────────────────────── */}
            <section className="px-3 pt-3 pb-2 border-b border-zinc-100 shrink-0">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-1.5">
                Phòng
              </p>
              {roomKeys.length === 0 ? (
                <p className="text-[11px] text-zinc-400 py-1">
                  Chưa có phòng kín nào. Vẽ tường để tạo phòng.
                </p>
              ) : (
                <div className="flex flex-col gap-0.5">
                  {roomKeys.map((key, i) => {
                    const matId = roomMaterials[key];
                    const mat = floorMaterials.find(
                      (m) => m.id === (matId ?? globalMaterialId),
                    );
                    return (
                      <div key={key} className="group">
                        <RoomRow
                          label={getRoomLabel(key, i)}
                          isSelected={selectedRoomKey === key}
                          materialLabel={mat?.label ?? "Gỗ Sồi"}
                          isGlobal={!matId}
                          area={roomAreas[i] ?? 0}
                          description={roomDescriptions[key] ?? ""}
                          onSelect={() =>
                            setSelectedRoomKey(
                              selectedRoomKey === key ? null : key,
                            )
                          }
                          onRename={(name) => setRoomName(key, name)}
                          onDescriptionChange={(desc) =>
                            setRoomDescription(key, desc)
                          }
                          onSend={() => sendRoomData(key, i)}
                          isSending={fillState[key]?.loading}
                          sendMessage={fillState[key]?.message}
                          sendError={fillState[key]?.error}
                          hasOptions={!!fillState[key]?.result}
                          onShowOptions={() => {
                            setSelectedRoomKey(key);
                            setFillState((prev) => ({
                              ...prev,
                              [key]: { ...prev[key], panelVisible: true },
                            }));
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </div>

        {/* Toggle tab — only visible when open */}
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-label="Đóng bảng"
          className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-full bg-white rounded-r-xl px-2 py-4 shadow-md hover:bg-zinc-50 active:scale-95 transition-all duration-150 text-zinc-500 hover:text-zinc-800 ${open ? "" : "hidden"}`}
        >
          {open ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>

        {/* ── Options panel — appears to the right when fill results exist ── */}
        {selectedRoomKey && fillState[selectedRoomKey]?.panelVisible && (
          <RoomAutoFillOptions
            roomKey={selectedRoomKey}
            fillRoomState={fillState[selectedRoomKey]}
            onApplied={(placedIds, selectedOptionId) =>
              setFillState((prev) => ({
                ...prev,
                [selectedRoomKey]: {
                  ...prev[selectedRoomKey],
                  placedIds,
                  selectedOptionId,
                },
              }))
            }
            onClose={() =>
              setFillState((prev) => ({
                ...prev,
                [selectedRoomKey]: {
                  ...prev[selectedRoomKey],
                  panelVisible: false,
                },
              }))
            }
          />
        )}
      </div>
    </div>
  );
}
