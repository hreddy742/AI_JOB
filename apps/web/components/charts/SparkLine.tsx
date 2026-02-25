"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";

export function SparkLine({ data, color = "var(--color-accent)" }: { data: Array<{ value: number }>; color?: string }) {
  return (
    <div className="h-[60px] w-full opacity-60">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.26} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5} fill="url(#spark-fill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
