import { cn } from "@/lib/utils";

export function Divider({ label, className }: { label?: string; className?: string }) {
  if (!label) {
    return <div role="separator" className={cn("h-px w-full bg-[var(--color-border-sub)]", className)} />;
  }

  return (
    <div className={cn("flex items-center gap-3", className)} role="separator" aria-label={label}>
      <span className="h-px flex-1 bg-[linear-gradient(90deg,transparent,var(--color-border-sub),transparent)]" />
      <span className="label-sm">{label}</span>
      <span className="h-px flex-1 bg-[linear-gradient(90deg,transparent,var(--color-border-sub),transparent)]" />
    </div>
  );
}
