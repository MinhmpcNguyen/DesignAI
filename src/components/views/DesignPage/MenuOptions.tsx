import { useState } from "react";
import { TMenuOption } from "@/types/global";
import {
  FloorPlanIcon,
  ProductIcon,
  ProjectsIcon,
  ToolIcon,
} from "../../icons";

const menuOptions: TMenuOption[] = [
  //   { id: "template", name: "Bản mẫu", icon: TemplateIcon },
  { id: "floor-plan", name: "Mặt bằng", icon: FloorPlanIcon },
  { id: "products", name: "Sản phẩm", icon: ProductIcon },
  { id: "tool", name: "Công cụ", icon: ToolIcon },
  { id: "project", name: "Dự án", icon: ProjectsIcon },
];

interface MenuOptionsProps {
  activeMenu?: string | null;
  onMenuChange?: (id: string) => void;
}

export default function MenuOptions({
  activeMenu,
  onMenuChange,
}: MenuOptionsProps = {}) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div
      className="absolute left-2 top-1/2 -translate-y-1/2 flex flex-col gap-1.5 bg-white items-center p-1.5 rounded-[14px] shadow-(--shadow-style) z-30"
      style={{ willChange: "transform", border: "var(--border-style)" }}
    >
      {menuOptions.map((option) => {
        const Icon = option.icon;
        const isActive = activeMenu === option.id;
        const isHovered = hovered === option.id;

        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onMenuChange?.(option.id)}
            onMouseEnter={() => setHovered(option.id)}
            onMouseLeave={() => setHovered(null)}
            className={`
              relative flex flex-col items-center justify-center
              w-14 h-13 rounded-[10px] cursor-pointer border-none
              text-(--primary-color)
              transition-colors duration-200
              ${isActive || isHovered ? "bg-[#eee0d0]" : "bg-transparent"}
            `}
          >
            <span
              className="flex flex-col items-center justify-center transition-transform duration-300 ease-[cubic-bezier(0.34,1.4,0.64,1)] origin-center"
              style={{
                transform: isHovered ? "scale(1)" : "scale(0.85)",
                position: "absolute",
                pointerEvents: "none",
              }}
            >
              <Icon isSelected={isActive} />
              <span
                className="text-[10px] leading-none whitespace-nowrap text-ellipsis max-w-12 transition-[max-height,opacity,margin-top] duration-300 ease-in-out"
                style={{
                  maxHeight: isHovered ? "16px" : "0px",
                  opacity: isHovered ? 1 : 0,
                  marginTop: isHovered ? "3px" : "0px",
                }}
              >
                {option.name}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
