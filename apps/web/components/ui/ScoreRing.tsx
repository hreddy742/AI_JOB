"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

type RingSize = "sm" | "md" | "lg" | "xl";

const sizeMap: Record<RingSize, number> = {
  sm: 48,
  md: 64,
  lg: 80,
  xl: 96
};

function colorFromScore(score: number): string {
  if (score >= 90) return "var(--color-success)";
  if (score >= 75) return "var(--color-accent)";
  if (score >= 50) return "var(--color-warning)";
  return "var(--color-error)";
}

export function ScoreRing({
  score,
  size = "md",
  label,
  color
}: {
  score: number;
  size?: RingSize;
  label?: string;
  color?: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const safeScore = Math.max(0, Math.min(100, score));
  const px = sizeMap[size];
  const strokeWidth = Math.max(3, px / 14);
  const radius = (px - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    io.observe(node);
    return () => io.disconnect();
  }, []);

  const ringColor = color ?? colorFromScore(safeScore);
  const dash = useMemo(() => `${(visible ? safeScore : 0) / 100 * circumference} ${circumference}`, [visible, safeScore, circumference]);

  return (
    <div ref={rootRef} className="inline-flex flex-col items-center gap-1" aria-label={`Resume score: ${safeScore} out of 100`}>
      <div className="relative inline-grid place-items-center" style={{ width: px, height: px }}>
        <svg width={px} height={px} viewBox={`0 0 ${px} ${px}`} role="img" aria-hidden>
          <circle
            cx={px / 2}
            cy={px / 2}
            r={radius}
            fill="none"
            stroke="rgba(0,0,0,0.06)"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={px / 2}
            cy={px / 2}
            r={radius}
            fill="none"
            stroke={ringColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={dash}
            transform={`rotate(-90 ${px / 2} ${px / 2})`}
            style={{
              transition: "stroke-dasharray 1.2s var(--ease-out)",
              filter: `drop-shadow(0 0 6px color-mix(in srgb, ${ringColor} 60%, transparent))`
            }}
          />
        </svg>
        <span className={cn("absolute text-center text-[var(--color-text-primary)]", "font-[var(--font-display)]")}
          style={{ fontSize: `${Math.round(px / 3.2)}px`, lineHeight: 1 }}>
          {safeScore}
        </span>
      </div>
      {label ? <span className="text-[11px] text-[var(--color-text-muted)]">{label}</span> : null}
    </div>
  );
}
