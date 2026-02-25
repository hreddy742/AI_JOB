"use client";

type ScoreCardProps = {
  overall?: number | null;
  impact?: number | null;
  ats?: number | null;
  clarity?: number | null;
  completeness?: number | null;
  format?: number | null;
};

function cell(label: string, value?: number | null) {
  return (
    <div className="rounded border border-slate-700 bg-slate-950 p-2">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-slate-100">{value == null ? "N/A" : value.toFixed(1)}</p>
    </div>
  );
}

export function ResumeScoreCard({ overall, impact, ats, clarity, completeness, format }: ScoreCardProps) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 p-3">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Resume Scores</h3>
      <div className="grid gap-2 sm:grid-cols-3">
        {cell("Overall", overall)}
        {cell("Impact", impact)}
        {cell("ATS", ats)}
        {cell("Clarity", clarity)}
        {cell("Completeness", completeness)}
        {cell("Format", format)}
      </div>
    </section>
  );
}
