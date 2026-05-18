"use client";

import { SearchIcon } from "@/components/icons";
import ComingSoon from "@/components/views/ComingSoon";
import { X } from "lucide-react";
import { useState } from "react";

export default function SamplePage() {
  const [searchInput, setSearchInput] = useState("");

  return (
    <div className="flex flex-col items-center gap-5 px-4 sm:px-0">
      <ComingSoon />
      <div className="text-(--primary-text) font-bold flex flex-col items-center text-2xl sm:text-3xl md:text-4xl lg:text-[40px] text-center leading-normal">
        <h1>Tìm không gian bạn thích</h1>
        <h1>Hãy thử chuyển đến nhà của chúng tôi</h1>
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

      <div className="flex flex-1 gap-9 text-[14px] items-center justify-center">
        <p
          className="border px-2.5 py-1.5 rounded-lg"
          style={{ border: "var(--border-style)" }}
        >
          Nhà ở
        </p>
        <p
          className="border px-2.5 py-1.5 rounded-lg"
          style={{ border: "var(--border-style)" }}
        >
          Cho thuê
        </p>
        <p
          className="border px-2.5 py-1.5 rounded-lg"
          style={{ border: "var(--border-style)" }}
        >
          Văn phòng
        </p>
        <p
          className="border px-2.5 py-1.5 rounded-lg"
          style={{ border: "var(--border-style)" }}
        >
          Cửa hàng
        </p>
      </div>
    </div>
  );
}
