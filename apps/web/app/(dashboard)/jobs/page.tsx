"use client";

import { motion } from "framer-motion";
import { Briefcase, ChevronDown, ChevronUp, MapPin, RefreshCw, Search, SlidersHorizontal, X } from "lucide-react";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";

import JobCard from "@/components/premium/JobCard";
import Button from "@/components/premium/ui/Button";
import { Select } from "@/components/ui/input";
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
  source?: string;
  // Intelligence fields
  work_mode?: string;
  role_family?: string;
  sponsorship_status?: string;
  req_opt_allowed?: string;
  req_h1b_possible?: string;
  req_seniority?: string;
  req_must_have_skills?: string[];
  req_programming_languages?: string[];
  req_ml_ai_skills?: string[];
  req_ai_relevance_score?: number;
  why_matched?: string[];
  category?: string;
  subcategory?: string;
};

type ApplicationCreateResponse = {
  id: string;
};

type MatchingMode = "with_resume" | "without_resume" | "both";

const WINDOW_OPTIONS = [
  { value: "all", label: "All time" },
  { value: "1h", label: "Last hour" },
  { value: "24h", label: "Last 24h" },
  { value: "3d", label: "Last 3 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "14d", label: "Last 14 days" },
  { value: "30d", label: "Last 30 days" },
];

const PAGE_SIZE = 40;
const DEFAULT_EXPERIENCE = "unknown";
const DEFAULT_POSTED_WINDOW = "all";
const DEFAULT_SORT_BY = "latest";
const DEFAULT_MATCHING_MODE: MatchingMode = "with_resume";

function JobCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-[var(--color-border-sub)] bg-[var(--color-surface-1)] p-5 shadow-[var(--shadow-sm)]">
      <div className="mb-4 flex items-start gap-3">
        <div className="h-11 w-11 flex-shrink-0 rounded-xl bg-[var(--color-bg-sunken)]" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded-md bg-[var(--color-bg-sunken)]" />
          <div className="h-3 w-1/2 rounded-md bg-[var(--color-bg-sunken)]" />
          <div className="h-5 w-20 rounded-full bg-[var(--color-bg-sunken)]" />
        </div>
        <div className="h-9 w-9 rounded-full bg-[var(--color-bg-sunken)]" />
      </div>
      <div className="mb-4 space-y-2">
        <div className="h-3 w-full rounded bg-[var(--color-bg-sunken)]" />
        <div className="h-3 w-5/6 rounded bg-[var(--color-bg-sunken)]" />
      </div>
      <div className="mb-4 flex gap-2">
        <div className="h-6 w-16 rounded-full bg-[var(--color-bg-sunken)]" />
        <div className="h-6 w-20 rounded-full bg-[var(--color-bg-sunken)]" />
        <div className="h-6 w-14 rounded-full bg-[var(--color-bg-sunken)]" />
      </div>
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <div className="h-8 w-20 rounded-lg bg-[var(--color-bg-sunken)]" />
          <div className="h-8 w-8 rounded-lg bg-[var(--color-bg-sunken)]" />
        </div>
        <div className="h-3 w-20 rounded bg-[var(--color-bg-sunken)]" />
      </div>
    </div>
  );
}

