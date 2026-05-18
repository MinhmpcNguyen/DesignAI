import { useCatalogAllItems } from "@/hooks/useCatalog";
import { CatalogListItem } from "@/types/api";
import { useEffect, useState } from "react";
import SkeletonCard from "./SkeletonCard";
import CatalogCard from "./CatalogCard";
import { getCatalogModelUrl } from "@/services/api/baseUrl";

interface SearchResultsProps {
  searchQuery: string;
  onDragStart: (e: React.DragEvent, item: CatalogListItem) => void;
}

export default function SearchResults({
  searchQuery,
  onDragStart,
}: SearchResultsProps) {
  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const trimmed = debouncedQuery.trim();
  const { data, isLoading } = useCatalogAllItems({
    search: trimmed,
    enabled: !!trimmed,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 pt-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <p className="text-xs text-zinc-500 text-center py-6">
        Không có kết quả cho &ldquo;{searchQuery}&rdquo;
      </p>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 pt-2">
      {data.items.map((item) => (
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
  );
}
