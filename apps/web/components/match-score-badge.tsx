"use client";

import { ReactNode } from "react";

export function MatchScoreBadge({ score }: { score: number }) {
  const c = score >= 70 ? "from-emerald-500 to-lime-400" : score >= 40 ? "from-amber-500 to-orange-400" : "from-rose-500 to-red-400";
  return (
    <div className={`inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br ${c} text-xs font-bold text-white`}>
      {Math.round(score)}
    </div>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border p-4">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}
