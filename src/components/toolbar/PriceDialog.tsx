import {
  useObjectsValue,
  useRemoveMultipleObjects,
} from "@/states/slices/objects/hooks";
import { useCatalogItemDetailsByIds } from "@/hooks/useCatalog";
import { useWalls } from "@/states/slices/walls/hooks";
import { useRoomNames } from "@/states/slices/floor/hooks";
import {
  findRoomPolygons,
  centroidKey,
  isPointInPolygon,
} from "@/lib/roomPolygons";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Trash2, X } from "lucide-react";
import * as XLSX from "xlsx";
import type { SceneObject } from "@/states/slices/objects/types";

interface PriceDialogProps {
  open: boolean;
  onClose: () => void;
}

const headerExcelTable = [
  "STT",
  "Tên vật dụng",
  "Thương hiệu",
  "Đơn giá (VND)",
  "Thành tiền (VND)",
];

const fmt = new Intl.NumberFormat("vi-VN");

function getObjectPrice(
  obj: SceneObject,
  itemDetailsMap:
    | Map<string, ReturnType<typeof Object.fromEntries>>
    | undefined,
): number {
  if (obj.variantPriceCents !== undefined) return obj.variantPriceCents;
  if (obj.catalogItemId && itemDetailsMap?.has(obj.catalogItemId)) {
    return (itemDetailsMap.get(obj.catalogItemId) as { priceCents: number })
      .priceCents;
  }
  return 0;
}

