"use client";

import {
  FavoriteFilledIcon,
  ForRentIcon,
  HouseIcon,
  SearchIcon,
  ShopIcon,
  WorkIcon,
} from "@/components/icons";
import ComingSoon from "@/components/views/ComingSoon";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

interface RecentProject {
  id: number;
  name: string;
  thumbnailUrl: string;
  date: string;
}

interface AiGeneratedProject {
  id: number;
  style: string;
  thumbnailUrl: string;
}

export const mockDataRecentProjects: RecentProject[] = [
  {
    id: 1,
    name: "Dự án 1",
    thumbnailUrl: "/public/image/main/recently/recent_1.png",
    date: "2024-06-01 09:30 AM",
  },
  {
    id: 2,
    name: "Dự án 2",
    thumbnailUrl: "/public/image/main/recently/recent_2.png",
    date: "2024-06-02 10:00 AM",
  },
  {
    id: 3,
    name: "Dự án 3",
    thumbnailUrl: "/public/image/main/recently/recent_3.png",
    date: "2024-06-02 10:00 AM",
  },
  {
    id: 4,
    name: "Dự án 4",
    thumbnailUrl: "/public/image/main/recently/recent_4.png",
    date: "2024-06-02 10:00 AM",
  },
  {
    id: 5,
    name: "Dự án 5",
    thumbnailUrl: "/public/image/main/recently/recent_5.png",
    date: "2024-06-02 10:00 AM",
  },
];

const aiGeneratedProjects: AiGeneratedProject[] = [
  {
    id: 1,
    style: "Hiện đại",
    thumbnailUrl: "/public/image/main/ai-gen/ai_gen_1.png",
  },
  {
    id: 2,
    style: "Hiện đại",
    thumbnailUrl: "/public/image/main/ai-gen/ai_gen_2.png",
  },
  {
    id: 3,
    style: "Hiện đại",
    thumbnailUrl: "/public/image/main/ai-gen/ai_gen_3.png",
  },
  {
    id: 4,
    style: "Hiện đại",
    thumbnailUrl: "/public/image/main/ai-gen/ai_gen_4.png",
  },
];

export default function HomePage() {
  const [searchInput, setSearchInput] = useState("");
  const [favorites, setFavorites] = useState<Set<number>>(new Set());

  const toggleFavorite = (id: number) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex flex-col items-center gap-5 px-4 sm:px-0">
      <ComingSoon />
      <div className="text-(--primary-text) font-bold flex flex-col items-center text-2xl sm:text-3xl md:text-4xl lg:text-[40px] text-center leading-normal">
        <h1>Bạn muốn thiết kế không gian gì hôm nay?</h1>
        <h1>Hãy bắt đầu sáng tạo ngay nhé!</h1>
      </div>
      <div className="flex w-full sm:w-3/4 md:w-1/2 lg:w-[40%] items-center gap-2 border-2 border-[#B9B9B9] rounded-full px-4 sm:px-5 py-2.5 sm:py-4 focus-within:border-(--primary-color) focus-within:border-2 transition-colors">
        <SearchIcon />
        <input
          type="text"
          placeholder="Tìm kiếm trong hàng triệu mẫu"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
          className="flex-1 bg-transparent text-sm text-black placeholder-zinc-400 outline-none"
        />
        {searchInput && (
          <button
            onClick={() => setSearchInput("")}
            className="text-zinc-500 hover:text-black"
          >
            <X size={12} />
          </button>
        )}
      </div>

      <div className="flex flex-1 gap-9 text-[11px] items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <HouseIcon />
          <p>Nhà ở</p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <ForRentIcon />
          <p>Cho thuê</p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <WorkIcon />
          <p>Văn phòng</p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <ShopIcon />
          <p>Cửa hàng</p>
        </div>
      </div>

      {/* Recently Projects */}
      <div className="w-full flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-[24px] font-semibold">Gần đây</h1>
          <div className="flex items-center gap-1 text-(--primary-color) cursor-pointer">
            <p>Xem tất cả</p>
            <ChevronRight size={14} />
          </div>
        </div>
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {mockDataRecentProjects.map((project) => {
            const src = project.thumbnailUrl.replace(/^\/public/, "");
            return (
              <div key={project.id} className="w-full flex flex-col gap-2">
                <div className="w-full h-32 md:h-50 bg-zinc-100 rounded-lg overflow-hidden border border-[#e5e7eb] relative">
                  <Image
                    src={src}
                    alt={project.name}
                    fill
                    className="object-cover"
                  />
                </div>

                <p className="font-semibold text-sm truncate">{project.name}</p>
                <p className="text-xs text-zinc-500">{project.date}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* AI Generated Projects */}
      <div className="w-full flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-[24px] font-semibold">Khám phá mẫu do AI gen</h1>
          <div className="flex items-center gap-3">
            <button className="p-1.5 rounded-full bg-(--primary-border-color) cursor-pointer">
              <ChevronLeft size={14} />
            </button>
            <button className="p-1.5 rounded-full bg-(--primary-border-color) cursor-pointer">
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
        <div className="grid gap-6 grid-cols-2 sm:grid-cols-3 md:grid-cols-4">
          {aiGeneratedProjects.map((project) => {
            const src = project.thumbnailUrl.replace(/^\/public/, "");
            return (
              <div
                key={project.id}
                className="w-full flex flex-col gap-2 group"
              >
                <div className="w-full h-40 md:h-55 bg-zinc-100 rounded-lg overflow-hidden border border-[#e5e7eb] relative">
                  <Image
                    src={src}
                    alt={project.style}
                    fill
                    className="object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                  {/* Dark overlay */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  {/* Center buttons */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <div className="w-48 flex flex-col gap-2">
                      <button className="w-full bg-(--primary-color)/50 text-white text-xs font-medium px-3 py-2 rounded-md hover:bg-(--primary-color) transition-colors duration-200 cursor-pointer">
                        Áp dụng cho nhà của tôi
                      </button>
                      <button className="w-full bg-black/60 text-white text-xs font-medium px-3 py-2 rounded-md hover:bg-black transition-colors duration-200 cursor-pointer">
                        Xem chi tiết
                      </button>
                    </div>
                  </div>

                  {/* Style label bottom-left */}
                  <div className="absolute bottom-2 left-2 translate-y-2 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-300">
                    <span className="text-white text-xs font-semibold drop-shadow">
                      {project.style}
                    </span>
                  </div>
                  {/* Favorite icon top-right */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFavorite(project.id);
                    }}
                    className="absolute top-2 right-2 p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-300 cursor-pointer"
                  >
                    {favorites.has(project.id) ? (
                      <FavoriteFilledIcon />
                    ) : (
                      <FavoriteFilledIcon color="#D7d7d7" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
