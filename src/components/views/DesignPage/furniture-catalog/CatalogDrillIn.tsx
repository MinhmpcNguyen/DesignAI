import { useCatalogItems } from "@/hooks/useCatalog";
import { CatalogCategory, CatalogListItem } from "@/types/api";
import { ChevronLeft } from "lucide-react";
import { useMemo } from "react";
import SkeletonCard from "./SkeletonCard";
import CatalogCard from "./CatalogCard";
import { getCatalogModelUrl } from "@/services/api/baseUrl";

interface CategoryDrillInProps {
  cat: CatalogCategory;
  searchQuery: string;
  onBack: () => void;
  onDragStart: (e: React.DragEvent, item: CatalogListItem) => void;
}

export default function CategoryDrillIn({
  cat,
  searchQuery,
  onBack,
  onDragStart,
}: CategoryDrillInProps) {
  const { data, isLoading } = useCatalogItems(cat.id, { enabled: true });

  const items = useMemo(() => {
    if (!data?.items) return [];
    if (!searchQuery.trim()) return data.items;
    const q = searchQuery.toLowerCase();
    return data.items.filter(
      (item) =>
        (item.nameVn ?? item.name).toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q),
    );
  }, [data, searchQuery]);

  const displayName = cat.nameVn ?? cat.name;

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
          {displayName}
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
            : "Danh mục trống"}
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
