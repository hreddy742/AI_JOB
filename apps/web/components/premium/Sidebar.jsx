"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { BrainCircuit, BriefcaseBusiness, ChevronLeft, ChevronRight, LayoutDashboard, Radar, Settings, Sparkles } from "lucide-react";

import Button from "@/components/premium/ui/Button";
import { cn } from "@/lib/utils";

const items = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Resume Intelligence", href: "/resumes", icon: Sparkles },
  { label: "Job Discovery", href: "/jobs", icon: BriefcaseBusiness },
  { label: "AI Matching", href: "/matching", icon: Radar },
  { label: "Tailored Resume", href: "/tailored-resume", icon: BrainCircuit },
  { label: "Applications", href: "/applications", icon: BriefcaseBusiness },
  { label: "Insights", href: "/insights", icon: Sparkles },
  { label: "Settings", href: "/settings", icon: Settings }
];

export default function Sidebar({ collapsed, setCollapsed, pathname }) {
  return (
    <motion.aside animate={{ width: collapsed ? 78 : 258 }} transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }} className="rounded-xl border border-border bg-card p-3">
      <div className="mb-4 flex items-center justify-between">
        <AnimatePresence mode="wait">
          {!collapsed ? (
            <motion.div key="logo-full" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="leading-none">
              <p className="font-display text-lg font-semibold">Jobright AI</p>
              <p className="text-xs text-muted">Copilot Workspace</p>
            </motion.div>
          ) : (
            <motion.div key="logo-short" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Sparkles className="h-5 w-5 text-primary" />
            </motion.div>
          )}
        </AnimatePresence>
        <Button variant="ghost" className="p-2" onClick={() => setCollapsed((v) => !v)}>
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>
      <nav className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
                active ? "bg-primary text-primary-foreground shadow-card" : "text-muted hover:bg-slate-200/50 hover:text-fg dark:hover:bg-slate-700/40"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed ? <span>{item.label}</span> : null}
            </Link>
          );
        })}
      </nav>
    </motion.aside>
  );
}
