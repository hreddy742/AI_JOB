import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Grid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid gap-[14px]", className)}>{children}</div>;
}
