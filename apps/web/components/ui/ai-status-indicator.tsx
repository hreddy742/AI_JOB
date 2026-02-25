"use client";

import { motion } from "framer-motion";

export function AIStatusIndicator({ status = "Online" }: { status?: "Online" | "Processing" | "Offline" }) {
  const color = status === "Online" ? "bg-emerald-500" : status === "Processing" ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs">
      <span className="relative inline-flex h-2.5 w-2.5">
        <span className={`absolute inline-flex h-full w-full rounded-full opacity-70 ${color} animate-pulseWave`} />
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
      </span>
      AI {status}
    </div>
  );
}
