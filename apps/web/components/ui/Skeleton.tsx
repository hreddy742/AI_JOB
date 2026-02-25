import { cn } from "@/lib/utils";

type SkeletonVariant = "text-line" | "card" | "avatar" | "chart";

const variantClass: Record<SkeletonVariant, string> = {
  "text-line": "h-3 w-full rounded-md",
  card: "h-24 w-full rounded-[var(--radius-lg)]",
  avatar: "h-10 w-10 rounded-full",
  chart: "h-28 w-full rounded-[var(--radius-md)]"
};

export function Skeleton({ variant = "text-line", className }: { variant?: SkeletonVariant; className?: string }) {
  return <div className={cn("apex-skeleton", variantClass[variant], className)} aria-hidden />;
}
