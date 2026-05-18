"use client";

import { Hammer } from "lucide-react";
import { useRouter } from "next/navigation";

type ComingSoonProps = {
  description?: string;
  onBack?: () => void;
  backLabel?: string;
};

export default function ComingSoon({
  description,
  onBack,
  backLabel = "Quay lại",
}: ComingSoonProps) {
  const router = useRouter();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-2xl sm:max-w-md">
        {/* Icon */}
        <div className="mb-6 flex justify-center">
          <div className="flex size-20 items-center justify-center rounded-full bg-(--option-highlight-color)">
            <Hammer
              className="size-9 text-(--primary-color)"
              strokeWidth={1.5}
            />
          </div>
        </div>

        {/* Heading */}
        <div className="mb-3 text-center">
          <h2 className="text-2xl font-semibold text-[#1e1b16]">Sắp ra mắt</h2>
        </div>

        {/* Description */}
        <p className="mb-8 text-center text-sm leading-relaxed text-(--sub-color)">
          {description ??
            "Tính năng này hiện đang trong quá trình phát triển và sẽ được triển khai trong thời gian tới. Vui lòng quay lại sau."}
        </p>

        {/* Progress dots */}
        <div className="mb-8 flex justify-center gap-2">
          <span className="size-2 rounded-full bg-(--highlight-tab-color)" />
          <span className="size-2 rounded-full bg-(--primary-border-color)" />
          <span className="size-2 rounded-full bg-(--primary-border-color)" />
        </div>

        {/* Back button */}
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="w-full rounded-lg bg-(--primary-color) py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 active:opacity-80"
          >
            {backLabel}
          </button>
        )}

        {/* Navigate to project page */}
        <button
          type="button"
          onClick={() => router.push("/project")}
          className="mt-3 w-full rounded-lg border border-(--primary-color) py-2.5 text-sm font-medium text-(--primary-color) transition-colors hover:bg-(--primary-color) hover:text-white active:bg-(--option-active-color)"
        >
          Đi đến trang dự án
        </button>
      </div>
    </div>
  );
}
