import { LivingRoomIcon } from "@/components/icons";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import { TDesignCollection } from "@/types/api";

interface CollectionCardProps {
  collection: TDesignCollection;
  onDragStart: (e: React.DragEvent, collection: TDesignCollection) => void;
  onSelect: (id: string) => void;
}

export default function CollectionCard({
  collection,
  onDragStart,
  onSelect,
}: CollectionCardProps) {
  const imgUrl = collection.image1Url
    ? getCatalogModelUrl(collection.image1Url)
    : collection.image2Url
      ? getCatalogModelUrl(collection.image2Url)
      : null;
  return (
    <li
      draggable
      onDragStart={(e) => onDragStart(e, collection)}
      onClick={() => onSelect(collection.id)}
      className="flex flex-col items-center gap-1.5 p-2 rounded-2xl border border-transparent bg-white/70 hover:border-(--primary-color,#C8A882) hover:shadow-md cursor-grab active:cursor-grabbing select-none transition-all duration-200"
    >
      <div className="relative w-full aspect-square bg-(--primary-color,#C8A882)/10 rounded-xl overflow-hidden">
        {imgUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imgUrl}
            alt={collection.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-300">
            <LivingRoomIcon />
          </div>
        )}
      </div>
      <span className="text-xs font-semibold text-(--secondary-color) text-center leading-tight line-clamp-2 w-full">
        {collection.name}
      </span>
      {collection.objects.length > 0 && (
        <div className="text-[10px] text-zinc-500">
          {collection.objects.length} vật phẩm
        </div>
      )}
    </li>
  );
}
