"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useAccessToken, useIsHydrated } from "@/states/slices/auth/hooks";

const subscribe = () => () => {};

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isHydrated = useIsHydrated();
  const accessToken = useAccessToken();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );

  useEffect(() => {
    if (isHydrated && !accessToken) {
      router.push("/login");
    }
  }, [isHydrated, accessToken, router]);

  if (!mounted || !isHydrated) {
    return null;
  }

  if (!accessToken) {
    return null;
  }

  return <>{children}</>;
}
