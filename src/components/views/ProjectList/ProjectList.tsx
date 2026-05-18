"use client";

import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import {
  projectFiltersActions,
  projectFiltersSelectors,
} from "@/states/slices/projectFilters";
import ProjectFilterSelect from "./ProjectFilterSelect";
import YourProjectSection from "./YourProjectSection";
import { mockDataRecentProjects } from "@/app/(main)/home/page";
import Image from "next/image";
import { ChevronRight } from "lucide-react";

const ProjectList = () => {
  const dispatch = useAppDispatch();
  const filters = useAppSelector(projectFiltersSelectors.selectProjectFilters);
  const filterGroups = [
    {
      placeholder: "Loại",
      options: ["Tất cả", "Nhà phố", "Biệt thự", "Căn hộ"],
      value: filters.projectType,
      onDispatch: (nextValue: string) =>
        dispatch(projectFiltersActions.setProjectType(nextValue)),
    },
    {
      placeholder: "Diện tích",
      options: ["Tất cả", "Dưới 80m²", "80m² - 120m²", "Trên 120m²"],
      value: filters.areaRange,
      onDispatch: (nextValue: string) =>
        dispatch(projectFiltersActions.setAreaRange(nextValue)),
    },
    {
      placeholder: "Ngày sửa đổi",
      options: ["Mới nhất", "Cũ nhất", "7 ngày qua", "30 ngày qua"],
      value: filters.modifiedDate,
      onDispatch: (nextValue: string) =>
        dispatch(projectFiltersActions.setModifiedDate(nextValue)),
    },
  ];

  return (
    <div className="space-y-8 w-full">
      <div className="flex flex-col items-center gap-3">
        <div className="flex gap-3 items-center">
          {filterGroups.map((group) => (
            <ProjectFilterSelect
              key={group.placeholder}
              placeholder={group.placeholder}
              options={group.options}
              value={group.value}
              onDispatch={group.onDispatch}
            />
          ))}
        </div>
      </div>

      <YourProjectSection />

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
    </div>
  );
};

export default ProjectList;
