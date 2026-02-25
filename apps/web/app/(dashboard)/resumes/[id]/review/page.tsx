"use client";

import { useEffect, useState } from "react";

import { ResumeScoreCard } from "@/components/resume-score-card";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function ResumeReviewPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(force = false): Promise<void> {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = force ? await api.regenerateResumeReview(token, params.id) : await api.getResumeReview(token, params.id);
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, params.id]);

  const scores = report?.full_report?.llm?.scores || {};
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Resume Review</h1>
        <button onClick={() => void load(true)} className="rounded border border-slate-700 px-3 py-2 text-sm">
          Regenerate
        </button>
      </div>
      {loading ? <p className="text-sm text-slate-400">Loading...</p> : null}
      {error ? <p className="rounded bg-red-500/20 p-2 text-sm text-red-200">{error}</p> : null}
      {report ? (
        <>
          <ResumeScoreCard
            overall={scores.overall}
            impact={scores.impact}
            ats={scores.ats}
            clarity={scores.clarity}
            completeness={scores.completeness}
            format={scores.format}
          />
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-3">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Summary</h2>
            <p className="text-sm text-slate-200">{report.summary_text || report?.full_report?.llm?.summary_paragraph || "No summary."}</p>
          </section>
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-3">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Report JSON</h2>
            <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-200">
              {JSON.stringify(report.full_report, null, 2)}
            </pre>
          </section>
        </>
      ) : null}
    </div>
  );
}
