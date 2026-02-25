"use client";

import { useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function ResumeTailorStartPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const [jobId, setJobId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function start(): Promise<void> {
    if (!token) return;
    if (!UUID_RE.test(jobId.trim())) {
      setError("Enter a valid Job UUID.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = (await api.createTailorTaskForResume(token, params.id, { job_id: jobId.trim() })) as { task_id: string };
      setTaskId(result.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start tailoring");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Start Tailoring</h1>
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <input
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          placeholder="Job UUID"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
        />
        <div className="mt-3 flex items-center gap-2">
          <button onClick={() => void start()} disabled={loading} className="rounded bg-cyan-700 px-3 py-2 text-sm text-white">
            {loading ? "Starting..." : "Run Tailoring"}
          </button>
          {taskId ? (
            <Link href={`/resumes/${params.id}/tailor/${jobId}`} className="text-sm text-cyan-300 underline">
              Open result page
            </Link>
          ) : null}
        </div>
      </div>
      {taskId ? <p className="text-sm text-slate-300">Task queued: {taskId}</p> : null}
      {error ? <p className="rounded bg-red-500/20 p-2 text-sm text-red-200">{error}</p> : null}
    </div>
  );
}
