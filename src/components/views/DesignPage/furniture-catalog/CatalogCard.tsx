import ShapePreview from "@/components/drag-n-drop/ShapePreview";
import { getCatalogModelUrl } from "@/services/api/baseUrl";
import { CatalogListItem } from "@/types/api";
import { useGLTF } from "@react-three/drei";

interface CatalogCardProps {
  item: CatalogListItem;
  thumbnailUrl?: string;
  onDragStart: (e: React.DragEvent, item: CatalogListItem) => void;
  showCategory?: boolean;
}

export default function CatalogCard({
  item,
  thumbnailUrl,
  onDragStart,
  showCategory,
}: CatalogCardProps) {
  const fullModelUrl = item.modelUrl
    ? getCatalogModelUrl(item.modelUrl)
    : undefined;

  return (
    <li
      draggable
      onDragStart={(e) => onDragStart(e, item)}
      onMouseEnter={() => {
        if (fullModelUrl) useGLTF.preload(fullModelUrl);
      }}
      className="flex flex-col items-center gap-1.5 p-2 rounded-2xl border border-transparent bg-white/70 hover:border-(--primary-color,#C8A882) hover:shadow-md cursor-grab active:cursor-grabbing select-none transition-all duration-200"
    >
      <div className="relative w-full aspect-square bg-(--primary-color,#C8A882)/10 rounded-xl overflow-hidden">
        <ShapePreview
          shape="model"
          color={item.color ?? "#4a90e2"}
          size={200}
          modelUrl={fullModelUrl}
          thumbnailUrl={thumbnailUrl}
        />
      </div>
      <span className="text-xs font-semibold text-(--secondary-color) text-center leading-tight line-clamp-2 w-full">
        {item.nameVn ?? item.name}
      </span>
      {showCategory && (
        <div className="text-[10px] text-zinc-500 text-center w-full">
          {item.categoryId}
        </div>
      )}
    </li>
  );
}
