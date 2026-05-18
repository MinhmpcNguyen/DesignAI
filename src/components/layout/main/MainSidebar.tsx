"use client";

import {
  HomePageIcon,
  ProjectsIcon,
  SamplesIcon,
  NewDesignIcon,
} from "@/components/icons";
import { TMenuOption } from "@/types/global";
import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForkDesign } from "@/hooks/useDesign";
import { disposeThumbnailRenderer } from "@/lib/thumbnailRenderer";

const menuOptions: TMenuOption[] = [
  { id: "home", name: "Trang chủ", icon: HomePageIcon },
  { id: "project", name: "Dự án", icon: ProjectsIcon },
  { id: "sample", name: "Mẫu", icon: SamplesIcon },
];

export default function MainSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [hovered, setHovered] = useState<string | null>(null);
  const { mutateAsync: createProject } = useForkDesign();
  const menuIds = new Set(menuOptions.map((option) => option.id));
  const menuFromQuery = searchParams.get("menu");
  const pathSegment = pathname.split("/").filter(Boolean)[0];
  const activeMenu =
    (menuFromQuery && menuIds.has(menuFromQuery) && menuFromQuery) ||
    (menuIds.has(pathSegment) ? pathSegment : "home");

  const handleCreateProject = async () => {
    const newProject = await createProject({ title: "Dự án mới" });
    disposeThumbnailRenderer();
    router.push(
      `/design?id=${newProject.id}&title=${encodeURIComponent(newProject.title)}`,
    );
  };

  function handleMenuChange(id: string) {
    router.push(`/${id}`);
  }

  return (
    <div className="flex flex-col items-center p-2 gap-7">
      <button onClick={handleCreateProject} type="button">
        <div className="flex flex-col justify-center items-center gap-2 rounded-[10px] cursor-pointer hover:scale-105 duration-300 text-(--primary-color) w-14 h-14">
          <NewDesignIcon />
          <span className="text-[10px] text-(--secondary-color) leading-none whitespace-nowrap font-medium">
            Tạo mới
          </span>
        </div>
      </button>

      <div className="relative flex flex-col items-center gap-4">
        {menuOptions.map((option) => {
          const Icon = option.icon;
          const isActive = activeMenu === option.id;
          const isHovered = hovered === option.id;

          return (
            <button
              key={option.id}
              type="button"
              onMouseEnter={() => setHovered(option.id)}
              onMouseLeave={() => setHovered(null)}
              aria-pressed={isActive}
              onClick={() => handleMenuChange(option.id)}
              className={`
              relative flex flex-col items-center justify-center
              w-14 h-14 rounded-[10px] cursor-pointer border-none
              text-(--primary-color)
              transition-colors duration-200 hover:bg-[#eee0d0] hover:scale-1.5
              ${isActive ? "bg-[#eee0d0]" : "bg-transparent"}
            `}
            >
              <div
                className="flex flex-col justify-center items-center gap-2 transition-transform duration-300 ease-[cubic-bezier(0.34,1.4,0.64,1)] origin-center"
                style={{
                  transform: isHovered ? "scale(1)" : "scale(0.85)",
                  position: "absolute",
                  pointerEvents: "none",
                }}
              >
                <Icon isSelected={isActive} />
                <span
                  className={`text-[10px] leading-none whitespace-nowrap font-medium ${isActive ? "text-[#78591F]" : "text-[#757575]"}`}
                >
                  {option.name}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
