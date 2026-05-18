import { NewProjectIcon } from "@/components/icons";
import { projectStatus } from "@/constant/project";
import {
  useDeleteDesign,
  useForkDesign,
  useMyDesigns,
} from "@/hooks/useDesign";
import { disposeThumbnailRenderer } from "@/lib/thumbnailRenderer";
import { useAuthUser } from "@/states/slices/auth/hooks";
import { CirclePlus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import CreateProjectDialog from "./CreateProjectDialog";
import DeleteProjectDialog from "./DeleteProjectDialog";

const formatProjectUpdatedAt = (updatedAt: string) => {
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return "Sửa đổi tại: --";
  return `Sửa đổi tại: ${date.toLocaleString("vi-VN")}`;
};

const YourProjectSection = () => {
  const router = useRouter();
  const user = useAuthUser();
  const statusColorMap: Record<string, { bg: string; text: string }> = {
    "Đang chỉnh sửa": { bg: "#9c8251", text: "#ffffff" },
    "Đã duyệt thiết kế": { bg: "#6d5c41", text: "#ffffff" },
    "Đã bàn giao": { bg: "#807668", text: "#ffffff" },
  };
  const defaultStatusColors = { bg: "#F3F2EE", text: "#3B3B3B" };
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const { data: currUserProjectList } = useMyDesigns({
    status: selectedStatus === "all" ? undefined : selectedStatus,
  });
  const { mutateAsync: createProject, isPending: isCreatingProject } =
    useForkDesign();
  const { mutate: deleteProject, isPending: isDeletingProject } =
    useDeleteDesign();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleDeleteConfirm = () => {
    if (!confirmDeleteId) return;
    deleteProject(confirmDeleteId, {
      onSettled: () => setConfirmDeleteId(null),
    });
  };

  const handleCreateProject = async (title: string) => {
    const newProject = await createProject({ title });
    setIsCreateDialogOpen(false);
    disposeThumbnailRenderer();
    router.push(
      `/design?id=${newProject.id}&title=${encodeURIComponent(newProject.title)}`,
    );
  };

  const handleEditProject = (projectId: string, title: string) => {
    disposeThumbnailRenderer();
    router.push(`/design?id=${projectId}&title=${encodeURIComponent(title)}`);
  };

  return (
    <section className="w-full">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-[#1F1F1F]">Dự án của bạn</h2>
        <div className="w-56">
          <Select value={selectedStatus} onValueChange={setSelectedStatus}>
            <SelectTrigger className="w-full h-9 border-[#D9D9D9] text-sm text-[#1F1F1F]">
              <SelectValue placeholder="Lọc theo trạng thái" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {projectStatus.map((status) => (
                <SelectItem key={status.value} value={status.value}>
                  {status.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid auto-rows-fr items-stretch grid-cols-[repeat(auto-fit,minmax(0,288px))] gap-5">
        <button
          type="button"
          className="w-full h-full overflow-hidden rounded-lg border border-[#D9D9D9] bg-white text-left cursor-pointer flex flex-col"
          onClick={() => setIsCreateDialogOpen(true)}
        >
          <div className="flex h-57.5 items-center justify-center bg-[#F5F5F5] relative">
            <NewProjectIcon />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <CirclePlus className="size-11" />
            </div>
          </div>
          <div className="border-t border-[#D9D9D9] px-4 py-3">
            <p className="text-lg leading-snug font-semibold text-[#1F1F1F]">
              Dự án mới
            </p>
            <p className="mt-2 text-sm text-[#707070]">
              Tạo không gian nội thất của riêng bạn
            </p>
          </div>
        </button>

        {(currUserProjectList ?? []).map((project) => {
          const colors = statusColorMap[project.status] ?? defaultStatusColors;

          return (
            <article
              key={project.id}
              className="group w-full h-full overflow-hidden rounded-lg border border-[#D9D9D9] bg-white flex flex-col"
            >
              <div className="relative h-57.5">
                <Image
                  src="/image/login-image.jpg"
                  alt={project.title}
                  fill
                  className="object-cover transition-transform duration-300 group-hover:scale-105"
                />

                <div className="relative">
                  <button
                    type="button"
                    className="absolute top-3 right-3 z-10 rounded-full bg-black/25 p-1 text-white cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                    aria-label="Tùy chọn dự án"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmDeleteId(project.id);
                    }}
                  >
                    <Trash2 className="size-4" color="#d2d2d2" />
                  </button>
                </div>

                <div className="absolute inset-0 flex items-center justify-center bg-black/45 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <button
                    type="button"
                    onClick={() => handleEditProject(project.id, project.title)}
                    className="rounded-full bg-(--primary-color)/50 hover:bg-(--primary-color) transition-colors duration-200 px-10 py-2 text-sm font-semibold text-white flex items-center gap-2 cursor-pointer"
                  >
                    Chỉnh sửa
                  </button>
                </div>
              </div>

              <div className="px-4 py-3">
                <p className="text-lg leading-snug font-semibold text-[#1F1F1F]">
                  {project.title}
                </p>
                <div className="mt-2">
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                    style={{ backgroundColor: colors.bg, color: colors.text }}
                  >
                    {projectStatus.find((s) => s.value === project.status)
                      ?.label ?? project.status}
                  </span>
                </div>
                <p className="mt-2 text-sm text-[#707070]">
                  {formatProjectUpdatedAt(project.updatedAt)}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <div className="size-5 rounded-full bg-[#D6C3A2]" />
                  <span className="text-sm text-[#707070]">
                    {user?.displayName}
                  </span>
                </div>
              </div>
            </article>
          );
        })}
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
    </section>
  );
};

export default YourProjectSection;
