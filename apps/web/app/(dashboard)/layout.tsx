"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { ToastProvider } from "@/components/ui/toast";
import { useAuthStore } from "@/lib/store/auth-store";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const hydrateFromCookie = useAuthStore((s) => s.hydrateFromCookie);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    hydrateFromCookie();
  }, [hydrateFromCookie]);

  async function onLogout(): Promise<void> {
    await logout();
    router.push("/auth/login");
  }

  return (
    <ToastProvider>
      <AppShell>
        <div className="mb-6 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onLogout}>
            Logout
          </Button>
        </div>
        {children}
      </AppShell>
    </ToastProvider>
  );
}
