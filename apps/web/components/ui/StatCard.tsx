"use client";

import { type LucideIcon, TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "./Badge";
import { GlassCard } from "./GlassCard";

export function StatCard({
  label,
  value,
  Icon,
  delta,
  positive = true,
  iconTone = "var(--color-accent-soft)",
  iconColor = "var(--color-accent)",
  children
}: {
  label: string;
  value: string;
  Icon: LucideIcon;
  delta?: string;
  positive?: boolean;
  iconTone?: string;
  iconColor?: string;
  children?: React.ReactNode;
}) {
  return (
    <GlassCard variant="interactive" padding="md">
      <div className="flex items-start justify-between">
        <span className="grid h-9 w-9 place-items-center rounded-[var(--radius-md)]" style={{ background: iconTone, color: iconColor }}>
          <Icon size={16} />
        </span>
        {delta ? (
          <Badge variant={positive ? "green" : "red"} size="xs">
            {positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />} {delta}
          </Badge>
        ) : null}
      </div>
      <p className="number-lg mt-4">{value}</p>
      <p className="body-xs mt-1">{label}</p>
      {children ? <div className="mt-3">{children}</div> : null}
    </GlassCard>
  );
}
