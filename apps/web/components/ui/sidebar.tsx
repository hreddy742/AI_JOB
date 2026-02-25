"use client";

import { motion } from "framer-motion";
import { Briefcase, ChartColumn, FileText, LayoutGrid, MessageSquare, Settings, UserCircle2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ComponentType } from "react";

import { cn } from "@/lib/utils";

import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import { Button } from "./button";
import { GlassCard } from "./GlassCard";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  unread?: number;
};

const navGroups: Array<{ section: string; items: NavItem[] }> = [
  {
    section: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutGrid },
      { href: "/jobs", label: "Jobs", icon: Briefcase, unread: 6 },
      { href: "/resumes", label: "Resumes", icon: FileText },
      { href: "/applications", label: "Applications", icon: ChartColumn }
    ]
  },
  {
    section: "Support",
    items: [
      { href: "/copilot", label: "Copilot", icon: MessageSquare },
      { href: "/profile", label: "Profile", icon: UserCircle2 },
      { href: "/settings", label: "Settings", icon: Settings }
    ]
  }
];

export function Sidebar({
  collapsed,
  setCollapsed
}: {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}) {
  const pathname = usePathname();

  return (
    <motion.aside
      animate={{ width: collapsed ? 60 : 220 }}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      className="h-screen shrink-0 overflow-y-auto border-r border-[var(--color-border-sub)] bg-[rgba(248,246,242,0.7)] px-4 py-7 backdrop-blur-[24px]"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mb-6 flex items-center gap-2.5">
        <div className="grid h-8 w-8 place-items-center rounded-[9px] bg-[linear-gradient(145deg,var(--color-accent),var(--color-purple))] shadow-[0_4px_12px_rgba(37,99,235,0.25)]" />
        {!collapsed ? <span className="text-[16px] font-medium tracking-[-0.02em]" style={{ fontFamily: "var(--font-display)" }}>APEX APPLY</span> : null}
      </div>

      <div className="space-y-2">
        {navGroups.map((group) => (
          <div key={group.section}>
            {!collapsed ? <p className="label-sm px-3 pb-1.5 pt-3.5">{group.section}</p> : null}
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-[9px] text-left text-[13.5px] transition duration-150",
                      active
                        ? "bg-[var(--color-accent-soft)] font-medium text-[var(--color-accent)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[rgba(0,0,0,0.04)] hover:text-[var(--color-text-primary)]"
                    )}
                  >
                    <Icon className="h-[17px] w-[17px] opacity-85" />
                    {!collapsed ? <span>{item.label}</span> : null}
                    {!collapsed && item.unread ? (
                      <span className="ml-auto inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-semibold text-white">
                        {item.unread}
                      </span>
                    ) : null}
                    {!collapsed && active ? <span className="ml-auto h-[5px] w-[5px] rounded-full bg-[var(--color-accent)] shadow-[0_0_6px_var(--color-accent)]" /> : null}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-auto pt-6">
        <GlassCard padding="sm">
          <div className="flex items-center gap-2">
            <Avatar name="Harsha V" size="md" status="online" />
            {!collapsed ? (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">Harsha V</p>
                <p className="truncate text-[11px] text-[var(--color-text-muted)]">Product Engineer</p>
              </div>
            ) : null}
            {!collapsed ? (
              <Button variant="ghost" size="xs" iconOnly aria-label="Open settings" onClick={() => setCollapsed(false)}>
                <Settings size={13} />
              </Button>
            ) : null}
          </div>
          {!collapsed ? <div className="mt-2"><Badge variant="blue" size="xs" showDot>Pro plan</Badge></div> : null}
        </GlassCard>
      </div>
    </motion.aside>
  );
}
