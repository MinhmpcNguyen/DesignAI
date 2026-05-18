"use client";

import {
  useDeleteDesign,
  useForkDesign,
  useMyDesigns,
} from "@/hooks/useDesign";
import { disposeThumbnailRenderer } from "@/lib/thumbnailRenderer";
import {
  Loader2,
  Plus,
  Search,
  Trash2,
  X,
  ChevronLeft,
  Circle,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import CreateProjectDialog from "../ProjectList/CreateProjectDialog";
import DeleteProjectDialog from "../ProjectList/DeleteProjectDialog";

interface ProjectSidebarPanelProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const formatProjectUpdatedAt = (updatedAt: string) => {
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return "Sửa đổi: --";
  return `Sửa đổi: ${date.toLocaleDateString("vi-VN")} ${date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
};

export default function ProjectSidebarPanel({
  open: openProp,
  onOpenChange,
}: ProjectSidebarPanelProps = {}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentDesignId = searchParams.get("id");
  const [openLocal, setOpenLocal] = useState(false);
  const [search, setSearch] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const open = openProp !== undefined ? openProp : openLocal;

  const setOpen = (value: boolean) => {
    setOpenLocal(value);
    onOpenChange?.(value);
  };

  const { data: myProjects, isLoading } = useMyDesigns();
  const { mutateAsync: createProject, isPending: isCreatingProject } =
    useForkDesign();
  const { mutate: deleteProject, isPending: isDeletingProject } =
    useDeleteDesign();

  const filteredProjects = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return myProjects ?? [];
    return (myProjects ?? []).filter((project) =>
      project.title.toLowerCase().includes(q),
    );
  }, [myProjects, search]);

  const handleCreateProject = async (title: string) => {
    const newProject = await createProject({ title });
    setIsCreateDialogOpen(false);
    disposeThumbnailRenderer();
    router.push(
      `/design?id=${newProject.id}&title=${encodeURIComponent(newProject.title)}`,
    );
  };

  const handleOpenProject = (projectId: string, title: string) => {
    disposeThumbnailRenderer();
    router.push(`/design?id=${projectId}&title=${encodeURIComponent(title)}`);
  };

  const handleDeleteConfirm = () => {
    if (!confirmDeleteId) return;
    deleteProject(confirmDeleteId, {
      onSettled: () => setConfirmDeleteId(null),
    });
  };

  return (
    <>
      <div
        className={`absolute top-14 left-22 h-[calc(100%-3.5rem)] z-55 transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "-translate-x-102"
        }`}
      >
        <div
          className="relative w-80 h-full bg-white shadow-(--shadow-style) rounded-2xl flex flex-col overflow-hidden"
          style={{ border: "var(--border-style)" }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
            <span className="text-sm font-medium text-(--secondary-color)">
              Tên dự án
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors"
              aria-label="Đóng bảng dự án"
            >
              <X size={16} />
            </button>
          </div>

          <div className="px-4 py-3 border-b border-zinc-100 space-y-2">
            <button
              type="button"
              onClick={() => setIsCreateDialogOpen(true)}
              className="w-full h-10 flex items-center justify-center gap-2 rounded-lg bg-(--primary-color) hover:opacity-95 text-white text-sm font-medium transition-opacity"
            >
              <Plus size={16} />
              Tạo dự án mới
            </button>
            <div className="flex items-center gap-2 border border-zinc-200 rounded-lg px-3 py-2">
              <Search size={14} className="text-zinc-400 shrink-0" />
              <input
                type="text"
                placeholder="Tìm theo tên dự án..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.stopPropagation()}
                className="flex-1 bg-transparent text-sm text-black placeholder-zinc-400 outline-none"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-3">
            {isLoading ? (
              <div className="h-full flex items-center justify-center text-zinc-500">
                <Loader2 size={18} className="animate-spin" />
              </div>
            ) : filteredProjects.length === 0 ? (
              <p className="text-center text-xs text-zinc-400 py-8">
                {search
                  ? "Không tìm thấy dự án phù hợp"
                  : "Bạn chưa có dự án nào"}
              </p>
            ) : (
              <div className="space-y-2">
                {filteredProjects.map((project) => {
                  const isCurrentProject = currentDesignId === project.id;

                  return (
                    <article
                      key={project.id}
                      className={`rounded-xl border px-3 py-2.5 ${
                        isCurrentProject
                          ? "border-[#B59457] bg-[#F7F1E6]"
                          : "border-[#E8E3D8] bg-[#FFFCF7]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[#1F1F1F] truncate">
                            {project.title}
                          </p>
                          <p className="mt-1 text-[11px] text-[#7A7A7A]">
                            {formatProjectUpdatedAt(project.updatedAt)}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(project.id)}
                          className="mt-0.5 rounded-md p-1 text-zinc-500 hover:bg-zinc-100 hover:text-red-600 transition-colors"
                          aria-label={`Xóa dự án ${project.title}`}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          handleOpenProject(project.id, project.title)
                        }
                        className={`mt-2.5 w-full h-8 rounded-md border text-[12px] font-medium transition-colors flex items-center justify-center gap-1.5 ${
                          isCurrentProject
                            ? "border-[#B59457] bg-[#F2E7D1] text-[#5C430D]"
                            : "border-[#D9C9AE] bg-white text-[#5C430D] hover:bg-[#F7F1E6]"
                        }`}
                      >
                        <Circle size={8} fill="currentColor" />
                        {isCurrentProject ? "Đang mở" : "Mở dự án"}
                      </button>
                    </article>
                  );
                })}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label="Đóng bảng"
            className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-full bg-white rounded-r-xl px-2 py-4 shadow-(--shadow-style) hover:bg-zinc-50 active:scale-95 transition-all duration-150 text-zinc-500 hover:text-zinc-800 ${open ? "" : "hidden"}`}
            style={{ border: "var(--border-style)" }}
          >
            <ChevronLeft size={18} />
          </button>
        </div>
      </div>

      <CreateProjectDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onCreateProject={handleCreateProject}
        isCreating={isCreatingProject}
      />
      <DeleteProjectDialog
        projectId={confirmDeleteId}
        onClose={() => setConfirmDeleteId(null)}
        onConfirm={handleDeleteConfirm}
        isDeletingProject={isDeletingProject}
      />
    </>
  );
}
