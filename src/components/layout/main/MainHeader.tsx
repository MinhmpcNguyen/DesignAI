"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AppIcon, BellIcon, DropdownIcon } from "@/components/icons";
import { useAuthUser } from "@/states/slices/auth/hooks";
import { useAppSelector } from "@/states/reduxHooks";
import { authSelectors } from "@/states/slices/auth/state";
import { useLogout } from "@/hooks/useAuth";

export default function MainHeader() {
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
    <div className="flex items-center justify-between px-4.5 py-3">
      <AppIcon height={36} width={36} />

      <div ref={containerRef} className="relative flex items-center gap-4">
        <button className="cursor-pointer">
          <BellIcon />
        </button>
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          className="flex items-center gap-1 rounded-[99px] bg-[#ECECEC] cursor-pointer hover:shadow-sm transition-shadow"
          aria-label="User menu"
          aria-expanded={isOpen}
        >
          <div
            className="rounded-full w-10 h-10 flex items-center justify-center shadow-(--shadow-style)"
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
          <div className="absolute right-0 top-full mt-2 w-60 bg-white rounded-xl shadow-lg border border-gray-100 z-50 overflow-hidden">
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
