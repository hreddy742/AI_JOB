"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "blue" | "green" | "amber" | "red" | "purple";
type BadgeSize = "xs" | "sm" | "md";

const variantMap: Record<BadgeVariant, string> = {
  default: "bg-[rgba(0,0,0,0.05)] text-[var(--color-text-secondary)]",
  blue: "bg-[var(--color-accent-soft)] text-[var(--color-accent)]",
  green: "bg-[var(--color-success-soft)] text-[var(--color-success)]",
  amber: "bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
  red: "bg-[var(--color-error-soft)] text-[var(--color-error)]",
  purple: "bg-[var(--color-purple-soft)] text-[var(--color-purple)]"
};

const sizeMap: Record<BadgeSize, string> = {
  xs: "px-[7px] py-[2px] text-[10px]",
  sm: "px-[9px] py-[3px] text-[11px]",
  md: "px-[11px] py-1 text-[12px]"
};

export function Badge({
  children,
  className,
  variant = "default",
  size = "sm",
  showDot,
  dismissible,
  onDismiss
}: {
  children: React.ReactNode;
  className?: string;
  variant?: BadgeVariant;
  size?: BadgeSize;
  showDot?: boolean;
  dismissible?: boolean;
  onDismiss?: () => void;
}) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  const dotClass = {
    default: "bg-[var(--color-text-secondary)]",
    blue: "bg-[var(--color-accent)]",
    green: "bg-[var(--color-success)]",
    amber: "bg-[var(--color-warning)]",
    red: "bg-[var(--color-error)]",
    purple: "bg-[var(--color-purple)]"
  }[variant];

  return (
    <AnimatePresence initial={false}>
      <motion.span
        layout
        initial={{ opacity: 0, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.92, width: 0, paddingInline: 0 }}
        className={cn(
          "inline-flex items-center gap-1 rounded-full font-medium tracking-[0.02em]",
          variantMap[variant],
          sizeMap[size],
          className
        )}
      >
        {showDot ? <span className={cn("h-[5px] w-[5px] rounded-full", dotClass)} aria-hidden /> : null}
        <span>{children}</span>
        {dismissible ? (
          <button
            type="button"
            aria-label="Dismiss badge"
            onClick={() => {
              setVisible(false);
              onDismiss?.();
            }}
            className="ml-1 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full hover:bg-[rgba(0,0,0,0.08)]"
          >
            <X size={10} />
          </button>
        ) : null}
      </motion.span>
    </AnimatePresence>
  );
}
