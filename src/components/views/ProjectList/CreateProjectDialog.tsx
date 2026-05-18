import { X } from "lucide-react";
import { useRef, useState } from "react";

type CreateProjectDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateProject: (title: string) => Promise<void>;
  isCreating?: boolean;
};

const CreateProjectDialog = ({
  open,
  onOpenChange,
  onCreateProject,
  isCreating = false,
}: CreateProjectDialogProps) => {
  const [title, setTitle] = useState("");
  const isSubmittingRef = useRef(false);

  if (!open) return null;

  const handleClose = () => {
    setTitle("");
    onOpenChange(false);
  };

  const handleSubmit = async () => {
    const trimmed = title.trim();
    if (!trimmed || isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    try {
      await onCreateProject(trimmed);
    } finally {
      isSubmittingRef.current = false;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-[#1F1F1F]">
            Tạo dự án mới
          </h3>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-md p-1 text-[#707070] hover:bg-[#F5F5F5]"
            aria-label="Đóng"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label
              htmlFor="project-title"
              className="mb-2 block text-sm font-medium text-[#1F1F1F]"
            >
              Tên dự án
            </label>
            <input
              id="project-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleSubmit();
              }}
              placeholder="<Tên> - <Chung cư>"
              className="h-10 w-full rounded-md border border-[#D9D9D9] px-3 text-sm outline-none focus:border-[#9B814A]"
              disabled={isCreating}
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-md border border-[#D9D9D9] px-4 py-2 text-sm text-[#333333] hover:bg-[#F8F8F8]"
              disabled={isCreating}
            >
              Hủy
            </button>
            <button
              type="button"
              onClick={() => void handleSubmit()}
              className="rounded-md bg-[#9B814A] px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isCreating || !title.trim()}
            >
              {isCreating ? "Đang tạo..." : "Tạo dự án"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreateProjectDialog;
