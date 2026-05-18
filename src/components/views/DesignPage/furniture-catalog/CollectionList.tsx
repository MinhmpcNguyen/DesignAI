import { TDesignCollection } from "@/types/api";
import { useMemo } from "react";
import SkeletonCard from "./SkeletonCard";
import CollectionCard from "./CollectionCard";

interface CollectionListProps {
  collections: TDesignCollection[];
  isLoading: boolean;
  searchQuery: string;
  onDragStart: (e: React.DragEvent, collection: TDesignCollection) => void;
  onSelect: (id: string) => void;
}

export default function CollectionList({
  collections,
  isLoading,
  searchQuery,
  onDragStart,
  onSelect,
}: CollectionListProps) {
  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return collections;
    const q = searchQuery.toLowerCase();
    return collections.filter((c) => c.name.toLowerCase().includes(q));
  }, [collections, searchQuery]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 pt-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <p className="text-xs text-zinc-500 text-center py-6">
        {searchQuery
          ? `Không có kết quả cho "${searchQuery}"`
          : "Không có bộ sưu tập nào"}
      </p>
    );
  }

  return (
    <ul className="grid grid-cols-2 gap-3 pt-2">
      {filtered.map((collection) => (
        <CollectionCard
          key={collection.id}
          collection={collection}
          onDragStart={onDragStart}
          onSelect={onSelect}
        />
      ))}
    </ul>
  );
}
