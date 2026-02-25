import { cn } from "@/lib/utils";

export default function Card({ className, ...props }) {
  return <div className={cn("rounded-lg border border-border bg-card p-4 shadow-card", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn("font-display text-base font-semibold", className)} {...props} />;
}

export function CardDescription({ className, ...props }) {
  return <p className={cn("text-sm text-muted", className)} {...props} />;
}
