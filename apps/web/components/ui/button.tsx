"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Spinner } from "./Spinner";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "link";
type ButtonSize = "xs" | "sm" | "md" | "lg" | "xl";

type ButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  iconOnly?: boolean;
  leftIcon?: ReactNode;
};

const sizeClass: Record<ButtonSize, string> = {
  xs: "min-h-[30px] px-3 py-[5px] text-[12px] rounded-[7px]",
  sm: "min-h-[34px] px-[14px] py-[7px] text-[13px] rounded-[8px]",
  md: "min-h-[38px] px-[18px] py-[9px] text-[13.5px] rounded-[10px]",
  lg: "min-h-[44px] px-6 py-3 text-[15px] rounded-[11px]",
  xl: "min-h-[50px] px-8 py-[14px] text-[16px] rounded-[12px]"
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--color-accent)] text-white border border-transparent hover:bg-[var(--color-accent-hover)] hover:shadow-[var(--shadow-accent)] active:bg-[var(--color-accent-active)]",
  secondary:
    "bg-[var(--color-accent-soft)] text-[var(--color-accent)] border border-[rgba(37,99,235,0.15)] hover:bg-[rgba(37,99,235,0.16)] hover:shadow-[0_4px_12px_rgba(37,99,235,0.2)] active:bg-[rgba(37,99,235,0.22)]",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] border border-[var(--color-border-sub)] hover:bg-[rgba(0,0,0,0.04)] hover:border-[rgba(0,0,0,0.12)] hover:text-[var(--color-text-primary)]",
  danger:
    "bg-[var(--color-error-soft)] text-[var(--color-error)] border border-[rgba(220,38,38,0.15)] hover:bg-[rgba(220,38,38,0.18)] hover:shadow-[0_4px_12px_rgba(220,38,38,0.2)] active:bg-[rgba(220,38,38,0.24)]",
  link: "bg-transparent border border-transparent px-0 py-0 min-h-0 text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading,
  disabled,
  className,
  iconOnly,
  leftIcon,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <motion.button
      whileHover={variant === "link" || isDisabled ? undefined : { y: -1 }}
      whileTap={variant === "link" || isDisabled ? undefined : { y: 0, scale: 0.98 }}
      transition={{ duration: 0.15, ease: [0, 0, 0.2, 1] }}
      className={cn(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium tracking-[0.005em] transition-[transform,box-shadow,background-color,color,border-color] duration-150 [transition-timing-function:var(--ease-smooth)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)] disabled:pointer-events-none",
        sizeClass[size],
        variantClass[variant],
        iconOnly ? "aspect-square min-w-8 p-2" : "",
        isDisabled ? "opacity-70" : "",
        className
      )}
      disabled={isDisabled}
      {...props}
    >
      {iconOnly ? (
        <span className="inline-flex items-center justify-center">{loading ? <Spinner /> : children}</span>
      ) : (
        <>
          <span className="inline-flex w-[14px] justify-center">{loading ? <Spinner /> : leftIcon ? leftIcon : null}</span>
          <span>{children}</span>
        </>
      )}
    </motion.button>
  );
}
