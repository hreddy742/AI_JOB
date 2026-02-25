"use client";

import { MatchScoreBadge } from "./match-score-badge";

type Job = {
  id: string;
  title: string;
  company: string;
  source: string;
  url?: string;
  location_city?: string;
  remote?: boolean;
  sponsorship_score?: number;
  salary_min?: number;
  salary_max?: number;
  tags?: string[];
};

type JobCardProps = {
  job: Job;
  onSave: () => void;
  onTailor: () => void;
  onReferrals: () => void;
  onApply: () => void;
};

export function JobCard({ job, onSave, onTailor, onReferrals, onApply }: JobCardProps) {
  const sponsorScore = job.sponsorship_score ?? 0.5;
  const sponsor = sponsorScore >= 0.65 ? "Likely" : sponsorScore < 0.35 ? "Unlikely" : "Unknown";
  const salary =
    job.salary_min || job.salary_max
      ? `$${job.salary_min || 0} - $${job.salary_max || 0}`
      : "Salary not listed";

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900">{job.title}</h3>
          <p className="text-sm text-slate-600">
            {job.company} | {job.source}
          </p>
          <p className="text-xs text-slate-500">
            {job.location_city || "N/A"}
            {job.remote ? " | Remote" : ""}
          </p>
        </div>
        <MatchScoreBadge score={Math.min(100, Math.max(0, Math.round(sponsorScore * 100)))} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="rounded bg-slate-100 px-2 py-1">Sponsorship: {sponsor}</span>
        {(job.tags || []).slice(0, 3).map((tag) => (
          <span key={tag} className="rounded bg-cyan-50 px-2 py-1 text-cyan-700">
            {tag}
          </span>
        ))}
      </div>

      <p className="mt-2 text-sm text-slate-700">{salary}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded bg-slate-900 px-3 py-2 text-xs text-white" onClick={onSave}>
          Save
        </button>
        <button className="rounded bg-emerald-700 px-3 py-2 text-xs text-white" onClick={onApply}>
          Apply Now
        </button>
        <button className="rounded bg-cyan-700 px-3 py-2 text-xs text-white" onClick={onTailor}>
          Tailor & Apply
        </button>
        <button className="rounded bg-amber-600 px-3 py-2 text-xs text-white" onClick={onReferrals}>
          Find Referrals
        </button>
      </div>
    </article>
  );
}
