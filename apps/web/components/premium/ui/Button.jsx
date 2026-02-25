"use client";

import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

const variants = {
  primary: "bg-primary text-primary-foreground hover:brightness-105 shadow-card",
  secondary: "border border-border bg-card text-fg hover:bg-slate-100 dark:hover:bg-slate-800",
  ghost: "bg-transparent text-muted hover:text-fg hover:bg-slate-200/40 dark:hover:bg-slate-700/40"
};

export default function Button({ variant = "primary", className, children, ...props }) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.15, ease: [0.22, 1, 0.36, 1] }}
      className={cn("inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition", variants[variant], className)}
      {...props}
    >
      {children}
    </motion.button>
  );
}
