"use client";

import { motion } from "framer-motion";

export function AIThinking({ label = "AI is reasoning over your profile..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <div className="relative h-3 w-10">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="absolute h-2 w-2 rounded-full bg-primary"
            style={{ left: `${i * 12}px` }}
            animate={{ y: [0, -5, 0], opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 1.2, delay: i * 0.16 }}
          />
        ))}
      </div>
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}

export function AISkeleton() {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-card p-4">
      <div className="h-4 w-1/3 animate-pulse rounded bg-slate-300/60 dark:bg-slate-600/70" />
      <div className="h-3 w-full animate-pulse rounded bg-slate-300/60 dark:bg-slate-600/70" />
      <div className="h-3 w-5/6 animate-pulse rounded bg-slate-300/60 dark:bg-slate-600/70" />
      <div className="h-3 w-4/6 animate-pulse rounded bg-slate-300/60 dark:bg-slate-600/70" />
    </div>
  );
}
