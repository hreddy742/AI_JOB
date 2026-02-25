"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { CoverLetterModal } from "@/components/cover-letter-modal";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type ResumeItem = {
  id: string;
  version: number;
  original_text: string;
  created_at: string;
  is_active: boolean;
};

type TailoredItem = {
  id: string;
  job_id: string;
  reviewer_score: number | null;
  supervisor_approved: boolean;
  created_at: string;
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function ResumesPageContent() {
  const token = useAuthStore((s) => s.accessToken);
  const searchParams = useSearchParams();

  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [tailored, setTailored] = useState<TailoredItem[]>([]);

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string>("idle");
  const [taskError, setTaskError] = useState<string | null>(null);
  const [coverLetterOpen, setCoverLetterOpen] = useState(false);
  const [activeTool, setActiveTool] = useState<"tailor" | "review" | "edit" | null>(null);

  const selectedResume = useMemo(
    () => resumes.find((r) => r.id === selectedResumeId) ?? null,
    [resumes, selectedResumeId]
  );

  async function loadResumes(options?: { selectLatest?: boolean; refreshSelectedDetails?: boolean }): Promise<void> {
    if (!token) return;
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const rawItems = (await api.listResumes(token)) as ResumeItem[];
      const items = [...rawItems].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setResumes(items);
      if (items.length === 0) {
        setSelectedResumeId("");
        setTailored([]);
        return;
      }

      const current = selectedResumeId;
      const nextSelectedId =
        options?.selectLatest
          ? items[0].id
          : current && items.some((r) => r.id === current)
            ? current
            : items[0].id;

      if (nextSelectedId !== current) {
        setSelectedResumeId(nextSelectedId);
      }

      if (options?.refreshSelectedDetails || options?.selectLatest) {
        await loadTailored(nextSelectedId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resumes.");
    } finally {
      setLoading(false);
    }
  }

  async function loadTailored(resumeId: string): Promise<void> {
    if (!token || !resumeId) return;
    try {
      const items = (await api.listTailoredResumes(token, resumeId)) as TailoredItem[];
      setTailored(items);
    } catch {
      setTailored([]);
    }
  }

  useEffect(() => {
    void loadResumes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (selectedResumeId) {
      void loadTailored(selectedResumeId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedResumeId, token]);

  useEffect(() => {
    const tool = (searchParams.get("tool") || "").toLowerCase();
    if (tool === "tailor" || tool === "review" || tool === "edit") {
      setActiveTool(tool);
      const target = document.getElementById(`tool-${tool}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    setActiveTool(null);
  }, [searchParams]);

  useEffect(() => {
    if (!token || !taskId) return;
    const timer = setInterval(async () => {
      try {
        const status = (await api.getTailorTask(token, taskId)) as {
          status?: string;
          error?: string;
          tailored_resume_id?: string;
        };
        const next = status.status || "unknown";
        setTaskStatus(next);
        if (status.error) setTaskError(status.error);
        if (next === "completed" || next === "failed") {
          clearInterval(timer);
          if (selectedResumeId) void loadTailored(selectedResumeId);
        }
      } catch {
        clearInterval(timer);
        setTaskStatus("failed");
        setTaskError("Failed to fetch tailoring task status.");
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [token, taskId, selectedResumeId]);

  async function onUpload(): Promise<void> {
    if (!token) {
      setError("Session expired. Please sign in again.");
      return;
    }
    if (!file) {
      setError("Please choose a resume file first.");
      return;
    }
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      await api.uploadResume(token, file);
      setFile(null);
      await loadResumes({ selectLatest: true, refreshSelectedDetails: true });
      setSuccess("Resume uploaded successfully. Parsing has started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(id: string): Promise<void> {
    if (!token) return;
    setDeletingId(id);
    setError(null);
    setSuccess(null);
    try {
      await api.deleteResume(token, id);
      await loadResumes({ refreshSelectedDetails: true });
      if (selectedResumeId === id) {
        const next = resumes.filter((r) => r.id !== id);
        setSelectedResumeId(next[0]?.id || "");
      }
      setSuccess("Resume deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setDeletingId(null);
    }
  }

  async function onRunTailoring(): Promise<void> {
    if (!token || !selectedResumeId) return;
    setTaskError(null);
    setSuccess(null);
    if (!UUID_RE.test(jobId.trim())) {
      setTaskStatus("failed");
      setTaskError("Enter a valid Job ID (UUID).");
      return;
    }
    setTaskStatus("queued");
    try {
      const result = (await api.createTailorTask(token, {
        resume_id: selectedResumeId,
        job_id: jobId.trim(),
      })) as { task_id: string };
      setTaskId(result.task_id);
    } catch (err) {
      setTaskStatus("failed");
      setTaskError(err instanceof Error ? err.message : "Tailoring failed to start.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Resumes</h1>
        <p className="text-sm text-slate-400">
          Upload your base resume, run tailoring per job, and manage generated versions.
        </p>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">Upload Resume</h2>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="file"
            accept=".txt,.md,.pdf,.docx"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm"
          />
          <button
            type="button"
            onClick={onUpload}
            disabled={!file || uploading}
            className="rounded bg-cyan-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Tip: plain text (.txt/.md) works best. PDF/DOCX must contain selectable text (not scanned image).
        </p>
      </section>

      {error ? <div className="rounded-md bg-red-500/20 p-3 text-sm text-red-200">{error}</div> : null}
      {success ? <div className="rounded-md bg-emerald-500/20 p-3 text-sm text-emerald-200">{success}</div> : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Your Resumes</h2>
            <button
              type="button"
              onClick={async () => {
                if (!token) {
                  setError("Session expired. Please sign in again.");
                  return;
                }
                setRefreshing(true);
                setError(null);
                setSuccess(null);
                try {
                  await loadResumes({ refreshSelectedDetails: true });
                  setSuccess("Resume list refreshed.");
                } catch {
                  // loadResumes handles detailed error.
                } finally {
                  setRefreshing(false);
                }
              }}
              disabled={refreshing || loading}
              className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {loading ? <p className="text-sm text-slate-400">Loading...</p> : null}
          {!loading && resumes.length === 0 ? <p className="text-sm text-slate-400">No resumes uploaded yet.</p> : null}
          <div className="space-y-2">
            {resumes.map((resume) => (
              <button
                key={resume.id}
                type="button"
                onClick={() => setSelectedResumeId(resume.id)}
                className={`w-full rounded border px-3 py-2 text-left ${
                  selectedResumeId === resume.id ? "border-cyan-600 bg-slate-800" : "border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">v{resume.version}</span>
                  <span className="text-xs text-slate-400">{new Date(resume.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-slate-300">{resume.original_text.slice(0, 160)}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">Selected Resume</h2>
          {!selectedResume ? (
            <p className="text-sm text-slate-400">Select a resume to view details.</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-slate-800 px-2 py-1 text-xs">ID: {selectedResume.id}</span>
                <Link
                  id="tool-review"
                  href={`/resumes/${selectedResume.id}/review`}
                  className={`rounded border px-2 py-1 text-xs ${
                    activeTool === "review" ? "border-cyan-500 text-cyan-300" : "border-slate-700 text-slate-200"
                  }`}
                >
                  Review
                </Link>
                <Link
                  id="tool-edit"
                  href={`/resumes/${selectedResume.id}/edit`}
                  className={`rounded border px-2 py-1 text-xs ${
                    activeTool === "edit" ? "border-cyan-500 text-cyan-300" : "border-slate-700 text-slate-200"
                  }`}
                >
                  Edit
                </Link>
                <Link href={`/resumes/${selectedResume.id}/tailor`} className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200">
                  Tailor
                </Link>
                <button
                  type="button"
                  onClick={() => setCoverLetterOpen(true)}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200"
                >
                  Cover Letter
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (!token) return;
                    const res = (await api.getResumeDownloadUrl(token, selectedResume.id)) as { url: string };
                    window.open(res.url, "_blank");
                  }}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200"
                >
                  Download
                </button>
                <button
                  type="button"
                  onClick={() => void onDelete(selectedResume.id)}
                  disabled={deletingId === selectedResume.id}
                  className="rounded bg-red-700 px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {deletingId === selectedResume.id ? "Deleting..." : "Delete"}
                </button>
              </div>
              <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-200">
                {selectedResume.original_text}
              </pre>
              <div
                id="tool-tailor"
                className={`rounded border p-3 ${
                  activeTool === "tailor" ? "border-cyan-500 ring-1 ring-cyan-500/60" : "border-slate-700"
                }`}
              >
                <p className="mb-2 text-xs text-slate-300">Run tailoring with a Job ID.</p>
                <input
                  className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                  placeholder="Job UUID (from Jobs -> open job details)"
                  value={jobId}
                  onChange={(e) => setJobId(e.target.value)}
                />
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void onRunTailoring()}
                    className="rounded bg-cyan-700 px-3 py-2 text-sm font-semibold text-white"
                  >
                    Run Tailoring
                  </button>
                  <span className="text-xs text-slate-300">Status: {taskStatus}</span>
                </div>
                {taskError ? <p className="mt-2 text-xs text-red-300">{taskError}</p> : null}
              </div>
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Tailored Versions</h3>
                {tailored.length === 0 ? <p className="text-xs text-slate-400">No tailored outputs yet.</p> : null}
                <div className="space-y-2">
                  {tailored.map((t) => (
                    <div key={t.id} className="rounded border border-slate-700 bg-slate-950 p-2 text-xs">
                      <p>ID: {t.id}</p>
                      <p>Job: {t.job_id}</p>
                      <p>
                        Reviewer score: {t.reviewer_score ?? "N/A"} | Approved: {t.supervisor_approved ? "Yes" : "No"}
                      </p>
                      <p className="text-slate-400">{new Date(t.created_at).toLocaleString()}</p>
                      <Link href={`/resumes/${selectedResume.id}/tailor/${t.job_id}`} className="text-cyan-300 underline">
                        Open Tailor View
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
      {selectedResume ? <CoverLetterModal resumeId={selectedResume.id} open={coverLetterOpen} onClose={() => setCoverLetterOpen(false)} /> : null}
    </div>
  );
}

export default function ResumesPage() {
  return (
    <Suspense fallback={<div className="p-4 text-sm text-slate-400">Loading resumes...</div>}>
      <ResumesPageContent />
    </Suspense>
  );
}
