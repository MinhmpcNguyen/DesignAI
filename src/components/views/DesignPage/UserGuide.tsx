"use client";

import { useState } from "react";
import {
  HelpCircle,
  X,
  MousePointer2,
  Keyboard,
  Camera,
  Layers,
  Move,
  Paintbrush,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ShortcutRow {
  keys: string[];
  description: string;
}

interface Section {
  id: string;
  title: string;
  icon: React.ReactNode;
  shortcuts: ShortcutRow[];
}

// ---------------------------------------------------------------------------
// Data — all keyboard shortcuts and operations in one place
// ---------------------------------------------------------------------------
const SECTIONS: Section[] = [
  {
    id: "selection",
    title: "Chọn đối tượng",
    icon: <MousePointer2 className="size-4" />,
    shortcuts: [
      { keys: ["Click"], description: "Chọn một đối tượng" },
      {
        keys: ["Ctrl", "Click"],
        description: "Thêm / bỏ đối tượng khỏi vùng chọn",
      },
      { keys: ["Ctrl", "A"], description: "Chọn tất cả đối tượng" },
      {
        keys: ["Kéo (2D)"],
        description: "Marquee — kéo trên vùng trống để chọn nhiều đối tượng",
      },
      {
        keys: ["Ctrl", "Kéo (2D)"],
        description: "Marquee — thêm vào vùng chọn hiện tại",
      },
      { keys: ["Esc"], description: "Bỏ chọn / huỷ thao tác hiện tại" },
    ],
  },
  {
    id: "objects",
    title: "Thao tác đối tượng",
    icon: <Move className="size-4" />,
    shortcuts: [
      { keys: ["Delete", "Backspace"], description: "Xóa đối tượng đã chọn" },
      { keys: ["Ctrl", "D"], description: "Nhân đôi (Duplicate)" },
      { keys: ["Ctrl", "C"], description: "Sao chép (Copy)" },
      {
        keys: ["Ctrl", "V"],
        description: "Dán (Paste) — click vào scene để đặt vị trí",
      },
      { keys: ["Esc"], description: "Huỷ chế độ dán" },
      { keys: ["Ctrl", "Z"], description: "Hoàn tác (Undo)" },
      {
        keys: ["Ctrl", "Y"],
        description: "Làm lại (Redo) — hoặc Ctrl+Shift+Z",
      },
    ],
  },
  {
    id: "groups",
    title: "Nhóm đối tượng",
    icon: <Layers className="size-4" />,
    shortcuts: [
      {
        keys: ["Ctrl", "G"],
        description: "Nhóm các đối tượng đã chọn (cần ≥ 2 đối tượng)",
      },
      { keys: ["Ctrl", "Shift", "G"], description: "Giải nhóm" },
      {
        keys: ["Click vào thành viên"],
        description:
          "Chọn cả nhóm — di chuyển một thành viên sẽ di chuyển cả nhóm",
      },
    ],
  },
  {
    id: "camera",
    title: "Điều khiển camera",
    icon: <Camera className="size-4" />,
    shortcuts: [
      { keys: ["W", "A", "S", "D"], description: "Di chuyển camera (Pan)" },
      {
        keys: ["↑", "↓", "←", "→"],
        description: "Di chuyển camera (Arrow keys)",
      },
      { keys: ["Q", "E"], description: "Hạ / Nâng độ cao camera" },
      { keys: ["PageUp", "PageDown"], description: "Nâng / Hạ độ cao camera" },
      { keys: ["Chuột phải + kéo"], description: "Xoay góc nhìn (3D)" },
      { keys: ["Scroll"], description: "Zoom in / out" },
      {
        keys: ["Minimap"],
        description:
          "Kéo dot để pan · Kéo handle để xoay · Thanh trượt chiều cao",
      },
    ],
  },
  {
    id: "walls",
    title: "Chỉnh sửa tường",
    icon: <Paintbrush className="size-4" />,
    shortcuts: [
      {
        keys: ["Nút Edit Walls"],
        description: "Bật / tắt chế độ chỉnh sửa tường (toolbar phía trên)",
      },
      { keys: ["Click tường"], description: "Chọn tường" },
      { keys: ["Delete", "Backspace"], description: "Xóa tường đã chọn" },
      {
        keys: ["Kéo endpoint"],
        description: "Kéo đầu tường để thay đổi hướng / chiều dài",
      },
      {
        keys: ["Kéo midpoint"],
        description: "Kéo điểm giữa để di chuyển cả đoạn tường",
      },
      {
        keys: ["Nút Draw Wall"],
        description: "Bật công cụ vẽ tường — click điểm đầu, click điểm cuối",
      },
      {
        keys: ["Esc"],
        description: "Huỷ vẽ tường / bỏ chọn tường",
      },
    ],
  },
  {
    id: "ui",
    title: "Giao diện & chức năng",
    icon: <Keyboard className="size-4" />,
    shortcuts: [
      { keys: ["Nút 2D / 3D"], description: "Chuyển đổi chế độ xem 2D và 3D" },
      { keys: ["Nút Lưu"], description: "Lưu thiết kế lên server" },
      {
        keys: ["Nút AI"],
        description: "Tạo ảnh render AI từ screenshot scene hiện tại",
      },
      {
        keys: ["Sản phẩm (menu trái)"],
        description: "Mở catalog nội thất — kéo đồ vật vào scene",
      },
      {
        keys: ["Mặt bằng (menu trái)"],
        description: "Chọn mẫu căn hộ có sẵn",
      },
      {
        keys: ["Công cụ (menu trái)"],
        description: "Chọn vật liệu sàn (toàn phòng hoặc từng phòng)",
      },
      {
        keys: ["Báo giá"],
        description: "Xem và xuất Excel báo giá nội thất đang có trong scene",
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function KbdChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-md text-[11px] font-medium leading-none bg-zinc-100 border border-zinc-300 text-zinc-700 whitespace-nowrap">
      {label}
    </span>
  );
}

function SectionBlock({ section }: { section: Section }) {
  return (
    <div className="mb-5">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-(--primary-color)">{section.icon}</span>
        <span className="text-[13px] font-semibold text-zinc-800">
          {section.title}
        </span>
      </div>

      {/* Rows */}
      <div className="flex flex-col gap-0.5">
        {section.shortcuts.map((row, idx) => (
          <div
            key={idx}
            className="flex items-start justify-between gap-3 py-1.5 border-b border-zinc-100 last:border-0"
          >
            {/* Keys */}
            <div className="flex flex-wrap items-center gap-1 shrink-0">
              {row.keys.map((key, ki) => (
                <span key={ki} className="flex items-center gap-1">
                  <KbdChip label={key} />
                  {ki < row.keys.length - 1 && (
                    <span className="text-[10px] text-zinc-400">+</span>
                  )}
                </span>
              ))}
            </div>
            {/* Description */}
            <span className="text-[12px] text-zinc-500 text-right leading-snug">
              {row.description}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function UserGuide() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Trigger button — bottom-left, above MenuOptions col */}
      <button
        type="button"
        aria-label="Hướng dẫn sử dụng"
        onClick={() => setOpen((v) => !v)}
        className={`
          w-10 h-10 rounded-[10px] bg-white
          flex flex-col items-center justify-center gap-0.5
          cursor-pointer transition-colors duration-200
          ${open ? "text-(--primary-color)" : "text-zinc-500 hover:text-zinc-800"}
        `}
        style={{
          boxShadow: "4px 0px 8px 0px #00000014",
          border: "1px solid #e3e3e3",
        }}
      >
        <HelpCircle className="size-5" />
      </button>

      {/* Panel */}
      {open && (
        <div
          className="fixed bottom-16 left-2 z-50 w-100 max-h-[70vh] flex flex-col rounded-2xl bg-white overflow-hidden"
          style={{
            boxShadow: "0 8px 32px 0 #0000001a, 4px 0px 8px 0px #00000014",
            border: "1px solid #e3e3e3",
          }}
        >
          {/* Panel header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
            <div className="flex items-center gap-2">
              <HelpCircle className="size-4 text-(--primary-color)" />
              <span className="text-[14px] font-semibold text-zinc-800">
                Hướng dẫn sử dụng
              </span>
            </div>
            <button
              type="button"
              aria-label="Đóng hướng dẫn"
              onClick={() => setOpen(false)}
              className="rounded-lg p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* Scrollable content */}
          <div className="overflow-y-auto px-4 py-4 flex-1 min-h-0">
            {SECTIONS.map((section) => (
              <SectionBlock key={section.id} section={section} />
            ))}

            {/* Footer note */}
            <p className="text-[11px] text-zinc-400 text-center mt-2 pb-1">
              Mẹo: Ở chế độ 2D, kéo chuột trái trên vùng trống để chọn nhiều đối
              tượng cùng lúc.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
