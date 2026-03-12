"use client";

import { motion } from "framer-motion";
import { Bookmark, BookmarkCheck, DollarSign, ExternalLink, Info, MapPin, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import Button from "@/components/premium/ui/Button";
import { getAutomationCompatibility } from "@/lib/automation-compat";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

// Deterministic gradient by company initial
const LOGO_GRADIENTS = [
  ["#3b82f6", "#06b6d4"],  // blue → cyan
  ["#8b5cf6", "#a855f7"],  // violet → purple
  ["#10b981", "#14b8a6"],  // emerald → teal
  ["#f97316", "#f59e0b"],  // orange → amber
  ["#f43f5e", "#ec4899"],  // rose → pink
  ["#6366f1", "#3b82f6"],  // indigo → blue
];

function logoGradient(company) {
  const code = (company || "J").toUpperCase().charCodeAt(0);
  const pair = LOGO_GRADIENTS[code % LOGO_GRADIENTS.length];
  return `linear-gradient(135deg, ${pair[0]}, ${pair[1]})`;
}

function logoInitials(company) {
  return (company || "")
    .split(/[\s-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || "JB";
}

function timeAgo(ts) {
  if (!ts) return null;
  const diffSecs = Date.now() / 1000 - ts;
  if (diffSecs < 60) return "just now";
  if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ago`;
  if (diffSecs < 86400) {
    const h = Math.floor(diffSecs / 3600);
    const m = Math.floor((diffSecs % 3600) / 60);
    return m > 0 ? `${h}h ${m}m ago` : `${h}h ago`;
  }
  const days = Math.floor(diffSecs / 86400);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function exactDateTime(ts) {
  if (!ts) return null;
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const CATEGORY_COLORS = {
  "IT": "bg-blue-50 text-blue-700 border-blue-200",
  "Finance": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Healthcare": "bg-red-50 text-red-700 border-red-200",
  "Marketing": "bg-purple-50 text-purple-700 border-purple-200",
  "Sales": "bg-orange-50 text-orange-700 border-orange-200",
  "Engineering": "bg-yellow-50 text-yellow-700 border-yellow-200",
  "Operations": "bg-slate-50 text-slate-700 border-slate-200",
  "Design": "bg-pink-50 text-pink-700 border-pink-200",
  "HR": "bg-teal-50 text-teal-700 border-teal-200",
  "Legal": "bg-indigo-50 text-indigo-700 border-indigo-200",
  "Education": "bg-cyan-50 text-cyan-700 border-cyan-200",
  "Customer Support": "bg-lime-50 text-lime-700 border-lime-200",
};

function formatSalary(job) {
  if (!job.salary_min && !job.salary_max) return null;
  const fmt = (n) =>
    n >= 1000 ? `$${Math.round(n / 1000)}k` : `$${n.toLocaleString()}`;
  if (job.salary_min && job.salary_max) return `${fmt(job.salary_min)} – ${fmt(job.salary_max)}`;
  if (job.salary_max) return `Up to ${fmt(job.salary_max)}`;
  return `${fmt(job.salary_min)}+`;
}

function MatchRing({ match }) {
  if (match === null || match === undefined) return null;
  const pct = Math.round(match * 100);
  const r = 14;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = pct >= 80 ? "#16a34a" : pct >= 60 ? "#d97706" : "#94a3b8";

  return (
    <div className="flex flex-col items-center" title={`${pct}% match`}>
      <svg width="36" height="36" viewBox="0 0 36 36" className="-rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="3" />
        <circle
          cx="18"
          cy="18"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
        />
      </svg>
      <span className="mt-0.5 text-[10px] font-semibold" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

export default function JobCard({ job, onApply, initialSaved = false }) {
  const token = useAuthStore((s) => s.accessToken);
  const compatibility = getAutomationCompatibility(job.url);
  const supportsPrefill = compatibility === "high" || compatibility === "medium";
  const [saved, setSaved] = useState(Boolean(initialSaved));
  const [saving, setSaving] = useState(false);
  const [applied, setApplied] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    setSaved(Boolean(initialSaved));
  }, [initialSaved]);

  async function toggleSave() {
    if (!token || saving) return;
    setSaving(true);
    try {
      if (saved) {
        await api.unsaveJob(token, job.id);
        setSaved(false);
      } else {
        await api.saveJob(token, job.id);
        setSaved(true);
      }
    } catch {
      // Silently revert
    } finally {
      setSaving(false);
    }
  }

  async function handleApply() {
    if (!job.url || applying) return;
    setApplying(true);
    window.open(job.url, "_blank", "noopener,noreferrer");
    if (onApply) {
      try {
        await onApply(job);
      } catch {
        // Parent handles inline errors.
      }
    }
    setApplied(true);
    setApplying(false);
  }

  const salary = formatSalary(job);
  const postedTime = timeAgo(job.posted_at_ts);
  const postedExact = exactDateTime(job.posted_at_ts);
  const categoryColor = CATEGORY_COLORS[job.category] || "bg-[var(--color-bg-alt)] text-[var(--color-text-muted)] border-[var(--color-border-sub)]";
  const sourceName = job.source
    ? job.source.charAt(0).toUpperCase() + job.source.slice(1).replace(/_/g, " ")
    : null;
  const descPreview = job.description
    ? job.description.replace(/\s+/g, " ").trim().slice(0, 140) + (job.description.length > 140 ? "…" : "")
    : null;
  const tags = (job.tags || []).slice(0, 4);

  // Intelligence badges
  const workMode = job.work_mode;
  const roleFamily = job.role_family;
  const sponsorStatus = job.sponsorship_status;
  const optOk = job.req_opt_allowed === "yes";
  const h1bOk = job.req_h1b_possible === "yes";
  const topSkills = (job.req_programming_languages || job.req_must_have_skills || []).slice(0, 3);
  const seniority = job.req_seniority && job.req_seniority !== "unknown" ? job.req_seniority : null;
  const whyMatched = (job.why_matched || []).slice(0, 3);

  return (
    <motion.div
      whileHover={{ y: -2, boxShadow: "0 8px 32px rgba(0,0,0,0.10)" }}
      transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
      className="flex h-full flex-col rounded-xl border border-[var(--color-border-sub)] bg-[var(--color-surface-1)] p-5 shadow-[var(--shadow-glass)] transition-colors hover:border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] backdrop-blur-[12px]"
    >
      {/* Header */}
      <div className="mb-3 flex items-start gap-3">
        {/* Logo */}
        <div
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white shadow-sm"
          style={{ background: logoGradient(job.company) }}
        >
          {logoInitials(job.company)}
        </div>

        {/* Title + company */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold leading-snug text-[var(--color-text-primary)]" title={job.title}>
            {job.title}
          </h3>
          <p className="mt-0.5 truncate text-xs text-[var(--color-text-secondary)]">{job.company}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {/* Location */}
            <span className="flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
              <MapPin className="h-3 w-3" />
              {job.location}
            </span>
            {/* Type badge */}
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                job.remote || job.type === "Remote"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-blue-100 text-blue-700"
              }`}
            >
              {job.type || "Unknown"}
            </span>
            {/* Category badge */}
            {job.category && job.category !== "Other" ? (
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${categoryColor}`}>
                {job.subcategory && job.subcategory !== "General" ? job.subcategory : job.category}
              </span>
            ) : null}
          </div>
        </div>

        {/* Match ring */}
        <MatchRing match={job.match} />
      </div>

      {/* Description preview */}
      {descPreview ? (
        <p className="mb-3 line-clamp-2 text-[12px] leading-relaxed text-[var(--color-text-secondary)]">{descPreview}</p>
      ) : null}

      {/* Intelligence badges row */}
      <div className="mb-2 flex flex-wrap gap-1.5">
        {/* Work mode */}
        {workMode === "remote" && (
          <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-medium text-emerald-700">Remote</span>
        )}
        {workMode === "hybrid" && (
          <span className="rounded-full bg-cyan-50 border border-cyan-200 px-2 py-0.5 text-[10px] font-medium text-cyan-700">Hybrid</span>
        )}
        {workMode === "onsite" && (
          <span className="rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">On-site</span>
        )}
        {/* Role family */}
        {roleFamily && roleFamily !== "other" && (
          <span className="rounded-full bg-violet-50 border border-violet-200 px-2 py-0.5 text-[10px] font-medium text-violet-700">
            {roleFamily.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
          </span>
        )}
        {/* Seniority */}
        {seniority && (
          <span className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-medium text-amber-700">
            {seniority.charAt(0).toUpperCase() + seniority.slice(1)}
          </span>
        )}
        {/* Sponsorship */}
        {sponsorStatus === "sponsors" && (
          <span className="rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-[10px] font-medium text-blue-700">Sponsors Visa</span>
        )}
        {/* OPT / H1B micro-badges */}
        {optOk && (
          <span className="rounded-full bg-teal-50 border border-teal-200 px-2 py-0.5 text-[10px] font-medium text-teal-700">OPT ✓</span>
        )}
        {h1bOk && (
          <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-medium text-indigo-700">H1B ✓</span>
        )}
      </div>

      {/* Tags */}
      {tags.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-[var(--color-border-sub)] bg-[var(--color-bg-alt)] px-2 py-0.5 text-[10px] text-[var(--color-text-primary)]"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      {/* Top skills */}
      {topSkills.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {topSkills.map((skill) => (
            <span key={skill} className="rounded bg-[var(--color-bg-sunken)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--color-text-secondary)]">
              {skill}
            </span>
          ))}
        </div>
      )}

      {/* Why matched */}
      {whyMatched.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {whyMatched.map((reason) => (
            <span key={reason} className="flex items-center gap-0.5 rounded-full bg-primary/5 px-2 py-0.5 text-[10px] text-primary">
              ✓ {reason}
            </span>
          ))}
        </div>
      )}

      {/* Salary + prefill badge */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {salary ? (
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
            <DollarSign className="h-3 w-3" />
            {salary}
          </span>
        ) : null}
        {supportsPrefill ? (
          <span className="flex items-center gap-1 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-1 text-[11px] font-medium text-primary">
            <Zap className="h-3 w-3" />
            Auto-fill
          </span>
        ) : null}
      </div>

      {/* Actions */}
      <div className="mt-auto flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button
            onClick={handleApply}
            disabled={!job.url || applied || applying}
            className={`text-xs ${applied ? "opacity-60" : ""}`}
          >
            <ExternalLink className="mr-1 h-3.5 w-3.5" />
            {applied ? "Applied" : applying ? "Opening…" : "Apply"}
          </Button>
          <Link
            href={`/jobs/${job.id}`}
            className="flex h-8 items-center gap-1 rounded-lg border border-[var(--color-border-sub)] px-2.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
          >
            <Info className="h-3.5 w-3.5" />
            Details
          </Link>
          <motion.button
            onClick={toggleSave}
            disabled={saving}
            whileTap={{ scale: 0.9 }}
            title={saved ? "Unsave" : "Save for later"}
            className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${
              saved
                ? "border-emerald-300 bg-emerald-50 text-emerald-600"
                : "border-[var(--color-border-sub)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            {saved ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
          </motion.button>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)]">
          {sourceName ? <span>{sourceName}</span> : null}
          {sourceName && postedTime ? <span>·</span> : null}
          {postedTime ? (
            <span title={postedExact ?? undefined} className="cursor-default underline decoration-dotted decoration-[var(--color-border)]">
              {postedTime}
            </span>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}
