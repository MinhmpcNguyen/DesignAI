import { useCatalogItemsBatch } from "@/hooks/useCatalog";
import { CatalogListItem, TDesignCollection } from "@/types/api";
import { ChevronLeft } from "lucide-react";
import { useMemo } from "react";
import SkeletonCard from "./SkeletonCard";
import CatalogCard from "./CatalogCard";
import { getCatalogModelUrl } from "@/services/api/baseUrl";

interface CollectionDrillInProps {
  collection: TDesignCollection;
  searchQuery: string;
  onBack: () => void;
  onDragStart: (e: React.DragEvent, item: CatalogListItem) => void;
}

export default function CollectionDrillIn({
  collection,
  searchQuery,
  onBack,
  onDragStart,
}: CollectionDrillInProps) {
  // Extract unique catalogItemIds from the schema-free objects array
  const catalogItemIds = useMemo(() => {
    const ids = collection.objects
      .map((o) => (o as Record<string, unknown>).catalogItemId)
      .filter((id): id is string => typeof id === "string" && id.length > 0);
    return [...new Set(ids)];
  }, [collection.objects]);

  const results = useCatalogItemsBatch(catalogItemIds);

  const items = useMemo(() => {
    const loaded = results
      .map((r) => r.data)
      .filter((item): item is CatalogListItem => item != null);
    if (!searchQuery.trim()) return loaded;
    const q = searchQuery.toLowerCase();
    return loaded.filter(
      (item) =>
        (item.nameVn ?? item.name).toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q),
    );
  }, [results, searchQuery]);

  const isLoading = results.some((r) => r.isLoading);

  return (
    <>
      <div className="sticky top-0 z-10 bg-white flex items-center gap-1">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center text-black font-semibold rounded-md hover:bg-zinc-100 hover:underline transition-colors"
          aria-label="Quay lại"
        >
          <ChevronLeft size={18} />
        </button>
        <div className="flex-1 text-xs text-[#020101] truncate">
          {collection.name}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-2 grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-6">
          {searchQuery
            ? `Không có kết quả cho "${searchQuery}"`
            : "Bộ sưu tập không có sản phẩm"}
        </p>
      ) : (
        <div className="mt-2 grid grid-cols-2 gap-3">
          {items.map((item) => (
            <CatalogCard
              key={item.id}
              item={item}
              thumbnailUrl={
                item.thumbnailUrl
                  ? getCatalogModelUrl(item.thumbnailUrl)
                  : undefined
              }
              onDragStart={onDragStart}
            />
          ))}
        </div>
      )}
    </>
  );
}
