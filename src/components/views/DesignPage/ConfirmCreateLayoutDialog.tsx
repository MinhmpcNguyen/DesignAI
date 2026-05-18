"use client";

interface ConfirmCreateLayoutDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function ConfirmCreateLayoutDialog({
  open,
  onCancel,
  onConfirm,
}: ConfirmCreateLayoutDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/45 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-[#1F1F1F]">
          Xác nhận tạo mới
        </h3>
        <p className="mt-2 text-sm text-[#4A4A4A]">
          Tạo mặt bằng mới sẽ xóa những đồ vật và mặt bằng hiện có. Bạn có chắc
          chắn muốn tạo mới ko ?
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[#D9D9D9] px-4 py-2 text-sm text-[#333333] hover:bg-[#F8F8F8]"
          >
            Hủy
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-[#9B814A] px-4 py-2 text-sm font-medium text-white hover:opacity-95"
          >
            Tạo mới
          </button>
        </div>
      </div>
    </div>
  );
}
