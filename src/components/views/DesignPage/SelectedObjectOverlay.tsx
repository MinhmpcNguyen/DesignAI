"use client";

import { useState, useMemo, useEffect } from "react";
import { Euler, Quaternion } from "three";
import {
  useSelectionValue,
  useSetSelectedId,
} from "@/states/slices/selection/hooks";
import {
  useObjectsValue,
  useUpdateObjectPosition,
  useUpdateObjectRotation,
  useUpdateObjectSize,
  useRemoveObject,
  useAddObject,
  useSetObjectDisplayOptions,
} from "@/states/slices/objects/hooks";
import {
  useCatalogItemOptions,
  useCatalogItem,
  useCatalogItems,
} from "@/hooks/useCatalog";
import {
  // useFavoritesValue,
  useInitFavorites,
  // useToggleFavorite,
} from "@/states/slices/favorites/hooks";
// import { FavoriteFilledIcon, FavoriteIcon, StarIcon } from "../../icons";
import ShapePreview from "../../drag-n-drop/ShapePreview";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import type { CatalogListItem } from "@/types/api";
import { calcResizePrice } from "@/constant/resizeConfig";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";

interface AxisInputProps {
  label: string;
  live: number;
  unit?: string;
  onCommit: (value: number) => void;
}

function AxisInput({ label, live, unit, onCommit }: AxisInputProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const displayValue = editing ? draft : live?.toFixed(2);
  const isDirty = editing && draft !== live?.toFixed(2);

  const startEdit = () => {
    setDraft(live.toFixed(2));
    setEditing(true);
  };

  const commit = () => {
    const parsed = parseFloat(draft);
    if (!isNaN(parsed) && parsed !== live) {
      onCommit(parsed);
    }
    setEditing(false);
  };

  const revert = () => setEditing(false);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.key === "Enter") {
      commit();
      e.currentTarget.blur();
    } else if (e.key === "Escape") {
      revert();
      e.currentTarget.blur();
    }
  };

  return (
    <div className="flex items-center justify-between gap-2 py-2">
      <span className="text-sm text-slate-500">{label}</span>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          step="0.01"
          value={displayValue}
          onChange={(e) => {
            if (editing) setDraft(e.target.value);
          }}
          onFocus={startEdit}
          onBlur={commit}
          onKeyDown={handleKeyDown}
          className={
            "w-20 bg-transparent font-mono text-sm outline-none text-right border-b transition-colors " +
            (isDirty
              ? "border-(--primary-color) text-(--primary-color)"
              : "border-transparent text-slate-700 hover:border-(--secondary-color) focus:border-(--primary-color)")
          }
        />
        {unit && <span className="text-xs text-slate-400">{unit}</span>}
      </div>
    </div>
  );
}

// function StarRating({ rating }: { rating: number }) {
//   const fullStars = Math.floor(rating);
//   const hasHalf = rating % 1 >= 0.5;

//   return (
//     <div className="flex items-center gap-1">
//       {[1, 2, 3, 4, 5].map((i) => (
//         <StarIcon
//           key={i}
//           light={i <= fullStars}
//           half={i === fullStars + 1 && hasHalf}
//         />
//       ))}
//     </div>
//   );
// }

