import { type ReactNode } from "react";

import { Button } from "./button";

export function EmptyState({
  title,
  subtitle,
  ctaLabel,
  onCta,
  illustration
}: {
  title: string;
  subtitle: string;
  ctaLabel: string;
  onCta: () => void;
  illustration?: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-[280px] max-w-[320px] flex-col items-center justify-center text-center">
      <div className="animate-[float_4s_ease-in-out_infinite] text-[48px] opacity-60" aria-hidden>
        {illustration ?? "??"}
      </div>
      <h3 className="display-sm mt-4">{title}</h3>
      <p className="body-sm mt-1.5">{subtitle}</p>
      <Button className="mt-5" onClick={onCta}>{ctaLabel}</Button>
    </div>
  );
}
