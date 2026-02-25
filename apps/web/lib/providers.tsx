"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useAuthStore } from "@/lib/auth-store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const initFromCookie = useAuthStore((s) => s.initFromCookie);

  useEffect(() => {
    void initFromCookie();
  }, [initFromCookie]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
