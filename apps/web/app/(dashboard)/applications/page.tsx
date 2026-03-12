"use client";

import { useEffect, useState } from "react";

import ApplicationBoard from "@/components/premium/ApplicationBoard";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

const emptyBoard = {
  Saved: [] as any[],
  Applied: [] as any[],
  Interview: [] as any[],
  Offer: [] as any[],
  Archived: [] as any[],
};

const laneToStatus: Record<keyof typeof emptyBoard, string> = {
  Saved: "draft",
  Applied: "applied",
  Interview: "interviewing",
  Offer: "offered",
  Archived: "withdrawn",
};

function toLane(status: string | undefined): keyof typeof emptyBoard {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "draft") return "Saved";
  if (["shortlisted", "tailored", "applied", "submitted"].includes(normalized)) return "Applied";
  if (["phone_screen", "onsite", "interviewing"].includes(normalized)) return "Interview";
  if (["offered", "offer", "accepted"].includes(normalized)) return "Offer";
  return "Archived";
}

export default function ApplicationsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [board, setBoard] = useState(emptyBoard);
  const [error, setError] = useState<string | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!token) return;
      try {
        const apps = (await api.listApplications(token)) as any[];
        const nextBoard: typeof emptyBoard = {
          ...emptyBoard,
          Saved: [],
          Applied: [],
          Interview: [],
          Offer: [],
          Archived: [],
        };
        const decorated = await Promise.all(
          apps.map(async (app) => {
            let jobTitle = "Application";
            let company = "Unknown company";
            try {
              const job = (await api.getJob(token, String(app.job_id))) as any;
              jobTitle = job.title || jobTitle;
              company = job.company || company;
            } catch {
              // Keep lane entry even when job metadata fetch fails.
            }
            return { app, jobTitle, company };
          }),
        );
        for (const { app, jobTitle, company } of decorated) {
          const lane = toLane(app.status);
          nextBoard[lane].push({
            id: String(app.id),
            title: jobTitle,
            company,
            resume: app.tailored_resume_id ? "Tailored" : "Default",
            date: app.created_at ? new Date(app.created_at).toLocaleDateString() : "",
            status: app.status,
            tags: app.notes ? [String(app.notes).slice(0, 40)] : [],
          });
        }
        if (!cancelled) setBoard(nextBoard);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load applications.");
          setBoard(emptyBoard);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleMove(applicationId: string, fromLane: keyof typeof emptyBoard, toLane: keyof typeof emptyBoard) {
    if (!token || fromLane === toLane || movingId === applicationId) return;
    const item = (board[fromLane] || []).find((entry) => String(entry.id) === applicationId);
    if (!item) return;

    setMovingId(applicationId);
    setError(null);
    setBoard((current) => {
      const next = {
        Saved: [...current.Saved],
        Applied: [...current.Applied],
        Interview: [...current.Interview],
        Offer: [...current.Offer],
        Archived: [...current.Archived],
      };
      next[fromLane] = next[fromLane].filter((entry) => String(entry.id) !== applicationId);
      next[toLane] = [{ ...item, status: laneToStatus[toLane] }, ...next[toLane]];
      return next;
    });

    try {
      await api.updateApplication(token, applicationId, { status: laneToStatus[toLane] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update application stage.");
      setBoard((current) => {
        const next = {
          Saved: [...current.Saved],
          Applied: [...current.Applied],
          Interview: [...current.Interview],
          Offer: [...current.Offer],
          Archived: [...current.Archived],
        };
        next[toLane] = next[toLane].filter((entry) => String(entry.id) !== applicationId);
        next[fromLane] = [{ ...item }, ...next[fromLane]];
        return next;
      });
    } finally {
      setMovingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Application Tracker</h1>
      {error ? <p className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}
      <ApplicationBoard board={board} onMove={handleMove} disabled={Boolean(movingId)} />
    </div>
  );
}
