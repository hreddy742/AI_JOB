"use client";

import { useState } from "react";

import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type CoverLetterModalProps = {
  resumeId: string;
  open: boolean;
  onClose: () => void;
};

const TONES = ["professional", "enthusiastic", "concise", "storytelling"] as const;

export function CoverLetterModal({ resumeId, open, onClose }: CoverLetterModalProps) {
  const token = useAuthStore((s) => s.accessToken);
  const [tone, setTone] = useState<(typeof TONES)[number]>("professional");
  const [jobId, setJobId] = useState("");
  const [hiringManager, setHiringManager] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState("");

  if (!open) return null;

  async function generate(): Promise<void> {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const letter = (await api.createCoverLetter(token, resumeId, {
        job_id: jobId || undefined,
        tone,
        hiring_manager_name: hiringManager || undefined,
      })) as { content: string };
      setContent(letter.content || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate cover letter");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-3xl rounded-xl border border-slate-700 bg-slate-900 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Generate Cover Letter</h3>
          <button onClick={onClose} className="rounded border border-slate-700 px-2 py-1 text-xs">
            Close
          </button>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <input
            placeholder="Job ID (optional)"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <input
            placeholder="Hiring Manager (optional)"
            value={hiringManager}
            onChange={(e) => setHiringManager(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <select
            value={tone}
            onChange={(e) => setTone(e.target.value as (typeof TONES)[number])}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          >
            {TONES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={() => void generate()}
            disabled={loading}
            className="rounded bg-cyan-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate"}
          </button>
          {error ? <span className="text-xs text-red-300">{error}</span> : null}
        </div>
        <pre className="mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-200">
          {content || "Generated letter will appear here."}
        </pre>
      </div>
    </div>
  );
}