export default function SelectedObjectOverlay() {
  const [viewMode, setViewMode] = useState<"info" | "rating">("info");

  // Unified option value ID selection for API variants; keyed by option name
  const [selectedOptionIds, setSelectedOptionIds] = useState<{
    forId: string;
    byName: Record<string, string>;
  } | null>(null);

  // const { favoriteKeys: favoriteIds } = useFavoritesValue();
  const initFavorites = useInitFavorites();
  // const toggleFavorite = useToggleFavorite();

  // Ensure favorites are loaded from localStorage (idempotent)
  useEffect(() => {
    initFavorites();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const { selectedIds } = useSelectionValue();
  const { objects } = useObjectsValue();
  const updatePosition = useUpdateObjectPosition();
  const updateRotation = useUpdateObjectRotation();
  const updateSize = useUpdateObjectSize();
  const removeObject = useRemoveObject();
  const addObject = useAddObject();
  const setSelectedId = useSetSelectedId();

  const activeClass =
    "flex-1 items-center gap-1.5 px-2 py-1 rounded-xl bg-(--primary-color) text-white transition-all";
  const inactiveClass = "flex-1 items-center gap-1.5 px-2 py-1 transition-all";

  const selectedId = selectedIds.size === 1 ? [...selectedIds][0] : null;

  const obj = selectedId
    ? (objects.find((o) => o.id === selectedId) ?? null)
    : null;

  // Fetch live variant options when the object was placed from the catalog API
  const { data: catalogOptions } = useCatalogItemOptions(
    obj?.catalogItemId ?? "",
    { enabled: !!obj?.catalogItemId },
  );

  // Initialize selectedOptionIds from the default variant whenever catalog data loads or the
  // selected object changes. Ensures all option dimensions start with the correct active state.
  useEffect(() => {
    if (!catalogOptions || !obj) {
      setSelectedOptionIds(null);
      return;
    }
    const defaultIds = catalogOptions.defaultVariant.selectedOptionValueIds;
    const byName: Record<string, string> = {};
    for (const opt of catalogOptions.options) {
      const matchId = defaultIds.find((id) =>
        opt.values.some((v) => v.id === id),
      );
      if (matchId) byName[opt.name] = matchId;
    }
    setSelectedOptionIds({ forId: obj.id, byName });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalogOptions, obj?.id]);

  const { data: catalogItem } = useCatalogItem(obj?.catalogItemId ?? "", {
    enabled: !!obj?.catalogItemId,
  });

  // Related items — same category as selected object
  const relatedCategoryId = catalogItem?.categoryId ?? "";
  const { data: relatedData, isLoading: relatedLoading } = useCatalogItems(
    relatedCategoryId,
    { enabled: !!relatedCategoryId },
  );
  const relatedItems = useMemo(() => {
    if (!relatedData?.items) return [];
    return relatedData.items
      .filter((item) => item.id !== obj?.catalogItemId)
      .slice(0, 8);
  }, [relatedData, obj?.catalogItemId]);

  const apiColorValues =
    catalogOptions?.options.find((o) => o.name === "color")?.values ?? [];
  const apiSizeValues =
    catalogOptions?.options.find((o) => o.name === "size")?.values ?? [];
  const apiMaterialValues =
    catalogOptions?.options.find((o) => o.name === "material")?.values ?? [];
  const apiPrice =
    catalogOptions?.defaultVariant != null
      ? catalogOptions.defaultVariant.priceCents
      : null;

  // Favorite key: prefer catalogItemId for new objects, modelUrl for legacy
  // const favoriteKey = obj?.catalogItemId ?? obj?.modelUrl ?? null;

  const thumbnailUrl = catalogItem?.thumbnailUrl
    ? getCatalogModelUrl(catalogItem.thumbnailUrl)
    : undefined;
  // Active option value IDs for the currently selected object (API path)
  const activeOptionIds =
    selectedOptionIds?.forId === selectedId ? selectedOptionIds.byName : {};

  const selectOption = (optName: string, valueId: string) => {
    if (!selectedId) return;
    setSelectedOptionIds((prev) => ({
      forId: selectedId,
      byName: {
        ...(prev?.forId === selectedId ? prev.byName : {}),
        [optName]: valueId,
      },
    }));
  };

  const setObjectDisplayOptions = useSetObjectDisplayOptions();
  const activeColorId = activeOptionIds["color"];
  const activeMaterialId = activeOptionIds["material"];
  const activeSizeId = activeOptionIds["size"];
  const objSizeW = obj?.size[0];
  const objSizeH = obj?.size[1];
  const objSizeD = obj?.size[2];
  useEffect(() => {
    if (!obj) return;
    const colorOptVal = apiColorValues.find((v) => v.id === activeColorId);
    const colorHex =
      (colorOptVal?.extraData?.hex as string | undefined) ??
      colorOptVal?.value ??
      undefined;
    const colorName = colorOptVal?.name ?? colorOptVal?.value;

    const materialOptVal = apiMaterialValues.find(
      (v) => v.id === activeMaterialId,
    );
    const materialName = materialOptVal?.name ?? materialOptVal?.value;

    // Mirror displayPrice IIFE logic exactly (including calcResizePrice path)
    let priceCents: number | undefined;
    if (catalogOptions) {
      const defaultSizeId =
        catalogOptions.defaultVariant.selectedOptionValueIds.find((id) =>
          apiSizeValues.some((v) => v.id === id),
        );
      const baseSizeVec = apiSizeValues.find((v) => v.id === defaultSizeId)
        ?.extraData?.size as [number, number, number] | undefined;
      const matchesPreset =
        apiSizeValues.length === 0 ||
        apiSizeValues.some((v) => {
          const s = v.extraData?.size as number[] | undefined;
          return (
            s != null &&
            Math.abs(s[0] - obj.size[0]) < 0.001 &&
            Math.abs(s[1] - obj.size[1]) < 0.001 &&
            Math.abs(s[2] - obj.size[2]) < 0.001
          );
        });
      const activeIds = Object.values(activeOptionIds);
      const matching =
        activeIds.length > 0
          ? (catalogOptions.variants.find((v) =>
              activeIds.every((id) => v.optionValueIds.includes(id)),
            ) ?? null)
          : null;
      if (!matchesPreset && baseSizeVec) {
        priceCents = calcResizePrice(
          catalogOptions.defaultVariant.priceCents,
          baseSizeVec,
          obj.size,
          colorName,
          materialName,
        );
      } else {
        priceCents = (matching ?? catalogOptions.defaultVariant).priceCents;
      }
    }
    setObjectDisplayOptions({
      id: obj.id,
      selectedColorHex: colorHex,
      selectedColorName: colorName,
      selectedMaterialName: materialName,
      variantPriceCents: priceCents,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    obj?.id,
    activeColorId,
    activeMaterialId,
    activeSizeId,
    objSizeW,
    objSizeH,
    objSizeD,
  ]);

  if (!obj) return null;

  const displayName =
    obj.name ?? obj.type.charAt(0).toUpperCase() + obj.type.slice(1);

  // const rating =
  //   catalogItem?.rating != null
  //     ? parseFloat(catalogItem.rating)
  //     : (meta?.rating ?? 0);
  // const reviewCount = catalogItem?.reviewCount ?? meta?.reviewCount ?? 0;

  const [x, y, z] = obj.position;

  const quat = obj.rotation ?? [0, 0, 0, 1];
  const euler = new Euler().setFromQuaternion(
    new Quaternion(quat[0], quat[1], quat[2], quat[3]),
    "YXZ",
  );
  const ex = (euler.x * 180) / Math.PI;
  const ey = (euler.y * 180) / Math.PI;
  const ez = (euler.z * 180) / Math.PI;

  const commitAxis = (axis: 0 | 1 | 2) => (value: number) => {
    const newPos: [number, number, number] = [...obj.position];
    newPos[axis] = value;
    updatePosition(obj.id, newPos);
  };

  const commitEuler = (axis: "x" | "y" | "z") => (valueDeg: number) => {
    const newEuler = new Euler(
      axis === "x" ? (valueDeg * Math.PI) / 180 : euler.x,
      axis === "y" ? (valueDeg * Math.PI) / 180 : euler.y,
      axis === "z" ? (valueDeg * Math.PI) / 180 : euler.z,
      "YXZ",
    );
    const q = new Quaternion().setFromEuler(newEuler);
    updateRotation(obj.id, [q.x, q.y, q.z, q.w]);
  };

  const handleReplaceWithRelated = (item: CatalogListItem) => {
    removeObject(obj.id);
    addObject({
      id: `obj-${Date.now()}`,
      name: item.nameVn ?? item.name,
      type: "model",
      position: obj.position,
      rotation: obj.rotation ?? [0, 0, 0, 1],
      color: item.color ?? "#4a90e2",
      size: item.size ?? obj.size,
      modelUrl: getCatalogModelUrl(item.modelUrl),
      placementType: item.placementType ?? obj.placementType,
      snappedToWall: obj.snappedToWall,
      catalogItemId: item.id,
    });
    setSelectedId(null);
  };

  // Find the variant whose optionValueIds contains all currently selected IDs
  const matchingVariant =
    catalogOptions != null && Object.keys(activeOptionIds).length > 0
      ? (catalogOptions.variants.find((v) =>
          Object.values(activeOptionIds).every((id) =>
            v.optionValueIds.includes(id),
          ),
        ) ?? null)
      : null;

  // Dynamic price: API path uses matched variant price, legacy path scales from meta
  const displayPrice = (() => {
    if (catalogOptions != null) {
      // Detect drag-resize: check if current obj.size matches any preset size option.
      // If no preset matches, the user resized via drag handles — apply the volume formula.
      const defaultSizeId =
        catalogOptions.defaultVariant.selectedOptionValueIds.find((id) =>
          apiSizeValues.some((v) => v.id === id),
        );
      const baseSizeVec = apiSizeValues.find((v) => v.id === defaultSizeId)
        ?.extraData?.size as [number, number, number] | undefined;

      const matchesPreset =
        apiSizeValues.length === 0 ||
        apiSizeValues.some((v) => {
          const s = v.extraData?.size as number[] | undefined;
          return (
            s != null &&
            Math.abs(s[0] - obj.size[0]) < 0.001 &&
            Math.abs(s[1] - obj.size[1]) < 0.001 &&
            Math.abs(s[2] - obj.size[2]) < 0.001
          );
        });

      if (!matchesPreset && baseSizeVec) {
        const activeColorName = apiColorValues.find(
          (v) => v.id === activeOptionIds["color"],
        )?.name;
        const activeMaterialName = apiMaterialValues.find(
          (v) => v.id === activeOptionIds["material"],
        )?.name;
        return calcResizePrice(
          catalogOptions.defaultVariant.priceCents,
          baseSizeVec,
          obj.size,
          activeColorName ?? undefined,
          activeMaterialName ?? undefined,
        );
      }

      return (matchingVariant ?? catalogOptions.defaultVariant).priceCents;
    }
    return 0;
  })();

  const showPriceStrip = apiPrice !== null;

  return (
    <div className="absolute top-14 right-2 h-[calc(100%-3.5rem)] z-55">
      <div
        className="bg-white w-96 h-full mb-10 shadow-(--shadow-style) rounded-[14px] flex flex-col"
        style={{ border: "var(--border-style)" }}
      >
        <div className="flex items-center bg-[#ECECEC] rounded-xl p-1 m-4">
          <button
            onClick={() => setViewMode("info")}
            className={viewMode === "info" ? activeClass : inactiveClass}
          >
            <span className="text-sm font-light">Thông tin</span>
          </button>
        </div>
        <div className="px-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-(--sub-color) font-light">Chi tiết</p>
            {/* {favoriteKey && (
              <button
                aria-label={
                  favoriteIds.has(favoriteKey)
                    ? "Bỏ yêu thích"
                    : "Thêm vào yêu thích"
                }
                onClick={() => toggleFavorite(favoriteKey)}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all"
              >
                {favoriteIds.has(favoriteKey) ? (
                  <FavoriteFilledIcon />
                ) : (
                  <FavoriteIcon />
                )}
              </button>
            )} */}
          </div>
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-xl font-bold leading-tight flex-1 min-w-0">
              {displayName}
            </h2>
          </div>

          {/* Star rating row */}
          {/* <div className="flex items-center gap-2 mt-3">
            <div className="bg-(--highlight-tab-color) rounded">
              <span className="text-sm text-white py-0.5 px-1">
                {rating.toFixed(1)}
              </span>
            </div>
            <StarRating rating={rating} />
            <span className="text-xs text-[#666666]">
              ({reviewCount} đánh giá)
            </span>
          </div> */}

          {/* Preview & description */}
          {obj.modelUrl && (
            <div
              className="mt-3 rounded-xl overflow-hidden"
              style={{ height: 120 }}
            >
              <ShapePreview
                shape="model"
                color="#D2B48C"
                modelUrl={obj.modelUrl}
                thumbnailUrl={thumbnailUrl}
              />
            </div>
          )}
          {(catalogItem?.descriptionVn ?? catalogItem?.description) && (
            <p className="mt-2 text-sm text-(--secondary-sub-color) leading-relaxed line-clamp-3">
              {catalogItem?.descriptionVn ?? catalogItem?.description}
              catalogItem?.description
            </p>
          )}
        </div>

        {/* ── Price strip ── */}
        {showPriceStrip && (
          <div className="bg-[#F8EEE3] px-4 py-3 my-3 flex items-center justify-between">
            <div className="flex gap-2.5 flex-col">
              <p className="text-xs text-(--secondary-sub-color) tracking-wider font-medium">
                Giá hiện tại
              </p>
              <p className="text-3xl font-extrabold leading-none tracking-tight">
                {displayPrice.toLocaleString()} đ
              </p>
              <p className="text-xs text-(--secondary-sub-color) tracking-wider font-medium">
                Giá chưa bao gồm VAT
              </p>
            </div>
            {/* {meta.brand && (
              <span className="text-sm font-semibold text-slate-500 bg-white rounded-full px-4 py-1.5 border border-slate-200 shadow-sm whitespace-nowrap">
                {meta.brand}
              </span>
            )} */}
          </div>
        )}

        {/* ── Scrollable body ── */}
        <div className="px-4 mb-4 overflow-y-auto flex-1">
          {catalogOptions && (
            <Accordion
              type="multiple"
              defaultValue={[
                "color",
                "size",
                "material",
                "position",
                "rotation",
              ]}
            >
              {/* Color swatches */}
              {apiColorValues.length > 0 && (
                <AccordionItem value="color" className="border-0">
                  <AccordionTrigger className="text-sm text-(--sub-color) font-light py-3 hover:no-underline">
                    Màu sắc
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="flex gap-2.5 flex-wrap py-2 px-1">
                      {apiColorValues.map((v) => {
                        const hex = v.extraData?.hex ?? v.value;
                        return (
                          <button
                            key={v.id}
                            title={v.name ?? v.value}
                            onClick={() => selectOption("color", v.id)}
                            className={
                              "w-8 h-8 rounded-full border-[3px] shrink-0 transition-all " +
                              (activeOptionIds["color"] === v.id
                                ? "border-(--primary-color) scale-125 shadow-md shadow-(--primary-color)/40"
                                : "border-white hover:border-slate-300 hover:scale-110")
                            }
                            style={{
                              backgroundColor: hex,
                              boxShadow:
                                activeOptionIds["color"] === v.id
                                  ? undefined
                                  : "0 0 0 1px #e2e8f0",
                            }}
                          />
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}

              {/* Size pills */}
              {apiSizeValues.length > 0 && (
                <AccordionItem value="size" className="border-0">
                  <AccordionTrigger className="text-sm text-(--sub-color) font-light py-3 hover:no-underline">
                    Kích thước ( Cao x Dài x Rộng )
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="flex gap-2 flex-wrap pb-1">
                      {apiSizeValues.map((v) => {
                        const sizeVec = v.extraData?.size;
                        return (
                          <button
                            key={v.id}
                            onClick={() => {
                              if (sizeVec) {
                                updateSize(obj.id, sizeVec);
                                selectOption("size", v.id);
                              }
                            }}
                            className={
                              "text-sm px-4 py-1.5 rounded-full border font-medium transition-all " +
                              (activeOptionIds["size"] === v.id
                                ? "bg-(--primary-color) text-white border-(--primary-color) shadow-md shadow-(--primary-color)/40"
                                : "bg-white text-slate-600 border-slate-200 hover:border-(--primary-color) hover:text-(--primary-color)")
                            }
                          >
                            {v.name ?? v.value}
                          </button>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}

              {/* Material pills */}
              {apiMaterialValues.length > 0 && (
                <AccordionItem value="material" className="border-0">
                  <AccordionTrigger className="text-sm text-(--sub-color) font-light py-3 hover:no-underline">
                    Chất liệu
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="flex gap-2 flex-wrap pb-1">
                      {apiMaterialValues.map((v) => (
                        <button
                          key={v.id}
                          onClick={() => selectOption("material", v.id)}
                          className={
                            "text-sm px-4 py-1.5 rounded-full border font-medium transition-all " +
                            (activeOptionIds["material"] === v.id
                              ? "bg-(--primary-color) text-white border-(--primary-color) shadow-md shadow-(--primary-color)/40"
                              : "bg-white text-slate-600 border-slate-200 hover:border-(--primary-color) hover:text-(--primary-color)")
                          }
                        >
                          {v.name ?? v.value}
                        </button>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}

              <AccordionItem value="position" className="border-0">
                <AccordionTrigger className="text-sm text-(--sub-color) font-light py-3 hover:no-underline">
                  Vị trí
                </AccordionTrigger>
                <AccordionContent>
                  <div className="grid grid-cols-2 gap-x-4">
                    <AxisInput
                      label="X"
                      live={x}
                      unit="m"
                      onCommit={commitAxis(0)}
                    />
                    <AxisInput
                      label="Y"
                      live={y}
                      unit="m"
                      onCommit={commitAxis(1)}
                    />
                    <AxisInput
                      label="Z"
                      live={z}
                      unit="m"
                      onCommit={commitAxis(2)}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="rotation" className="border-0">
                <AccordionTrigger className="text-sm text-(--sub-color) font-light py-3 hover:no-underline">
                  Xoay
                </AccordionTrigger>
                <AccordionContent>
                  <div className="grid grid-cols-2 gap-x-4">
                    <AxisInput
                      label="Quay"
                      live={ey}
                      unit="°"
                      onCommit={commitEuler("y")}
                    />
                    <AxisInput
                      label="Nghiêng"
                      live={ex}
                      unit="°"
                      onCommit={commitEuler("x")}
                    />
                    <AxisInput
                      label="Lật"
                      live={ez}
                      unit="°"
                      onCommit={commitEuler("z")}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}

          {/* ── Related items ── */}
          {(relatedLoading || relatedItems.length > 0) && (
            <div className="mt-2 pb-2">
              <p className="text-sm text-(--sub-color) font-light mb-2">
                Sản phẩm tương tự
              </p>
              {relatedLoading ? (
                <div className="grid grid-cols-2 gap-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div
                      key={i}
                      className="flex flex-col items-center gap-1.5 p-2 rounded-2xl bg-zinc-50"
                    >
                      <div className="w-full aspect-square bg-zinc-100 rounded-xl animate-pulse" />
                      <div className="w-3/4 h-3 bg-zinc-100 rounded animate-pulse" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {relatedItems.map((item) => {
                    const itemThumbnailUrl = item.thumbnailUrl
                      ? getCatalogModelUrl(item.thumbnailUrl)
                      : undefined;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleReplaceWithRelated(item)}
                        className="flex flex-col items-center gap-1.5 p-2 rounded-2xl bg-zinc-50 hover:bg-zinc-100 transition-colors text-left w-full"
                      >
                        <div className="w-full aspect-square rounded-xl overflow-hidden">
                          <ShapePreview
                            shape="model"
                            color={item.color ?? "#4a90e2"}
                            modelUrl={getCatalogModelUrl(item.modelUrl)}
                            thumbnailUrl={itemThumbnailUrl}
                          />
                        </div>
                        <span className="text-xs text-slate-600 text-center line-clamp-2 w-full leading-tight">
                          {item.nameVn ?? item.name}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
