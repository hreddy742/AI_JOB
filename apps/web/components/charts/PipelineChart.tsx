"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";

export function PipelineChart({ data }: { data: Array<{ stage: string; count: number }> }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="stage" tickLine={false} axisLine={false} tick={{ fill: "#6B6760", fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: "#A8A5A0", fontSize: 11 }} />
          <Bar dataKey="count" radius={[8, 8, 0, 0]} fill="var(--color-accent)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
