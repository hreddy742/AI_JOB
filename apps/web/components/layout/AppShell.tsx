"use client";

import { type ReactNode, useState } from "react";

import { Sidebar } from "@/components/ui/sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="apex-app-shell">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <main className="apex-main">{children}</main>
    </div>
  );
}
