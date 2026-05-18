"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  X,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
  BedDouble,
  Sofa,
  Bath,
  Plus,
} from "lucide-react";
import { useBuildings, useLoadDesign, useTemplates } from "@/hooks/useDesign";
import { useReplaceAllObjects } from "@/states/slices/objects/hooks";
import { useSetWalls } from "@/states/slices/walls/hooks";
import { useSetViewMode } from "@/states/slices/view/hooks";
import {
  useSetEditMode,
  useStartDrawingWall,
} from "@/states/slices/wallEditor/hooks";
import usePagination from "@/hooks/usePagination";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TTemplateListItem } from "@/types/api";
import ConfirmCreateLayoutDialog from "./ConfirmCreateLayoutDialog";
import ImageFloorPlanPanel from "./ImageFloorPlanPanel";

interface Props {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onApplySuccess?: () => void;
}

const SVG_PREVIEW_SIZE = 80;
const SVG_PAD_RATIO = 0.12;

/** Renders all room polygons as a small SVG floor plan. Accepts multiple polygons for multi-room layouts. */
function FloorPlanSvg({ polygons }: { polygons: [number, number][][] }) {
  const allPoints = polygons.flat();
  if (allPoints.length === 0) return null;
  const xs = allPoints.map((p) => p[0]);
  const zs = allPoints.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);
  const span = Math.max(maxX - minX, maxZ - minZ) || 1;
  const padWorld = span * SVG_PAD_RATIO;
  const originX = (minX + maxX) / 2 - (span + padWorld * 2) / 2;
  const originZ = (minZ + maxZ) / 2 - (span + padWorld * 2) / 2;
  const scale = SVG_PREVIEW_SIZE / (span + padWorld * 2);
  const toSvg = (x: number, z: number): [number, number] => [
    (x - originX) * scale,
    (z - originZ) * scale,
  ];
  return (
    <svg
      width={SVG_PREVIEW_SIZE}
      height={SVG_PREVIEW_SIZE}
      viewBox={`0 0 ${SVG_PREVIEW_SIZE} ${SVG_PREVIEW_SIZE}`}
      className="overflow-visible"
    >
      {polygons.map((poly, i) => (
        <polygon
          key={i}
          points={poly.map(([x, z]) => toSvg(x, z).join(",")).join(" ")}
          fill="rgba(200,168,130,0.18)"
          stroke="#C8A882"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}

/** A compact info card showing room counts and design style instead of a wall SVG. */
function TemplateCard({ template }: { template: TTemplateListItem }) {
  const { roomCounts, designStyle, polygon } = template;
  const hasPolygon = polygon && polygon.length >= 3;
  if (hasPolygon) {
    return (
      <div className="w-full h-20 rounded-lg bg-linear-to-br from-[#fdf6ee] to-[#f5ece0] flex items-center justify-center overflow-hidden">
        <FloorPlanSvg polygons={polygon ?? []} />
      </div>
    );
  }
  return (
    <div className="w-full h-20 rounded-lg bg-linear-to-br from-[#fdf6ee] to-[#f5ece0] flex flex-col items-center justify-center gap-1 px-2">
      <div className="flex items-center gap-2.5 text-[10px] text-(--secondary-color)">
        {roomCounts.bedrooms > 0 && (
          <span className="flex items-center gap-0.5">
            <BedDouble size={10} className="text-(--primary-color)" />
            {roomCounts.bedrooms}
          </span>
        )}
        {roomCounts.living > 0 && (
          <span className="flex items-center gap-0.5">
            <Sofa size={10} className="text-(--primary-color)" />
            {roomCounts.living}
          </span>
        )}
        {roomCounts.bathrooms > 0 && (
          <span className="flex items-center gap-0.5">
            <Bath size={10} className="text-(--primary-color)" />
            {roomCounts.bathrooms}
          </span>
        )}
      </div>
      {designStyle && (
        <span className="text-[9px] text-zinc-400 capitalize leading-none">
          {designStyle}
        </span>
      )}
    </div>
  );
}

export default function RoomTemplateSelector({
  open: openProp,
  onOpenChange,
  onApplySuccess,
}: Props) {
  const replaceAllObjects = useReplaceAllObjects();
  const setWalls = useSetWalls();
  const setViewMode = useSetViewMode();
  const setEditMode = useSetEditMode();
  const startDrawingWall = useStartDrawingWall();
  const [isConfirmCreateOpen, setIsConfirmCreateOpen] = useState(false);
  const [isImagePanelOpen, setIsImagePanelOpen] = useState(false);
  const [openLocal, setOpenLocal] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  );
  const open = openProp !== undefined ? openProp : openLocal;
  const setOpen = (value: boolean) => {
    if (!value) setSelectedTemplateId(null);
    setOpenLocal(value);
    onOpenChange?.(value);
  };

  const [search, setSearch] = useState("");
  const [activeBuildingId, setActiveBuildingId] = useState<string | null>(null);
  const { data: buildingsData } = useBuildings();
  const {
    data: templatesData,
    isLoading: isLoadingTemplates,
    isError: isTemplatesError,
  } = useTemplates();
  const loadDesignQuery = useLoadDesign(selectedTemplateId);
  const onOpenChangeRef = useRef(onOpenChange);
  const onApplySuccessRef = useRef(onApplySuccess);

  useEffect(() => {
    onOpenChangeRef.current = onOpenChange;
  }, [onOpenChange]);

  useEffect(() => {
    onApplySuccessRef.current = onApplySuccess;
  }, [onApplySuccess]);

  const buildings = buildingsData ?? [];
  const allTemplates = templatesData?.items ?? [];

  const filtered = allTemplates.filter((t) => {
    const matchBuilding =
      !activeBuildingId || t.buildingId === activeBuildingId;
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q);
    return matchBuilding && matchSearch;
  });

  // Paginate filtered templates (2 columns grid, show 6 per page)
  const {
    data: pageItems,
    next,
    prev,
    currentPage,
    maxPage,
  } = usePagination<TTemplateListItem>(filtered, { itemPerPage: 6 });

  const applyTemplate = (template: TTemplateListItem) => {
    if (selectedTemplateId && loadDesignQuery.isFetching) return;

    if (selectedTemplateId === template.id) {
      void loadDesignQuery.refetch();
      return;
    }

    setSelectedTemplateId(template.id);
  };

  const handleCreateNew = () => {
    setIsConfirmCreateOpen(true);
  };

  const handleCreateFromImage = () => {
    setIsImagePanelOpen(true);
  };

  const handleConfirmCreateNew = () => {
    setIsConfirmCreateOpen(false);
    replaceAllObjects([]);
    setWalls([]);
    setViewMode("2D");
    setEditMode("walls");
    startDrawingWall([0, 0]);
    setOpen(false);
  };

  useEffect(() => {
    if (!selectedTemplateId || !loadDesignQuery.isSuccess) return;
    const timer = setTimeout(() => {
      setOpenLocal(false);
      onOpenChangeRef.current?.(false);
      onApplySuccessRef.current?.();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadDesignQuery.isSuccess, selectedTemplateId]);

  return (
    <>
      <div
        className={`absolute top-14 left-22 h-[calc(100%-3.5rem)] z-55 transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "-translate-x-102"
        }`}
      >
        <div className="relative h-full flex items-stretch">
          <div
            className="w-80 h-full bg-white shadow-(--shadow-style) rounded-2xl flex flex-col overflow-hidden"
            style={{ border: "var(--border-style)" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
              <span className="font-medium text-sm text-(--secondary-color)">
                Mặt bằng
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
                aria-label="Đóng bảng"
              >
                <X size={16} />
              </button>
            </div>

            {/* Search + building filter */}
            <div className="px-4 pt-3 pb-3 border-b border-zinc-100 shrink-0 space-y-2">
              <div className="flex items-center gap-2 border border-zinc-200 rounded-lg px-3 py-2">
                <Search size={14} className="text-zinc-400 shrink-0" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                  placeholder="Tìm mẫu hoặc tên chung cư..."
                  className="flex-1 bg-transparent text-sm text-black placeholder-zinc-400 outline-none"
                />
              </div>
              <div className="flex flex-col">
                <label className="mb-1 block text-[11px] font-medium text-(--secondary-color)">
                  Chung cư
                </label>
                <Select
                  value={activeBuildingId ?? "all"}
                  onValueChange={(value) =>
                    setActiveBuildingId(value === "all" ? null : value)
                  }
                >
                  <SelectTrigger className="w-full h-8 rounded-lg border-zinc-200 text-[12px] text-(--secondary-color)">
                    <SelectValue placeholder="Tất cả" />
                  </SelectTrigger>
                  <SelectContent className="z-60">
                    <SelectItem value="all">Tất cả</SelectItem>
                    {buildings.map((b) => (
                      <SelectItem key={b.id} value={b.id}>
                        {b.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Template grid */}
            <div className="overflow-y-auto flex-1 px-3 py-3">
              {isLoadingTemplates ? (
                <div className="grid grid-cols-2 gap-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div
                      key={i}
                      className="rounded-xl bg-zinc-100 animate-pulse h-32"
                    />
                  ))}
                </div>
              ) : isTemplatesError ? (
                <p className="text-center text-xs text-zinc-400 py-8">
                  Không thể tải mẫu, vui lòng thử lại
                </p>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={handleCreateNew}
                      className="flex flex-col items-center gap-1.5 p-1.5 rounded-xl bg-[#fafafa] border-2 transition-all duration-150 cursor-pointer hover:border-(--primary-color,#C8A882) hover:shadow-md"
                    >
                      <div className="w-full h-20 rounded-lg bg-linear-to-br from-[#fdf6ee] to-[#f5ece0] flex items-center justify-center">
                        <Plus size={22} className="text-(--primary-color)" />
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold leading-tight">
                          Tạo mới
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">
                          Bắt đầu từ bản trống
                        </p>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={handleCreateFromImage}
                      className="flex flex-col items-center gap-1.5 p-1.5 rounded-xl bg-[#fafafa] border-2 transition-all duration-150 cursor-pointer hover:border-(--primary-color,#C8A882) hover:shadow-md"
                    >
                      <div className="w-full h-20 rounded-lg bg-linear-to-br from-[#fdf6ee] to-[#f5ece0] flex items-center justify-center">
                        <p className="text-[11px] text-(--primary-color) font-semibold leading-tight">
                          Ảnh mặt bằng
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold leading-tight">
                          Tải ảnh lên
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">
                          Hệ thống sẽ tự động nhận diện phòng
                        </p>
                      </div>
                    </button>
                    {pageItems.map((template) => {
                      const isApplying =
                        selectedTemplateId === template.id &&
                        loadDesignQuery.isFetching;
                      return (
                        <button
                          key={template.id}
                          onClick={() => applyTemplate(template)}
                          disabled={Boolean(
                            selectedTemplateId && loadDesignQuery.isFetching,
                          )}
                          className="flex flex-col items-center gap-1.5 p-1.5 rounded-xl bg-[#fafafa] border-2 transition-all duration-150 cursor-pointer hover:border-(--primary-color,#C8A882) hover:shadow-md disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                          <div className="relative w-full h-20 rounded-lg overflow-hidden flex items-center justify-center">
                            {isApplying ? (
                              <div className="absolute inset-0 flex items-center justify-center bg-white/70">
                                <Loader2
                                  size={20}
                                  className="animate-spin text-(--primary-color)"
                                />
                              </div>
                            ) : null}
                            <TemplateCard template={template} />
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold leading-tight">
                              {template.name}
                            </p>
                            <p className="text-[10px] text-zinc-400 mt-0.5">
                              {template.description}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {/* Pagination controls — show only when there are more items than the page size */}
                  {filtered.length > 6 && maxPage > 1 && (
                    <div className="flex items-center justify-center gap-3 mt-2">
                      <button
                        type="button"
                        onClick={prev}
                        disabled={currentPage <= 1}
                        className="p-2 rounded-md bg-white border border-zinc-200 disabled:opacity-50"
                        aria-label="Trang trước"
                      >
                        <ChevronLeft size={16} />
                      </button>

                      <span className="text-xs text-zinc-500">
                        {currentPage} / {maxPage}
                      </span>

                      <button
                        type="button"
                        onClick={next}
                        disabled={currentPage >= maxPage}
                        className="p-2 rounded-md bg-white border border-zinc-200 disabled:opacity-50"
                        aria-label="Trang sau"
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  )}
                  {filtered.length === 0 && (
                    <p className="text-center text-xs text-zinc-400 py-2">
                      Không tìm thấy mẫu phù hợp
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Toggle tab — only visible when open */}
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label="Đóng bảng"
            className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-full bg-white rounded-r-xl px-2 py-4 shadow-md hover:bg-zinc-50 active:scale-95 transition-all duration-150 text-zinc-500 hover:text-zinc-800 ${open ? "" : "hidden"}`}
            style={{ border: "var(--border-style)" }}
          >
            {open ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
        </div>
      </div>
      <ConfirmCreateLayoutDialog
        open={isConfirmCreateOpen}
        onCancel={() => setIsConfirmCreateOpen(false)}
        onConfirm={handleConfirmCreateNew}
      />
      <ImageFloorPlanPanel
        open={isImagePanelOpen}
        onOpenChange={setIsImagePanelOpen}
      />
    </>
  );
}
