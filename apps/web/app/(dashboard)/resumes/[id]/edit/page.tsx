"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type VersionItem = {
  id: string;
  version_number: number;
  change_summary: string | null;
  created_at: string;
};

export default function ResumeEditPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const [resume, setResume] = useState<any>(null);
  const [originalValue, setOriginalValue] = useState("");
  const [newValue, setNewValue] = useState("");
  const [summary, setSummary] = useState("Edited content");
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(): Promise<void> {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [r, v] = await Promise.all([api.getResume(token, params.id), api.listResumeVersions(token, params.id)]);
      setResume(r);
      setVersions((v as VersionItem[]) || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resume editor");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, params.id]);

  async function saveEdit(): Promise<void> {
    if (!token) return;
    try {
      await api.editResume(token, params.id, {
        section: "manual",
        field_path: "text",
        original_value: originalValue,
        new_value: newValue,
        change_summary: summary,
      });
      setOriginalValue("");
      setNewValue("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save edit");
    }
  }

  async function restoreVersion(n: number): Promise<void> {
    if (!token) return;
    try {
      await api.restoreResumeVersion(token, params.id, n);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore version");
    }
  }

  const preview = useMemo(() => resume?.original_text || "", [resume]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Edit Resume</h1>
      {loading ? <p className="text-sm text-slate-400">Loading...</p> : null}
      {error ? <p className="rounded bg-red-500/20 p-2 text-sm text-red-200">{error}</p> : null}

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Apply Edit</h2>
        <textarea
          value={originalValue}
          onChange={(e) => setOriginalValue(e.target.value)}
          placeholder="Exact text to replace"
          className="mb-2 min-h-24 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        />
        <textarea
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder="New text"
          className="mb-2 min-h-24 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        />
        <input
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          className="mb-2 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          placeholder="Change summary"
        />
        <button onClick={() => void saveEdit()} className="rounded bg-cyan-700 px-3 py-2 text-sm font-semibold text-white">
          Save Edit
        </button>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Version History</h2>
          <div className="space-y-2">
            {versions.length === 0 ? <p className="text-xs text-slate-400">No versions yet.</p> : null}
            {versions.map((v) => (
              <div key={v.id} className="rounded border border-slate-700 bg-slate-950 p-2 text-xs">
                <p>v{v.version_number}</p>
                <p>{v.change_summary || "No summary"}</p>
                <p className="text-slate-400">{new Date(v.created_at).toLocaleString()}</p>
                <button onClick={() => void restoreVersion(v.version_number)} className="mt-1 text-cyan-300 underline">
                  Restore
                </button>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Current Content</h2>
          <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-200">
            {preview}
          </pre>
        </div>
      </section>
    </div>
  );
}
