"use client";

import { SHAPE_DRAG_TYPE } from "@/constant";
import { useCatalogCategories } from "@/hooks/useCatalog";
import { useCollections } from "@/hooks/useDesign";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import {
  useSetDraggingShape,
  useSetIsDragging,
} from "@/states/slices/drag/hooks";
import type { SceneObject } from "@/states/slices/objects/types";
import type { CatalogListItem, TDesignCollection } from "@/types/api";
import { UISelection } from "@/types/enum";
import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import { OtherIcon } from "../../../icons";
import CategoryDrillIn from "./CatalogDrillIn";
import CollectionDrillIn from "./CollectionDrillIn";
import CollectionList from "./CollectionList";
import SearchResults from "./SearchResults";
import { CATEGORY_ICONS, SEARCH_QUICK_TAGS } from "@/constant/design";

interface FurnitureCatalogOverlayProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function FurnitureCatalogOverlay({
  open: openProp,
  onOpenChange,
}: FurnitureCatalogOverlayProps = {}) {
  const [openLocal, setOpenLocal] = useState(true);
  const open = openProp !== undefined ? openProp : openLocal;
  const setOpen = (value: boolean) => {
    setOpenLocal(value);
    onOpenChange?.(value);
  };
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [activeTab, setActiveTab] = useState<UISelection>(
    UISelection.Collections,
  );
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(
    null,
  );

  const setIsDragging = useSetIsDragging();
  const setDraggingShape = useSetDraggingShape();

  const { data: categoriesData, isLoading: categoriesLoading } =
    useCatalogCategories();
  const categories = categoriesData?.categories ?? [];

  const { data: collectionsData, isLoading: collectionsLoading } =
    useCollections({ enabled: activeTab === UISelection.Collections });
  const collections = collectionsData ?? [];

  const isSearching = searchQuery.trim() !== "";

  const handleDragStart = useCallback(
    (e: React.DragEvent, item: CatalogListItem) => {
      e.dataTransfer.setData(SHAPE_DRAG_TYPE, "model");
      e.dataTransfer.effectAllowed = "copy";
      setIsDragging(true);
      setDraggingShape({
        shape: "model",
        name: item.nameVn ?? item.name,
        color: item.color ?? "#4a90e2",
        size: item.size ?? [1, 1, 1],
        modelUrl: getCatalogModelUrl(item.modelUrl),
        placementType: item.placementType,
        objectRole: item.objectRole,
        catalogItemId: item.id,
      });
    },
    [setIsDragging, setDraggingShape],
  );

  const handleCollectionDragStart = useCallback(
    (e: React.DragEvent, collection: TDesignCollection) => {
      e.dataTransfer.setData(SHAPE_DRAG_TYPE, "collection");
      e.dataTransfer.effectAllowed = "copy";
      setIsDragging(true);
      setDraggingShape({
        shape: "model",
        name: collection.name,
        color: "#4a90e2",
        size: [1, 1, 1],
        collectionId: collection.id,
        collectionObjects: (collection.objects as unknown as SceneObject[]).map(
          (obj) => ({
            ...obj,
            modelUrl: obj.modelUrl
              ? getCatalogModelUrl(obj.modelUrl)
              : obj.modelUrl,
          }),
        ),
      });
    },
    [setIsDragging, setDraggingShape],
  );

  // Debounce search input → update `searchQuery` after 300ms
  useEffect(() => {
    const id = window.setTimeout(() => setSearchQuery(searchInput), 300);
    return () => clearTimeout(id);
  }, [searchInput]);

  return (
    <>
      {/* Object Palette - Drawer */}
      <div
        className={`absolute top-14 left-22 h-[calc(100%-3.5rem)] z-55 transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "-translate-x-102"
        }`}
      >
        <div
          className="w-70 h-full bg-white shadow-(--shadow-style) rounded-2xl flex flex-col overflow-hidden"
          style={{ border: "var(--border-style)" }}
        >
          {/* Product header (matches the provided catalog UI) */}
          <div className="bg-white border-b border-zinc-200">
            <div className="px-4 py-3 flex gap-4 text-sm">
              {(Object.values(UISelection) as UISelection[]).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab);
                    setSearchQuery("");
                    setSearchInput("");
                    setSelectedCategory(null);
                    setSelectedCollection(null);
                  }}
                  className={
                    activeTab === tab
                      ? "flex flex-1 justify-center text-(--highlight-tab-color) font-medium border-b-2 border-(--highlight-tab-color) pb-1 whitespace-nowrap"
                      : "flex flex-1 justify-center text-(--sub-color) font-medium hover:text-(--highlight-tab-color) transition-colors whitespace-nowrap"
                  }
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {/* Search */}
          <div className="px-4 pt-3 pb-2">
            <div className="flex items-center gap-2 border border-zinc-200 rounded-lg px-3 py-2 relative">
              <Search size={16} className="text-zinc-500 shrink-0" />
              <input
                type="text"
                placeholder={
                  activeTab === UISelection.Collections
                    ? "Tìm bộ sưu tập..."
                    : "Tìm kiếm sản phẩm..."
                }
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.stopPropagation()}
                className="flex-1 bg-transparent px-0 text-sm text-black placeholder-zinc-400 outline-none"
              />
              {searchInput && (
                <button
                  onClick={() => setSearchInput("")}
                  className="text-zinc-500 hover:text-black absolute right-2"
                >
                  <X size={12} />
                </button>
              )}
            </div>
            {activeTab === UISelection.PublicFurniture && (
              <div className="mt-2 flex flex-wrap gap-2">
                {SEARCH_QUICK_TAGS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => {
                      setSearchInput(tag);
                      setSearchQuery(tag);
                    }}
                    className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-700 hover:border-(--primary-color,#C8A882) hover:text-(--primary-color,#8B6B3E) transition-colors"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Main panel content — tab-conditional */}
          <div className="overflow-y-auto flex-1 px-4 pb-6">
            {activeTab === UISelection.Collections ? (
              /* ── Bộ sưu tập tab ── */
              selectedCollection && !isSearching ? (
                <CollectionDrillIn
                  collection={
                    collections.find((c) => c.id === selectedCollection)!
                  }
                  searchQuery={searchQuery}
                  onBack={() => setSelectedCollection(null)}
                  onDragStart={handleDragStart}
                />
              ) : (
                <CollectionList
                  collections={collections}
                  isLoading={collectionsLoading}
                  searchQuery={searchQuery}
                  onDragStart={handleCollectionDragStart}
                  onSelect={setSelectedCollection}
                />
              )
            ) : categoriesLoading ? (
              <div className="grid grid-cols-2 gap-3 pt-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-28 bg-zinc-100 rounded-xl animate-pulse"
                  />
                ))}
              </div>
            ) : categories.length === 0 ? (
              <p className="text-xs text-zinc-500 text-center py-6">
                Không tải được danh mục sản phẩm.
              </p>
            ) : selectedCategory && !isSearching ? (
              <CategoryDrillIn
                cat={categories.find((c) => c.id === selectedCategory)!}
                searchQuery={searchQuery}
                onBack={() => setSelectedCategory(null)}
                onDragStart={handleDragStart}
              />
            ) : isSearching ? (
              <SearchResults
                searchQuery={searchQuery}
                onDragStart={handleDragStart}
              />
            ) : (
              <div className="grid grid-cols-2 gap-3 pt-2">
                {categories.map((cat) => {
                  const displayName = cat.nameVn ?? cat.name;
                  const Icon =
                    CATEGORY_ICONS[displayName] ??
                    CATEGORY_ICONS[cat.name] ??
                    OtherIcon;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setSelectedCategory(cat.id)}
                      className="flex flex-col items-center gap-1.5 p-1.5 rounded-xl bg-[#fafafa] border border-(--primary-border-color) transition-all duration-150 cursor-pointer hover:border-(--primary-color,#C8A882) hover:shadow-md"
                    >
                      <div className="text-sm font-light text-(--secondary-color)">
                        {displayName}
                      </div>
                      <div className="bg-white rounded-lg w-full h-20 overflow-hidden flex items-center justify-center">
                        <Icon />
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Toggle button — center-right edge of panel, only visible when open */}
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label="Đóng bảng"
            style={{ border: "var(--border-style)" }}
            className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-full bg-white rounded-r-xl px-2 py-4 shadow-(--shadow-style) hover:bg-zinc-50 active:scale-95 transition-all duration-150 text-zinc-500 hover:text-zinc-800 ${open ? "" : "hidden"}`}
          >
            {open ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
        </div>
      </div>
    </>
  );
}