export default function PriceDialog({ open, onClose }: PriceDialogProps) {
  const { objects } = useObjectsValue();
  const removeMultipleObjects = useRemoveMultipleObjects();
  const walls = useWalls();
  const roomNames = useRoomNames();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Compute rooms
  const roomPolygons = useMemo(() => findRoomPolygons(walls), [walls]);
  const roomKeys = useMemo(
    () => roomPolygons.map((p) => centroidKey(p)),
    [roomPolygons],
  );

  // Default: first room. null = "Tất cả"
  const [activeRoomKey, setActiveRoomKey] = useState<string | null>(
    () => roomKeys[0] ?? null,
  );

  // Fetch full catalog details for all objects that have a catalogItemId
  const catalogItemIds = useMemo(
    () =>
      [
        ...new Set(objects.map((o) => o.catalogItemId).filter(Boolean)),
      ] as string[],
    [objects],
  );
  const { data: itemDetailsMap } = useCatalogItemDetailsByIds(catalogItemIds, {
    enabled: open,
  });

  // Bucket objects by room key (or "other")
  const objectsByRoom = useMemo<Record<string, SceneObject[]>>(() => {
    const buckets: Record<string, SceneObject[]> = {};
    for (const obj of objects) {
      let assigned = false;
      for (let i = 0; i < roomPolygons.length; i++) {
        if (
          isPointInPolygon(obj.position[0], obj.position[2], roomPolygons[i])
        ) {
          const key = roomKeys[i];
          (buckets[key] ??= []).push(obj);
          assigned = true;
          break;
        }
      }
      if (!assigned) (buckets["other"] ??= []).push(obj);
    }
    return buckets;
  }, [objects, roomPolygons, roomKeys]);

  // Objects to show in table
  const displayedObjects = useMemo<SceneObject[]>(() => {
    if (activeRoomKey === null) return objects;
    return objectsByRoom[activeRoomKey] ?? [];
  }, [activeRoomKey, objects, objectsByRoom]);

  // Totals
  const furnitureTotal = useMemo(
    () =>
      displayedObjects.reduce(
        (sum, obj) =>
          sum +
          getObjectPrice(
            obj,
            itemDetailsMap as Map<string, { priceCents: number }> | undefined,
          ),
        0,
      ),
    [displayedObjects, itemDetailsMap],
  );
  const vatAmount = Math.round(furnitureTotal * 0.1);
  const grandTotal = furnitureTotal + vatAmount;

  // Select / deselect
  const toggleRow = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === displayedObjects.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayedObjects.map((o) => o.id)));
    }
  };

  const handleDelete = () => {
    removeMultipleObjects(selectedIds);
    setSelectedIds(new Set());
  };

  const handleExportExcel = () => {
    const dataRows = objects.map((obj, index) => {
      const detail = obj.catalogItemId
        ? (
            itemDetailsMap as
              | Map<string, { priceCents: number; brand: string }>
              | undefined
          )?.get(obj.catalogItemId)
        : undefined;
      const unitPrice = detail?.priceCents ?? 0;
      const itemName = obj.name ?? obj.modelUrl ?? "Không xác định";
      return [index + 1, itemName, detail?.brand ?? "", unitPrice, unitPrice];
    });
    const footerRow = ["", "", "", "Tổng cộng", "", grandTotal];
    const worksheet = XLSX.utils.aoa_to_sheet([
      headerExcelTable,
      ...dataRows,
      footerRow,
    ]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "BaoGia");
    XLSX.writeFile(workbook, `bao-gia-phong-${Date.now()}.xlsx`);
  };

  if (!open) return null;
  if (typeof document === "undefined") return null;

  const getRoomLabel = (key: string, index: number) =>
    roomNames[key] ?? `Phòng ${index + 1}`;

  const otherCount = objectsByRoom["other"]?.length ?? 0;
  const allSelected =
    displayedObjects.length > 0 && selectedIds.size === displayedObjects.length;

  return createPortal(
    <div className="fixed inset-0 z-80 flex items-center justify-center p-4">
      {/* Backdrop */}
      <button
        aria-label="Close price dialog"
        className="absolute inset-0 bg-black/35"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-7xl rounded-2xl bg-white shadow-(--shadow-style) flex flex-col overflow-hidden"
        style={{ border: "var(--border-style)", height: "90vh" }}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-100 shrink-0">
          <div>
            <h3 className="text-base font-semibold text-slate-800">Báo giá</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Tất cả | Sản phẩm đã sử dụng : {objects.length} cái | Đã chọn:{" "}
              {selectedIds.size} cái | Tổng cộng: {fmt.format(grandTotal)} đ
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-52 border-r border-zinc-100 flex flex-col shrink-0 overflow-y-auto">
            {/* Upper section — Tất cả */}
            <div className="px-3 pt-3 pb-2">
              <button
                onClick={() => setActiveRoomKey(null)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-colors ${
                  activeRoomKey === null
                    ? "bg-[#f5ece0] text-[#7c5a3a] font-medium"
                    : "text-zinc-600 hover:bg-zinc-50"
                }`}
              >
                <span>Tất cả</span>
                <span className="text-xs text-zinc-400">
                  {objects.length} cái
                </span>
              </button>
            </div>

            <div className="mx-3 border-t border-zinc-100" />

            {/* Lower section — per room */}
            <div className="px-3 pt-2 pb-3 flex flex-col gap-0.5">
              {roomKeys.map((key, i) => {
                const count = objectsByRoom[key]?.length ?? 0;
                return (
                  <button
                    key={key}
                    onClick={() => setActiveRoomKey(key)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-colors ${
                      activeRoomKey === key
                        ? "bg-[#f5ece0] text-[#7c5a3a] font-medium"
                        : "text-zinc-600 hover:bg-zinc-50"
                    }`}
                  >
                    <span className="truncate text-left">
                      {getRoomLabel(key, i)}
                    </span>
                    <span className="text-xs text-zinc-400 shrink-0 ml-1">
                      {count} cái
                    </span>
                  </button>
                );
              })}
              {otherCount > 0 && (
                <button
                  onClick={() => setActiveRoomKey("other")}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-colors ${
                    activeRoomKey === "other"
                      ? "bg-[#f5ece0] text-[#7c5a3a] font-medium"
                      : "text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  <span>Khác</span>
                  <span className="text-xs text-zinc-400">
                    {otherCount} cái
                  </span>
                </button>
              )}
            </div>
          </div>

          {/* Table panel */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Table header bar */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-100 shrink-0">
              <span className="text-sm font-medium text-zinc-700">
                {activeRoomKey === null
                  ? "Đồ nội thất"
                  : getRoomLabel(
                      activeRoomKey,
                      roomKeys.indexOf(activeRoomKey),
                    )}
              </span>
              <div className="flex items-center gap-3">
                {selectedIds.size > 0 && (
                  <button
                    onClick={handleDelete}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-50 text-red-600 text-xs hover:bg-red-100 transition-colors"
                    aria-label="Xóa đồ đã chọn"
                  >
                    <Trash2 size={13} />
                    Xóa {selectedIds.size} mục
                  </button>
                )}
                <span className="text-sm text-zinc-500 py-1.5">
                  Tổng cộng: {fmt.format(furnitureTotal)} đ
                </span>
              </div>
            </div>

            {/* Scrollable table */}
            <div className="flex-1 overflow-auto">
              <table className="w-full text-xs border-collapse min-w-max">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b border-zinc-100">
                    <th className="w-8 px-3 py-2.5 text-center">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleAll}
                        className="accent-[#7c5a3a]"
                      />
                    </th>
                    <th className="w-12 px-2 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Hình ảnh
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Thương hiệu
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Tên mặt hàng
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Mã màu
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Tên màu
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Mã sản phẩm
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Vật liệu
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Chiều rộng
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Chiều cao
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap">
                      Chiều sâu
                    </th>
                    <th className="px-3 py-2.5 text-left text-zinc-400 font-medium">
                      Đơn vị
                    </th>
                    <th className="px-3 py-2.5 text-right text-zinc-400 font-medium whitespace-nowrap">
                      Đơn giá
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayedObjects.length === 0 ? (
                    <tr>
                      <td
                        colSpan={13}
                        className="px-4 py-8 text-center text-zinc-400"
                      >
                        Không có đồ nội thất trong phòng này
                      </td>
                    </tr>
                  ) : (
                    displayedObjects.map((obj) => {
                      const detail = obj.catalogItemId
                        ? (
                            itemDetailsMap as
                              | Map<
                                  string,
                                  {
                                    priceCents: number;
                                    brand: string;
                                    nameVn: string;
                                    thumbnailUrl: string | null;
                                    skuSlug: string;
                                    colorDefault: string;
                                  }
                                >
                              | undefined
                          )?.get(obj.catalogItemId)
                        : undefined;

                      const price =
                        obj.variantPriceCents ?? detail?.priceCents ?? 0;
                      const brand =
                        detail?.brand && detail.brand.trim()
                          ? detail.brand
                          : "—";
                      const name = obj.name ?? detail?.nameVn ?? "—";
                      const rawColor = (
                        obj.selectedColorHex ??
                        detail?.colorDefault ??
                        obj.color ??
                        ""
                      ).replace("#", "");
                      const colorCode = rawColor || "000000";
                      const colorName = obj.selectedColorName ?? "—";
                      const sku =
                        detail?.skuSlug ?? obj.id.slice(-6).toUpperCase();
                      const thumbnailSrc = detail?.thumbnailUrl
                        ? getCatalogModelUrl(detail.thumbnailUrl)
                        : null;

                      const isChecked = selectedIds.has(obj.id);

                      return (
                        <tr
                          key={obj.id}
                          className={`border-b border-zinc-50 transition-colors ${isChecked ? "bg-[#fdf6ee]" : "hover:bg-zinc-50"}`}
                        >
                          <td className="px-3 py-2 text-center">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => toggleRow(obj.id)}
                              className="accent-[#7c5a3a]"
                            />
                          </td>
                          <td className="px-2 py-2">
                            {thumbnailSrc ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={thumbnailSrc}
                                alt={name}
                                className="w-10 h-10 rounded-lg object-cover bg-zinc-100"
                              />
                            ) : (
                              <div className="w-10 h-10 rounded-lg bg-zinc-100" />
                            )}
                          </td>
                          <td className="px-3 py-2 text-zinc-600 whitespace-nowrap">
                            {brand}
                          </td>
                          <td className="px-3 py-2 text-zinc-700 font-medium max-w-40 truncate">
                            {name}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <span
                                className="w-4 h-4 rounded-sm border border-zinc-200 shrink-0"
                                style={{ backgroundColor: `#${colorCode}` }}
                              />
                              <span className="text-zinc-500">{colorCode}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2 text-zinc-500 whitespace-nowrap">
                            {colorName}
                          </td>
                          <td className="px-3 py-2 text-zinc-500 font-mono whitespace-nowrap">
                            {sku}
                          </td>
                          <td className="px-3 py-2 text-zinc-500 whitespace-nowrap">
                            {obj.selectedMaterialName ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-zinc-600 whitespace-nowrap">
                            {Math.round(obj.size[0] * 1000)}mm
                          </td>
                          <td className="px-3 py-2 text-zinc-600 whitespace-nowrap">
                            {Math.round(obj.size[1] * 1000)}mm
                          </td>
                          <td className="px-3 py-2 text-zinc-600 whitespace-nowrap">
                            {Math.round(obj.size[2] * 1000)}mm
                          </td>
                          <td className="px-3 py-2 text-zinc-400">mm</td>
                          <td className="px-3 py-2 text-right text-zinc-700 whitespace-nowrap">
                            {fmt.format(price)} đ
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-6 items-center justify-between px-5 py-3 border-t border-zinc-100 shrink-0 bg-white">
          <button
            onClick={handleExportExcel}
            className="w-1/7 rounded-full bg-(--primary-color) px-5 py-2 text-sm text-white transition-all active:scale-95"
          >
            Xuất file excel
          </button>
          {activeRoomKey == null && (
            <div className="flex w-6/7 justify-end bg-(--option-highlight-color) h-full rounded-lg px-4 py-2">
              <p className="text-sm font-medium text-zinc-700">
                Tổng cộng{" "}
                <span className="text-zinc-500 font-normal">
                  Đồ nội thất: {fmt.format(furnitureTotal)} đ + VAT:{" "}
                  {fmt.format(vatAmount)} đ ={" "}
                </span>
                <span className="text-(--primary-color) font-semibold">
                  {fmt.format(grandTotal)} đ
                </span>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
