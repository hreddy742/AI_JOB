import { type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type GlassCardVariant = "default" | "elevated" | "sunken" | "interactive";
type GlassCardPadding = "sm" | "md" | "lg" | "xl";

const variantClass: Record<GlassCardVariant, string> = {
  default: "bg-[var(--color-surface-1)] border border-[var(--color-border)] shadow-[var(--shadow-glass)] backdrop-blur-[20px] saturate-[1.8]",
  elevated: "bg-[var(--color-surface-2)] border border-[var(--color-border)] shadow-[var(--shadow-glass-lg)] backdrop-blur-[24px] saturate-[1.9]",
  sunken: "bg-[rgba(0,0,0,0.03)] border border-[var(--color-border-sub)] shadow-[inset_0_1px_3px_rgba(0,0,0,0.05)]",
  interactive:
    "bg-[var(--color-surface-1)] border border-[var(--color-border)] shadow-[var(--shadow-glass)] backdrop-blur-[20px] saturate-[1.8] hover:-translate-y-0.5 hover:bg-[var(--color-surface-hover)] hover:shadow-[var(--shadow-glass-lg)]"
};

const paddingClass: Record<GlassCardPadding, string> = {
  sm: "px-[18px] py-4",
  md: "px-6 py-5",
  lg: "px-8 py-7",
  xl: "px-10 py-9"
};

export type GlassCardProps = HTMLAttributes<HTMLDivElement> & {
  variant?: GlassCardVariant;
  padding?: GlassCardPadding;
  hoverable?: boolean;
  children: ReactNode;
};

export function GlassCard({
  variant = "default",
  padding = "md",
  hoverable,
  className,
  children,
  ...props
}: GlassCardProps) {
  const interactive = hoverable && variant !== "sunken" ? "hover:-translate-y-0.5 hover:shadow-[var(--shadow-glass-lg)] hover:bg-[var(--color-surface-hover)]" : "";

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-lg)] transition-[transform,box-shadow,background-color] duration-[220ms] [transition-timing-function:var(--ease-smooth)]",
        variantClass[variant],
        paddingClass[padding],
        interactive,
        className
      )}
      {...props}
    >
      {variant !== "sunken" ? (
        <span
          aria-hidden
          className="pointer-events-none absolute left-3 right-3 top-0 z-[1] h-px bg-[linear-gradient(90deg,transparent_0%,rgba(255,255,255,0.9)_50%,transparent_100%)]"
        />
      ) : null}
      {children}
    </div>
  );
}
