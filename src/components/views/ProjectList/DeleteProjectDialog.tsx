import { Loader2 } from "lucide-react";

interface DeleteProjectDialogProps {
  projectId: string | null;
  onClose: () => void;
  onConfirm: () => void;
  isDeletingProject: boolean;
}

export default function DeleteProjectDialog({
  projectId,
  onClose,
  onConfirm,
  isDeletingProject,
}: DeleteProjectDialogProps) {
  if (!projectId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm p-5 rounded-xl bg-white"
        onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: "var(--shadow-style)" }}
      >
        <h3 className="text-base font-semibold text-(--text-color) flex items-center gap-2">
          Xóa dự án?
        </h3>
        <p className="mt-2 text-sm text-[#707070]">
          Hành động này không thể hoàn tác. Dự án sẽ bị xóa vĩnh viễn.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            className="rounded-lg border border-[#D9D9D9] px-4 py-2 text-sm font-medium text-[#1F1F1F] hover:bg-[#F5F5F5] cursor-pointer"
            onClick={onClose}
            disabled={isDeletingProject}
          >
            Hủy
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg bg-[#dc2626] px-4 py-2 text-sm font-medium text-white hover:bg-[#b91c1c] cursor-pointer disabled:opacity-60"
            onClick={onConfirm}
            disabled={isDeletingProject}
          >
            {isDeletingProject && <Loader2 className="size-4 animate-spin" />}
            Xóa
          </button>
        </div>
      </div>
    </div>
  );
}
