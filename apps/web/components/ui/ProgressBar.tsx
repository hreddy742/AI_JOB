"use client";

import { useEffect, useMemo, useRef, useState } from "react";

function colorFromValue(value: number): string {
  if (value >= 90) return "var(--color-success)";
  if (value >= 75) return "var(--color-accent)";
  if (value >= 50) return "var(--color-warning)";
  return "var(--color-error)";
}

export function ProgressBar({
  value,
  label,
  variant = "default"
}: {
  value: number;
  label: string;
  variant?: "default" | "semantic";
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const safe = Math.max(0, Math.min(100, value));

  useEffect(() => {
    const node = ref.current;
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

  const color = useMemo(() => (variant === "semantic" ? colorFromValue(safe) : "var(--color-accent)"), [safe, variant]);

  return (
    <div ref={ref} className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="body-sm">{label}</span>
        <span className="mono-sm">{safe}%</span>
      </div>
      <div className="h-[5px] w-full overflow-hidden rounded-full bg-[rgba(0,0,0,0.06)]">
        <div
          className="h-[5px] rounded-full"
          style={{
            width: `${visible ? safe : 0}%`,
            background: color,
            boxShadow: `0 0 8px ${color}50`,
            transition: "width 1.2s var(--ease-out)"
          }}
        />
      </div>
    </div>
  );
}
