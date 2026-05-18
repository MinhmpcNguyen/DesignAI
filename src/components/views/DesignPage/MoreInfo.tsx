"use client";

import { useEffect, useRef, useState } from "react";
import { DropdownIcon, SaveIcon, ShareIcon } from "../../icons";
import VerticalDivide from "../../VerticalDivide";
import { useAuthUser } from "@/states/slices/auth/hooks";
import { useRouter } from "next/navigation";
import { useLogout } from "@/hooks/useAuth";
import { useAppSelector } from "@/states/reduxHooks";
import { authSelectors } from "@/states/slices/auth/state";
import { Loader2 } from "lucide-react";

interface MoreInfoProps {
  onSave?: () => void;
  isSaving?: boolean;
  designTitle?: string;
}

export default function MoreInfo({
  onSave,
  isSaving,
  designTitle,
}: MoreInfoProps) {
  const [isOpen, setIsOpen] = useState(false);

  const router = useRouter();
  const user = useAuthUser();
  const refreshToken = useAppSelector(authSelectors.selectRefreshToken);
  const logout = useLogout();

  const containerRef = useRef<HTMLDivElement>(null);

  const initial = user?.displayName?.charAt(0).toUpperCase() ?? "?";

  const handleLogout = () => {
    logout.mutate(
      { refreshToken: refreshToken ?? "" },
      {
        onSuccess: () => router.push("/login"),
        onError: () => router.push("/login"),
      },
    );
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div
      className="flex items-center bg-white gap-0.5 px-2 py-2 rounded-[99px] shadow-(--shadow-style) min-w-0"
      style={{ border: "var(--border-style)" }}
    >
      <div className="group relative max-w-40">
        <span className="block truncate text-sm font-medium">
          {designTitle ?? "—"}
        </span>
        <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 hidden w-max max-w-70 -translate-x-1/2 rounded-md bg-black px-2 py-1 text-xs text-white shadow-md group-hover:block">
          {designTitle ?? "—"}
        </div>
      </div>
      <VerticalDivide />

      <button onClick={onSave} disabled={isSaving} className="cursor-pointer">
        {isSaving ? (
          <Loader2 className="size-4 animate-spin" color="#9c8251" />
        ) : (
          <SaveIcon />
        )}
      </button>
      <VerticalDivide />
      <button
        type="button"
        aria-label="Share"
        title="Chia sẻ"
        className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none"
      >
        <ShareIcon />
      </button>
      <VerticalDivide />
      <div ref={containerRef} className="relative">
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          className="flex items-center gap-1 rounded-[99px] bg-[#ECECEC] cursor-pointer hover:shadow-sm transition-shadow"
          aria-label="User menu"
          aria-expanded={isOpen}
        >
          <div
            className="rounded-full w-8 h-8 flex items-center justify-center shadow-(--shadow-style)"
            style={{ border: "var(--border-style)" }}
          >
            <span className="text-sm font-medium text-black">{initial}</span>
          </div>
          <div
            className="p-1.5 transition-transform duration-200"
            style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
          >
            <DropdownIcon />
          </div>
        </button>

        {isOpen && (
          <div className="absolute right-0 mt-2 w-60 bg-white rounded-xl shadow-lg border border-gray-100 z-50 overflow-hidden">
            {/* User info */}
            <div className="flex items-center gap-3 px-4 py-3">
              <div
                className="rounded-full w-10 h-10 shrink-0 flex items-center justify-center shadow-(--shadow-style)"
                style={{ border: "var(--border-style)" }}
              >
                <span className="text-sm font-medium text-black">
                  {initial}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">
                  {user?.displayName ?? "—"}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {user?.email ?? "—"}
                </p>
              </div>
            </div>

            <div className="border-t border-gray-100" />

            {/* Logout */}
            <button
              onClick={handleLogout}
              disabled={logout.isPending}
              className="w-full text-left px-4 py-3 text-sm text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {logout.isPending ? "Logging out…" : "Log out"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
