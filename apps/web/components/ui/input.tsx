import {
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes
} from "react";

import { cn } from "@/lib/utils";

type FieldWrapperProps = {
  label?: string;
  error?: string;
  children: ReactNode;
};

const baseControlClass =
  "w-full rounded-[var(--radius-md)] border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.65)] px-3.5 py-2.5 text-[14px] text-[var(--color-text-primary)] outline-none backdrop-blur-[12px] transition-[border-color,box-shadow,background-color] duration-[220ms] [transition-timing-function:var(--ease-smooth)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:bg-[rgba(255,255,255,0.85)] focus:shadow-[0_0_0_3px_rgba(37,99,235,0.08)]";

export function FormField({ label, error, children }: FieldWrapperProps) {
  return (
    <label className="block">
      {label ? <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-[var(--color-text-muted)]">{label}</span> : null}
      {children}
      {error ? (
        <span className="mt-[5px] block animate-[fadeUp_0.2s_var(--ease-smooth)] text-[12px] text-[var(--color-error)]">{error}</span>
      ) : null}
    </label>
  );
}

type FieldIconProps = {
  leftIcon?: ReactNode;
  rightAction?: ReactNode;
  error?: boolean;
};

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(baseControlClass, className)} />;
}

export function InputWithIcon({
  leftIcon,
  rightAction,
  className,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & FieldIconProps) {
  return (
    <div className="relative">
      {leftIcon ? <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">{leftIcon}</span> : null}
      <input
        {...props}
        className={cn(baseControlClass, leftIcon ? "pl-9" : "", rightAction ? "pr-9" : "", error ? "border-[var(--color-error)] bg-[rgba(254,242,242,0.6)] shadow-[0_0_0_3px_rgba(220,38,38,0.06)]" : "", className)}
      />
      {rightAction ? <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">{rightAction}</span> : null}
    </div>
  );
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(baseControlClass, className)} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(baseControlClass, "min-h-[100px] resize-y leading-[1.6]", className)} />;
}
