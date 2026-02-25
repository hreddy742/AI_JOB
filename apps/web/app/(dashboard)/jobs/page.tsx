"use client";

import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";

import JobCard from "@/components/premium/JobCard";
import Button from "@/components/premium/ui/Button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type ResumeItem = {
  id: string;
  label: string;
  version: number;
  file_name: string;
  created_at: string;
};

type MatchItem = {
  job_id: string;
  similarity_score: number;
};

type SearchJobItem = {
  id: string;
  title: string;
  company: string;
  description?: string;
  location_city?: string;
  location_state?: string;
  location_country?: string;
  remote?: boolean;
  job_type?: string;
  experience_level?: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  tags?: string[];
  url?: string;
  posted_at_ts?: number;
};

type MatchingMode = "with_resume" | "without_resume" | "both";
type TitleMatchMode = "fuzzy" | "phrase" | "exact";

const WINDOW_OPTIONS = [
  { value: "1h", label: "Last hour" },
  { value: "24h", label: "Last 24 hours" },
  { value: "3d", label: "Last 3 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "14d", label: "Last 14 days" },
  { value: "30d", label: "Last 30 days" },
];

export default function JobDiscoveryPage() {
  const PAGE_SIZE = 50;
  const token = useAuthStore((s) => s.accessToken);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [titleMatchMode, setTitleMatchMode] = useState<TitleMatchMode>("phrase");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [experience, setExperience] = useState("unknown");
  const [postedWindow, setPostedWindow] = useState("7d");
  const [sortBy, setSortBy] = useState("latest");
  const [page, setPage] = useState(1);
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [matchingMode, setMatchingMode] = useState<MatchingMode>("with_resume");
  const [jobs, setJobs] = useState<SearchJobItem[]>([]);
  const [matchMap, setMatchMap] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [refreshStarted, setRefreshStarted] = useState(false);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem("active_resume_id") : null;
    if (stored) setSelectedResumeId(stored);
  }, []);

  useEffect(() => {
    function onActiveResumeChanged(event: Event) {
      const custom = event as CustomEvent<{ resumeId?: string }>;
      if (custom.detail?.resumeId) setSelectedResumeId(custom.detail.resumeId);
    }
    window.addEventListener("active-resume-changed", onActiveResumeChanged as EventListener);
    return () => window.removeEventListener("active-resume-changed", onActiveResumeChanged as EventListener);
  }, []);

  async function loadResumes() {
    if (!token) return;
    try {
      const items = (await api.listResumes(token)) as ResumeItem[];
      const sorted = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setResumes(sorted);
      if (!selectedResumeId && sorted.length > 0) {
        setSelectedResumeId(sorted[0].id);
        window.localStorage.setItem("active_resume_id", sorted[0].id);
      }
    } catch {
      setResumes([]);
    }
  }

  function applyWindow(params: URLSearchParams) {
    if (postedWindow === "1h") {
      params.set("min_hours_ago", "1");
      return;
    }
    if (postedWindow === "24h") {
      params.set("days_ago", "1");
      return;
    }
    params.set("days_ago", postedWindow.replace("d", ""));
  }

  async function loadJobs() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const useResumeMatching = matchingMode === "with_resume" || matchingMode === "both";
      const includeWithoutResumeContext = matchingMode === "without_resume" || matchingMode === "both";
      const params = new URLSearchParams();
      const effectiveQuery = query.trim();
      if (effectiveQuery) params.set("q", effectiveQuery);
      if (useResumeMatching && selectedResumeId) params.set("resume_id", selectedResumeId);
      params.set("use_resume_context", useResumeMatching ? "true" : "false");
      params.set("include_without_resume_context", includeWithoutResumeContext ? "true" : "false");
      if (location.trim()) params.set("location_country", location.trim());
      if (remoteOnly) params.set("remote", "true");
      if (experience !== "unknown") params.set("experience_level", experience);
      applyWindow(params);
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      params.set("sort_by", sortBy === "oldest" ? "oldest" : "latest");
      params.set("title_match_mode", titleMatchMode);

      const result = (await api.searchJobs(token, params)) as {
        items: SearchJobItem[];
        total: number;
        refresh_started?: boolean;
      };
      setJobs(result.items || []);
      setTotal(result.total || 0);
      setRefreshStarted(Boolean(result.refresh_started));

      if (useResumeMatching && selectedResumeId) {
        const matches = (await api.getJobMatches(token, selectedResumeId, 200, 0.0)) as { items: MatchItem[] };
        const nextMatchMap: Record<string, number> = {};
        (matches.items || []).forEach((m) => {
          nextMatchMap[m.job_id] = m.similarity_score;
        });
        setMatchMap(nextMatchMap);
      } else {
        setMatchMap({});
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs.");
      setJobs([]);
      setTotal(0);
      setRefreshStarted(false);
      setMatchMap({});
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadResumes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 350);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedResumeId, matchingMode, query, location, remoteOnly, experience, postedWindow, sortBy, titleMatchMode, page]);

  useEffect(() => {
    setPage(1);
  }, [selectedResumeId, matchingMode, query, location, remoteOnly, experience, postedWindow, sortBy, titleMatchMode]);

  useEffect(() => {
    const useResumeMatching = matchingMode === "with_resume" || matchingMode === "both";
    if (!useResumeMatching && sortBy === "best_match") {
      setSortBy("latest");
    }
  }, [matchingMode, sortBy]);

  useEffect(() => {
    if (!refreshStarted || loading || jobs.length > 0) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 15000);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshStarted, loading, jobs.length]);

  const enriched = useMemo(() => {
    const mapped = jobs.map((job) => {
      const title = job.title || "";
      const company = job.company || "";
      const locationText = [job.location_city, job.location_state, job.location_country].filter(Boolean).join(", ") || "Remote";
      const jdText = `${job.description || ""} ${(job.tags || []).join(" ")}`.toLowerCase();
      const hasResumeScore = matchMap[job.id] !== undefined;
      const fallbackScore = Math.min(0.95, Math.max(0.35, ((jdText.length % 40) + 35) / 100));
      const score = hasResumeScore ? matchMap[job.id] : fallbackScore;
      const missing: string[] = [];
      for (const tag of job.tags || []) {
        if (!jdText.includes(tag.toLowerCase())) continue;
      }
      return {
        ...job,
        logo: company
          .split(" ")
          .filter(Boolean)
          .slice(0, 2)
          .map((part) => part[0])
          .join("")
          .toUpperCase() || "JB",
        location: locationText,
        type: job.remote ? "Remote" : job.job_type || "Unknown",
        match: Number(score || 0),
        missing,
      };
    });

    if (sortBy === "best_match") {
      return mapped.sort((a, b) => (b.match || 0) - (a.match || 0));
    }
    if (sortBy === "oldest") {
      return mapped.sort((a, b) => (a.posted_at_ts || 0) - (b.posted_at_ts || 0));
    }
    return mapped.sort((a, b) => (b.posted_at_ts || 0) - (a.posted_at_ts || 0));
  }, [jobs, matchMap, sortBy]);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Job Discovery</h1>
      <Card>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
          <div className="xl:col-span-2">
            <p className="mb-1 text-xs text-slate-400">Search</p>
            <Input value={query} onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)} placeholder="Title, company, keywords" />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-400">Location</p>
            <Input value={location} onChange={(e: ChangeEvent<HTMLInputElement>) => setLocation(e.target.value)} placeholder="Country or location" />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-400">Experience</p>
            <Select value={experience} onChange={(e: ChangeEvent<HTMLSelectElement>) => setExperience(e.target.value)}>
              <option value="unknown">Any</option>
              <option value="entry">Entry</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
              <option value="executive">Exec</option>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-400">Posted</p>
            <Select value={postedWindow} onChange={(e: ChangeEvent<HTMLSelectElement>) => setPostedWindow(e.target.value)}>
              {WINDOW_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-400">Sort</p>
            <Select value={sortBy} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSortBy(e.target.value)}>
              <option value="latest">Time: New to Old</option>
              <option value="oldest">Time: Old to New</option>
              <option
                value="best_match"
                disabled={!(matchingMode === "with_resume" || matchingMode === "both") || !selectedResumeId}
              >
                Resume: High to Low
              </option>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-400">Title Match</p>
            <Select value={titleMatchMode} onChange={(e: ChangeEvent<HTMLSelectElement>) => setTitleMatchMode(e.target.value as TitleMatchMode)}>
              <option value="fuzzy">Fuzzy</option>
              <option value="phrase">Phrase</option>
              <option value="exact">Exact title</option>
            </Select>
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="xl:col-span-1">
            <p className="mb-1 text-xs text-slate-400">Filter</p>
            <label className="flex h-10 items-center gap-2 rounded-md border border-white/10 px-3 text-sm">
            <input type="checkbox" checked={remoteOnly} onChange={(e: ChangeEvent<HTMLInputElement>) => setRemoteOnly(e.target.checked)} />
            Remote only
            </label>
          </div>

          <div className="xl:col-span-2">
            <p className="mb-1 text-xs text-slate-400">Mode</p>
            <Select value={matchingMode} onChange={(e: ChangeEvent<HTMLSelectElement>) => setMatchingMode(e.target.value as MatchingMode)}>
              <option value="with_resume">Resume</option>
              <option value="without_resume">No Resume</option>
              <option value="both">Both</option>
            </Select>
          </div>

          <div className="xl:col-span-2">
            <p className="mb-1 text-xs text-slate-400">Resume</p>
            <Select
              value={selectedResumeId}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedResumeId(e.target.value)}
              disabled={matchingMode === "without_resume"}
            >
              <option value="">Select</option>
              {resumes.map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.label || `Resume v${resume.version}`} ({resume.file_name})
                </option>
              ))}
            </Select>
          </div>

          <div className="xl:col-span-1">
            <p className="mb-1 text-xs text-transparent">Action</p>
            <Button variant="primary" onClick={() => void loadJobs()} disabled={loading} className="w-full">
              <Search className="mr-1 h-4 w-4" /> {loading ? "Searching..." : "Search"}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Showing 50 jobs per page.
        </p>
      </Card>

      {error ? <div className="rounded-md bg-red-500/20 p-3 text-sm text-red-200">{error}</div> : null}
      {!error && enriched.length === 0 && refreshStarted ? (
        <div className="rounded-md bg-amber-500/20 p-3 text-sm text-amber-100">
          No jobs matched right now. We started a fresh background fetch. New jobs will appear soon.
        </div>
      ) : null}

      <div className="text-sm text-slate-300">
        Showing {enriched.length} jobs on page {page} {total ? `(Total found: ${total})` : ""}.
      </div>

      <div className="flex items-center gap-2">
        <Button variant="secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={loading || page <= 1}>
          Previous 50
        </Button>
        <Button
          variant="secondary"
          onClick={() => setPage((p) => p + 1)}
          disabled={loading || (total > 0 ? page >= Math.ceil(total / PAGE_SIZE) : enriched.length < PAGE_SIZE)}
        >
          Next 50
        </Button>
      </div>

      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {enriched.map((job, idx) => (
          <motion.div key={job.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: idx * 0.03 } }}>
            <JobCard job={job} />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
