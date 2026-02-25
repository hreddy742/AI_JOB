import { cn } from "@/lib/utils";

const toneMap = {
  default: "border-border bg-slate-200/50 text-slate-800 dark:bg-slate-700/40 dark:text-slate-100",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  danger: "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400",
  info: "border-cyan-500/30 bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
};

export default function Badge({ tone = "default", className, children }) {
  return <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium", toneMap[tone], className)}>{children}</span>;
}
