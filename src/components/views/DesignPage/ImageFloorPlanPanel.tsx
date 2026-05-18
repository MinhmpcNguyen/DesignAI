"use client";

import { useRef, useState } from "react";
import { ImageIcon, Loader2, Upload, X } from "lucide-react";
import { extractWalls } from "@/services/api/apiUrl";
import { useReplaceAllObjects } from "@/states/slices/objects/hooks";
import { useSetWalls } from "@/states/slices/walls/hooks";
import { useSetViewMode } from "@/states/slices/view/hooks";
import type { Wall } from "@/states/slices/walls/types";
import type { ExtractedWall } from "@/types/api";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function mapExtractedWalls(extracted: ExtractedWall[]): Wall[] {
  return extracted.map((w, i) => ({
    id: `wall-img-${Date.now()}-${i}`,
    startPoint: w.startPoint,
    endPoint: w.endPoint,
    thickness: w.thickness > 0 ? w.thickness : 0.2,
    height: w.height > 0 ? w.height : 3,
    color: w.color || "#e0e0e0",
  }));
}

export default function ImageFloorPlanPanel({ open, onOpenChange }: Props) {
  const setWalls = useSetWalls();
  const replaceAllObjects = useReplaceAllObjects();
  const setViewMode = useSetViewMode();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    if (isLoading) return;
    setFile(null);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setError(null);
    onOpenChange(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setError(null);
    const url = URL.createObjectURL(selected);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
    // Reset input so the same file can be re-selected
    e.target.value = "";
  };

  const handleGenerate = async () => {
    if (!file || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await extractWalls(file);
      const walls = mapExtractedWalls(res.data.walls);
      replaceAllObjects([]);
      setWalls(walls);
      setViewMode("2D");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Đã xảy ra lỗi, vui lòng thử lại",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className={`absolute top-14 left-22 h-[calc(100%-3.5rem)] z-55 transition-transform duration-300 ease-in-out ${
        open ? "translate-x-0" : "-translate-x-102"
      }`}
    >
      <div
        className="w-80 h-full bg-white shadow-(--shadow-style) rounded-2xl flex flex-col overflow-hidden"
        style={{ border: "var(--border-style)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
          <span className="font-medium text-sm text-(--secondary-color)">
            Tải ảnh mặt bằng
          </span>
          <button
            type="button"
            onClick={handleClose}
            disabled={isLoading}
            className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors disabled:opacity-50"
            aria-label="Đóng bảng"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 flex flex-col px-4 py-4 gap-4 overflow-y-auto">
          <p className="text-xs text-zinc-400 leading-relaxed">
            Tải lên ảnh mặt bằng của bạn. Hệ thống sẽ tự động nhận diện các bức
            tường và tạo mặt bằng.
          </p>

          {/* Image frame — clickable to open file picker */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="w-full aspect-4/3 rounded-xl border-2 border-dashed border-zinc-200 hover:border-(--primary-color,#C8A882) bg-[#fafafa] flex items-center justify-center overflow-hidden transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewUrl}
                alt="Ảnh mặt bằng"
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-zinc-400">
                <ImageIcon size={32} strokeWidth={1.2} />
                <span className="text-xs">Nhấn để chọn ảnh</span>
              </div>
            )}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />

          {/* Buttons */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-1.5 h-9 rounded-lg border border-zinc-200 text-xs font-medium text-zinc-600 hover:bg-zinc-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Upload size={13} />
              Tải ảnh lên
            </button>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={!file || isLoading}
              className="flex-1 flex items-center justify-center gap-1.5 h-9 rounded-lg bg-(--primary-color,#C8A882) text-white text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 size={13} className="animate-spin" />
              ) : null}
              Tạo mặt bằng
            </button>
          </div>

          {/* Error message */}
          {error && (
            <p className="text-xs text-red-500 leading-relaxed">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