function PaginationControls({
  page,
  total,
  pageSize,
  loading,
  enrichedLength,
  onPrev,
  onNext,
}: {
  page: number;
  total: number;
  pageSize: number;
  loading: boolean;
  enrichedLength: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  const totalPages = total > 0 ? Math.ceil(total / pageSize) : null;
  return (
    <div className="flex items-center gap-2">
      <Button variant="secondary" onClick={onPrev} disabled={loading || page <= 1} className="text-xs">
        ← Prev
      </Button>
      {totalPages ? (
        <span className="min-w-[4rem] text-center text-xs text-[var(--color-text-secondary)]">
          {page} / {totalPages}
        </span>
      ) : null}
      <Button
        variant="secondary"
        onClick={onNext}
        disabled={loading || (total > 0 ? page >= Math.ceil(total / pageSize) : enrichedLength < pageSize)}
        className="text-xs"
      >
        Next →
      </Button>
    </div>
  );
}

export default function JobDiscoveryPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [jobType, setJobType] = useState("");
  const [category, setCategory] = useState("");
  const [subcategory, setSubcategory] = useState("");
  const [mustHaveSkill, setMustHaveSkill] = useState("");
  const [reqVisaSponsorship, setReqVisaSponsorship] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [optFriendly, setOptFriendly] = useState(false);
  const [h1bFriendly, setH1bFriendly] = useState(false);
  const [noClearance, setNoClearance] = useState(false);
  const [salaryMin, setSalaryMin] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [experience, setExperience] = useState(DEFAULT_EXPERIENCE);
  const [postedWindow, setPostedWindow] = useState(DEFAULT_POSTED_WINDOW);
  const [sortBy, setSortBy] = useState(DEFAULT_SORT_BY);
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  const [page, setPage] = useState(1);
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [matchingMode, setMatchingMode] = useState<MatchingMode>(DEFAULT_MATCHING_MODE);
  const [jobs, setJobs] = useState<SearchJobItem[]>([]);
  const [matchMap, setMatchMap] = useState<Record<string, number>>({});
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [refreshStarted, setRefreshStarted] = useState(false);

  const hasActiveFilters =
    query !== "" ||
    location !== "" ||
    remoteOnly ||
    jobType !== "" ||
    category !== "" ||
    subcategory !== "" ||
    mustHaveSkill !== "" ||
    reqVisaSponsorship !== "" ||
    workMode !== "" ||
    optFriendly ||
    h1bFriendly ||
    noClearance ||
    salaryMin !== "" ||
    roleFamily !== "" ||
    experience !== DEFAULT_EXPERIENCE ||
    postedWindow !== "all";

  function clearFilters() {
    setQuery("");
    setLocation("");
    setRemoteOnly(false);
    setJobType("");
    setCategory("");
    setSubcategory("");
    setMustHaveSkill("");
    setReqVisaSponsorship("");
    setWorkMode("");
    setOptFriendly(false);
    setH1bFriendly(false);
    setNoClearance(false);
    setSalaryMin("");
    setRoleFamily("");
    setExperience(DEFAULT_EXPERIENCE);
    setPostedWindow(DEFAULT_POSTED_WINDOW);
    setSortBy(DEFAULT_SORT_BY);
  }

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

  async function loadSavedJobs() {
    if (!token) return;
    try {
      const items = (await api.listSavedJobs(token)) as Array<{ id: string }>;
      setSavedIds(new Set((items || []).map((item) => String(item.id))));
    } catch {
      setSavedIds(new Set());
    }
  }

  function applyWindow(params: URLSearchParams) {
    if (postedWindow === "all") return;
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
      if (jobType) params.set("job_type", jobType);
      if (category) params.set("category", category);
      if (subcategory) params.set("subcategory", subcategory);
      if (mustHaveSkill.trim()) params.set("must_have_skill", mustHaveSkill.trim());
      if (reqVisaSponsorship) params.set("req_visa_sponsorship", reqVisaSponsorship);
      if (workMode) params.set("work_mode", workMode);
      if (optFriendly) params.set("opt_friendly", "true");
      if (h1bFriendly) params.set("h1b_friendly", "true");
      if (noClearance) params.set("no_clearance", "true");
      if (salaryMin) params.set("salary_min", salaryMin);
      if (roleFamily) params.set("role_family", roleFamily);
      if (experience !== "unknown") params.set("experience_level", experience);
      applyWindow(params);
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      params.set("sort_by", sortBy === "oldest" ? "oldest" : "latest");

      const matchesPromise =
        useResumeMatching && selectedResumeId
          ? (api.getJobMatches(token, selectedResumeId, PAGE_SIZE, 0.4) as Promise<{ items: MatchItem[] }>).catch(() => null)
          : Promise.resolve(null);

      const [result, matchesResult] = await Promise.all([
        api.searchJobs(token, params) as Promise<{ items: SearchJobItem[]; total: number; refresh_started?: boolean }>,
        matchesPromise,
      ]);

      setJobs(result.items || []);
      setTotal(result.total || 0);
      setRefreshStarted(Boolean(result.refresh_started));

      if (matchesResult) {
        const nextMatchMap: Record<string, number> = {};
        (matchesResult.items || []).forEach((m) => {
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
    void loadSavedJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 350);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedResumeId, matchingMode, query, location, remoteOnly, jobType, category, subcategory, mustHaveSkill, reqVisaSponsorship, workMode, optFriendly, h1bFriendly, noClearance, salaryMin, roleFamily, experience, postedWindow, sortBy, page]);

  useEffect(() => {
    setPage(1);
  }, [selectedResumeId, matchingMode, query, location, remoteOnly, jobType, category, subcategory, mustHaveSkill, reqVisaSponsorship, workMode, optFriendly, h1bFriendly, noClearance, salaryMin, roleFamily, experience, postedWindow, sortBy]);

  useEffect(() => {
    const useResumeMatching = matchingMode === "with_resume" || matchingMode === "both";
    if (!useResumeMatching && sortBy === "best_match") {
      setSortBy("latest");
    }
  }, [matchingMode, sortBy]);

  // Retry once after 15s if background refresh started but no results
  useEffect(() => {
    if (!refreshStarted || loading || jobs.length > 0) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 15000);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshStarted]);

  async function handleApply(job: SearchJobItem) {
    if (!token) return;
    try {
      setError(null);
      void api.recordJobFeedback(token, job.id, { event_type: "apply_click" }).catch(() => undefined);
      const app = (await api.createApplication(token, { job_id: job.id })) as ApplicationCreateResponse;
      await api.queueApplicationPrefill(token, app.id, true);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Opened the job page, but automation did not start: ${err.message}`
          : "Opened the job page, but automation did not start.",
      );
    }
  }

  const enriched = useMemo(() => {
    const mapped = jobs.map((job) => {
        const locationText =
          [job.location_city, job.location_state, job.location_country].filter(Boolean).join(", ") || "Remote";
        const resumeScore = matchMap[job.id] ?? null;
        return {
          ...job,
          location: locationText,
          type: job.remote ? "Remote" : job.job_type || "Unknown",
          match: resumeScore,
        };
      });

    if (sortBy === "best_match") {
      return mapped.sort((a, b) => (b.match ?? -1) - (a.match ?? -1));
    }
    if (sortBy === "oldest") {
      return mapped.sort((a, b) => (a.posted_at_ts || 0) - (b.posted_at_ts || 0));
    }
    return mapped.sort((a, b) => (b.posted_at_ts || 0) - (a.posted_at_ts || 0));
  }, [jobs, matchMap, sortBy]);

  const paginationProps = {
    page,
    total,
    pageSize: PAGE_SIZE,
    loading,
    enrichedLength: enriched.length,
    onPrev: () => setPage((p) => Math.max(1, p - 1)),
    onNext: () => setPage((p) => p + 1),
  };

  const useResumeMatching = matchingMode === "with_resume" || matchingMode === "both";

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--color-text-primary)]">Job Discovery</h1>
          <p className="body-sm mt-0.5 text-[var(--color-text-secondary)]">Find and track your next opportunity</p>
        </div>
        <button
          onClick={async () => {
            if (refreshing || !token) return;
            setRefreshing(true);
            try {
              await api.refreshJobs(token);
            } catch {
              // non-critical — still reload cached results
            } finally {
              setRefreshing(false);
              void loadJobs();
            }
          }}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--color-border-sub)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-2)] disabled:opacity-40"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Fetching…" : "Refresh"}
        </button>
      </div>

      {/* Filter bar */}
      <div className="rounded-xl border border-[var(--color-border-sub)] bg-[var(--color-surface-1)] p-4 shadow-[var(--shadow-glass)] backdrop-blur-[12px]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Filters
            {hasActiveFilters ? (
              <span className="rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] text-[var(--color-accent)]">
                Active
              </span>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setFiltersCollapsed((v) => !v)}
            className="flex h-8 items-center gap-1.5 rounded-lg border border-[var(--color-border-sub)] px-2.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
          >
            {filtersCollapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
            {filtersCollapsed ? "Expand" : "Minimize"}
          </button>
        </div>
        {!filtersCollapsed ? (
          <>
        {/* Row 1 — text inputs */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={query}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void loadJobs(); }}
              placeholder="Title, company, skills… (e.g. ai, software engineer)"
              className="h-10 w-full rounded-lg border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.65)] pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-glow)] transition-colors"
            />
          </div>
          <div className="relative w-48 shrink-0">
            <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={location}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setLocation(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void loadJobs(); }}
              placeholder="Country (e.g. USA)"
              className="h-10 w-full rounded-lg border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.65)] pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-glow)] transition-colors"
            />
          </div>
        </div>

        {/* Row 2 — filter controls */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {/* Remote toggle */}
          <button
            type="button"
            onClick={() => setRemoteOnly((v) => !v)}
            className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-medium transition-all ${
              remoteOnly
                ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                : "border-[var(--color-border-sub)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${remoteOnly ? "bg-[var(--color-accent)]" : "bg-[var(--color-text-muted)]"}`} />
            Remote only
          </button>

          <Select value={workMode} onChange={(e: ChangeEvent<HTMLSelectElement>) => setWorkMode(e.target.value)} className="h-9 w-32 py-0 text-xs">
            <option value="">Any mode</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </Select>

          <Select value={experience} onChange={(e: ChangeEvent<HTMLSelectElement>) => setExperience(e.target.value)} className="h-9 w-32 py-0 text-xs">
            <option value="unknown">Any level</option>
            <option value="entry">Entry</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
            <option value="lead">Lead</option>
            <option value="executive">Executive</option>
          </Select>

          <Select
            value={jobType}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setJobType(e.target.value)}
            className="h-9 w-36 py-0 text-xs"
          >
            <option value="">Any type</option>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
          </Select>

          <Select
            value={category}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => { setCategory(e.target.value); setSubcategory(""); }}
            className="h-9 w-36 py-0 text-xs"
          >
            <option value="">Any field</option>
            <option value="IT">IT</option>
            <option value="Finance">Finance</option>
            <option value="Healthcare">Healthcare</option>
            <option value="Marketing">Marketing</option>
            <option value="Sales">Sales</option>
            <option value="Engineering">Engineering</option>
            <option value="Operations">Operations</option>
            <option value="Design">Design</option>
            <option value="HR">HR</option>
            <option value="Legal">Legal</option>
            <option value="Education">Education</option>
            <option value="Customer Support">Customer Support</option>
          </Select>

          {category === "IT" && (
            <Select value={subcategory} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSubcategory(e.target.value)} className="h-9 w-40 py-0 text-xs">
              <option value="">Any IT role</option>
              <option value="AI/ML">AI / ML</option>
              <option value="Frontend">Frontend</option>
              <option value="Backend">Backend</option>
              <option value="Full Stack">Full Stack</option>
              <option value="DevOps/Cloud">DevOps / Cloud</option>
              <option value="Data Engineering">Data Engineering</option>
              <option value="Data Science">Data Science</option>
              <option value="Cybersecurity">Cybersecurity</option>
              <option value="Mobile">Mobile</option>
              <option value="QA/Testing">QA / Testing</option>
              <option value="Product/Design">Product / Design</option>
              <option value="Database">Database</option>
              <option value="Software Engineering">Software Engineering</option>
            </Select>
          )}
          {category === "Engineering" && (
            <Select value={subcategory} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSubcategory(e.target.value)} className="h-9 w-40 py-0 text-xs">
              <option value="">Any engineering</option>
              <option value="Mechanical">Mechanical</option>
              <option value="Electrical">Electrical</option>
              <option value="Civil">Civil</option>
              <option value="Chemical">Chemical</option>
              <option value="Aerospace">Aerospace</option>
              <option value="Manufacturing">Manufacturing</option>
            </Select>
          )}
          {category === "Finance" && (
            <Select value={subcategory} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSubcategory(e.target.value)} className="h-9 w-40 py-0 text-xs">
              <option value="">Any finance</option>
              <option value="Accounting">Accounting</option>
              <option value="Investment">Investment</option>
              <option value="Banking">Banking</option>
              <option value="Quant/Trading">Quant / Trading</option>
              <option value="FinTech">FinTech</option>
            </Select>
          )}

          <input
            type="text"
            value={mustHaveSkill}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setMustHaveSkill(e.target.value)}
            placeholder="Must-have skill"
            className="h-9 w-36 rounded-lg border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.65)] px-3 text-xs text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-glow)] transition-colors"
          />

          <Select value={reqVisaSponsorship} onChange={(e: ChangeEvent<HTMLSelectElement>) => setReqVisaSponsorship(e.target.value)} className="h-9 w-36 py-0 text-xs">
            <option value="">Any sponsorship</option>
            <option value="sponsors">Sponsors</option>
            <option value="no_sponsor">No sponsorship</option>
            <option value="unknown">Unknown</option>
          </Select>

          <button
            type="button"
            onClick={() => setOptFriendly((v) => !v)}
            className={`flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-all ${
              optFriendly
                ? "border-emerald-400 bg-emerald-50 text-emerald-700"
                : "border-[var(--color-border-sub)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            OPT-friendly
          </button>

          <button
            type="button"
            onClick={() => setH1bFriendly((v) => !v)}
            className={`flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-all ${
              h1bFriendly
                ? "border-blue-400 bg-blue-50 text-blue-700"
                : "border-[var(--color-border-sub)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            H1B-possible
          </button>

          <button
            type="button"
            onClick={() => setNoClearance((v) => !v)}
            className={`flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-all ${
              noClearance
                ? "border-rose-400 bg-rose-50 text-rose-700"
                : "border-[var(--color-border-sub)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            No Clearance
          </button>

          <Select value={roleFamily} onChange={(e: ChangeEvent<HTMLSelectElement>) => setRoleFamily(e.target.value)} className="h-9 w-40 py-0 text-xs">
            <option value="">Any role family</option>
            <option value="ai_ml">AI / ML</option>
            <option value="software_engineering">Software Engineering</option>
            <option value="data">Data</option>
            <option value="devops_cloud">DevOps / Cloud</option>
            <option value="product">Product</option>
            <option value="design">Design</option>
            <option value="security">Security</option>
            <option value="other">Other</option>
          </Select>

          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-[var(--color-text-muted)]">$</span>
            <input
              type="number"
              min={0}
              step={10000}
              value={salaryMin}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setSalaryMin(e.target.value)}
              placeholder="Min salary"
              className="h-9 w-32 rounded-lg border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.65)] pl-6 pr-3 text-xs text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-glow)] transition-colors"
            />
          </div>

          <Select value={postedWindow} onChange={(e: ChangeEvent<HTMLSelectElement>) => setPostedWindow(e.target.value)} className="h-9 w-32 py-0 text-xs">
            {WINDOW_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </Select>

          <Select value={sortBy} onChange={(e: ChangeEvent<HTMLSelectElement>) => setSortBy(e.target.value)} className="h-9 w-36 py-0 text-xs">
            <option value="latest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="best_match" disabled={!useResumeMatching || !selectedResumeId}>Best match</option>
          </Select>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              title="Clear all filters"
              className="flex h-9 items-center gap-1.5 rounded-lg border border-[var(--color-border-sub)] px-3 text-xs text-[var(--color-text-secondary)] hover:border-red-300 hover:text-red-600 transition-colors"
            >
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}

          {/* Search button — always last, always visible */}
          <button
            type="button"
            onClick={() => void loadJobs()}
            disabled={loading}
            className="ml-auto flex h-9 items-center gap-2 rounded-lg bg-[var(--color-accent)] px-5 text-sm font-semibold text-white shadow-sm transition hover:brightness-105 disabled:opacity-50"
          >
            <Search className="h-3.5 w-3.5" />
            Search
          </button>
        </div>

        {/* Row 3 — resume context */}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-[var(--color-border-sub)] pt-3">
          <SlidersHorizontal className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
          <span className="text-xs text-[var(--color-text-muted)]">Resume context:</span>
          <Select
            value={matchingMode}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setMatchingMode(e.target.value as MatchingMode)}
            className="h-8 w-40 py-0 text-xs"
          >
            <option value="with_resume">With resume</option>
            <option value="without_resume">Without resume</option>
            <option value="both">Both</option>
          </Select>
          <Select
            value={selectedResumeId}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedResumeId(e.target.value)}
            disabled={matchingMode === "without_resume" || resumes.length === 0}
            className="h-8 min-w-[160px] flex-1 py-0 text-xs"
          >
            <option value="">{resumes.length === 0 ? "No resumes uploaded" : "Select resume…"}</option>
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label || `Resume v${r.version}`} — {r.file_name}
              </option>
            ))}
          </Select>
        </div>
          </>
        ) : (
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-xs text-[var(--color-text-muted)]">
              Filter bar minimized.
              {hasActiveFilters ? " Active filters are applied." : ""}
            </span>
            {hasActiveFilters ? (
              <button
                type="button"
                onClick={clearFilters}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-[var(--color-border-sub)] px-2.5 text-xs text-[var(--color-text-secondary)] hover:border-red-300 hover:text-red-600 transition-colors"
              >
                <X className="h-3.5 w-3.5" /> Clear filters
              </button>
            ) : null}
          </div>
        )}
      </div>

      {/* Error */}
      {error ? (
        <div className="flex items-center gap-3 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          <span className="font-medium">Search error:</span> {error}
          <button onClick={() => void loadJobs()} className="ml-auto text-xs underline opacity-70 hover:opacity-100">
            Retry
          </button>
        </div>
      ) : null}

      {/* Results header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {loading ? (
            <span className="body-sm text-[var(--color-text-secondary)]">Searching…</span>
          ) : (
            <>
              <span className="font-display text-lg font-semibold text-[var(--color-text-primary)]">
                {total > 0 ? `${total.toLocaleString()} Jobs` : "No Jobs Found"}
              </span>
              {total > 0 && (
                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  Page {page} of {Math.ceil(total / PAGE_SIZE)}
                </span>
              )}
            </>
          )}
        </div>
        <PaginationControls {...paginationProps} />
      </div>

      {/* Refresh banner */}
      {!error && enriched.length === 0 && refreshStarted && !loading ? (
        <div className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          <RefreshCw className="h-4 w-4 animate-spin" />
          A fresh fetch has started — results will appear shortly.
        </div>
      ) : null}

      {/* Job grid */}
      {loading ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <JobCardSkeleton key={i} />
          ))}
        </div>
      ) : enriched.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {enriched.map((job, idx) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: Math.min(idx * 0.03, 0.3) }}
            >
              <JobCard job={job} onApply={handleApply} initialSaved={savedIds.has(job.id)} />
            </motion.div>
          ))}
        </div>
      ) : !error ? (
        /* Empty state */
        <div className="flex flex-col items-center py-20 text-center">
          <div className="mb-5 rounded-2xl bg-primary/10 p-6">
            <Briefcase className="h-10 w-10 text-primary" />
          </div>
          <p className="font-display text-xl font-semibold text-[var(--color-text-primary)]">No jobs found</p>
          <p className="body-sm mt-2 max-w-xs text-[var(--color-text-secondary)]">
            {refreshing
              ? "Fetching jobs from job boards — this takes about 30 seconds…"
              : hasActiveFilters
                ? "Try broadening your search, adjusting the posted window, or clearing your filters."
                : "Your job feed is empty. Click below to fetch the latest listings."}
          </p>
          <div className="mt-5 flex gap-3">
              <Button
                variant="primary"
                disabled={refreshing}
                onClick={async () => {
                  if (!token || refreshing) return;
                  setRefreshing(true);
                  try {
                    await api.refreshJobs(token);
                  } catch {
                    // ignore
                  } finally {
                    setRefreshing(false);
                    void loadJobs();
                  }
                }}
              >
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Fetching…" : "Fetch Jobs"}
              </Button>
            {hasActiveFilters && (
              <Button variant="secondary" onClick={clearFilters}>
                <X className="mr-1.5 h-3.5 w-3.5" /> Clear filters
              </Button>
            )}
          </div>
        </div>
      ) : null}

      {/* Bottom pagination */}
      {enriched.length > 0 ? (
        <div className="flex justify-end">
          <PaginationControls {...paginationProps} />
        </div>
      ) : null}
    </div>
  );
}
