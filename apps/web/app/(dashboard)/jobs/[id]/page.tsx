"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Briefcase, CheckCircle, DollarSign, ExternalLink, Globe, GraduationCap, MapPin, Shield, Star, Users, Zap } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type JobRequirements = {
  must_have_skills: string[];
  nice_to_have_skills: string[];
  programming_languages: string[];
  frameworks: string[];
  databases: string[];
  cloud_tools: string[];
  ml_ai_skills: string[];
  certifications: string[];
  min_years_experience: number | null;
  experience_years_min: number | null;
  experience_years_max: number | null;
  education_level: string | null;
  seniority: string;
  visa_sponsorship: string;
  opt_allowed: string;
  stem_opt_allowed: string;
  h1b_possible: string;
  us_citizens_only: boolean;
  security_clearance_required: boolean;
  role_family: string;
  ai_relevance_score: number;
  salary_text_raw: string | null;
  salary_extracted_min: number | null;
  salary_extracted_max: number | null;
  salary_period: string;
  confidence: number;
};

type JobDetail = {
  id: string;
  title: string;
  company: string;
  description: string;
  location_city?: string;
  location_state?: string;
  location_country?: string;
  remote: boolean;
  work_mode: string;
  role_family: string;
  job_type: string;
  experience_level: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  sponsorship_status: string;
  sponsorship_score: number;
  tags?: string[];
  url?: string;
  source?: string;
  posted_at?: string;
  category?: string;
  subcategory?: string;
  requirements: JobRequirements | null;
  why_matched: string[];
};

function Badge({ children, color = "default" }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    default: "bg-[var(--color-bg-alt)] border-[var(--color-border-sub)] text-[var(--color-text-secondary)]",
    green: "bg-emerald-50 border-emerald-200 text-emerald-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    violet: "bg-violet-50 border-violet-200 text-violet-700",
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    teal: "bg-teal-50 border-teal-200 text-teal-700",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-700",
    red: "bg-red-50 border-red-200 text-red-700",
    cyan: "bg-cyan-50 border-cyan-200 text-cyan-700",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${colors[color] || colors.default}`}>
      {children}
    </span>
  );
}

function SkillChip({ label }: { label: string }) {
  return (
    <span className="rounded-md bg-[var(--color-bg-sunken)] border border-[var(--color-border-sub)] px-2 py-0.5 font-mono text-xs text-[var(--color-text-primary)]">
      {label}
    </span>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--color-border-sub)] bg-[var(--color-surface-1)] p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[var(--color-text-muted)]">{icon}</span>
        <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function formatSalary(min?: number | null, max?: number | null, currency = "USD") {
  if (!min && !max) return null;
  const fmt = (n: number) => n >= 1000 ? `${currency === "USD" ? "$" : currency}${Math.round(n / 1000)}k` : `${n}`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (max) return `Up to ${fmt(max)}`;
  return `${fmt(min!)}+`;
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const feedbackSentRef = useRef(false);

  useEffect(() => {
    feedbackSentRef.current = false;
  }, [params.id]);

  useEffect(() => {
    if (!token) return;
    api.getJob(token, params.id)
      .then((d) => setJob(d as JobDetail))
      .catch(() => setError("Job not found or unavailable."));
  }, [token, params.id]);

  useEffect(() => {
    if (!token || !job || feedbackSentRef.current) return;
    feedbackSentRef.current = true;
    void api.recordJobFeedback(token, job.id, { event_type: "open" }).catch(() => {
      feedbackSentRef.current = false;
    });
  }, [token, job]);

  async function handleApply() {
    if (!token || !job) return;
    setApplying(true);
    try {
      void api.recordJobFeedback(token, job.id, { event_type: "apply_click" }).catch(() => undefined);
      if (job.url) window.open(job.url, "_blank", "noopener,noreferrer");
      const application = (await api.createApplication(token, { job_id: params.id })) as { id: string };
      await api.queueApplicationPrefill(token, application.id, true);
      setApplied(true);
    } catch {
      setApplied(false);
    } finally {
      setApplying(false);
    }
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-red-600">{error}</p>
        <button className="mt-3 text-sm underline text-[var(--color-text-secondary)]" onClick={() => router.back()}>Go back</button>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6 animate-pulse">
        <div className="h-7 w-1/2 rounded-lg bg-[var(--color-bg-sunken)]" />
        <div className="h-4 w-1/3 rounded bg-[var(--color-bg-sunken)]" />
        <div className="mt-6 space-y-2">
          {[...Array(8)].map((_, i) => <div key={i} className="h-3 rounded bg-[var(--color-bg-sunken)]" />)}
        </div>
      </div>
    );
  }

  const req = job.requirements;
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);
  const extractedSalary = req ? formatSalary(req.salary_extracted_min, req.salary_extracted_max) : null;
  const displaySalary = salary || extractedSalary;

  return (
    <article className="mx-auto max-w-3xl space-y-5 p-6">
      {/* Back */}
      <button onClick={() => router.back()} className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to jobs
      </button>

      {/* Header */}
      <div className="rounded-xl border border-[var(--color-border-sub)] bg-[var(--color-surface-1)] p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">{job.title}</h1>
            <p className="mt-1 text-base text-[var(--color-text-secondary)]">
              {job.company}
              {job.location_city ? ` · ${job.location_city}` : ""}
              {job.location_state ? `, ${job.location_state}` : ""}
              {job.location_country ? `, ${job.location_country}` : ""}
            </p>

            {/* Intelligence badges */}
            <div className="mt-3 flex flex-wrap gap-2">
              {job.work_mode === "remote" && <Badge color="green">Remote</Badge>}
              {job.work_mode === "hybrid" && <Badge color="cyan">Hybrid</Badge>}
              {job.work_mode === "onsite" && <Badge>On-site</Badge>}
              {job.role_family && job.role_family !== "other" && (
                <Badge color="violet">{job.role_family.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</Badge>
              )}
              {req?.seniority && req.seniority !== "unknown" && (
                <Badge color="amber">{req.seniority.charAt(0).toUpperCase() + req.seniority.slice(1)}</Badge>
              )}
              {job.job_type && job.job_type !== "unknown" && (
                <Badge>{job.job_type.replace(/_/g, " ")}</Badge>
              )}
              {job.experience_level && job.experience_level !== "unknown" && (
                <Badge>{job.experience_level}</Badge>
              )}
              {job.sponsorship_status === "sponsors" && <Badge color="blue">Sponsors Visa</Badge>}
              {req?.opt_allowed === "yes" && <Badge color="teal">OPT-friendly</Badge>}
              {req?.h1b_possible === "yes" && <Badge color="indigo">H1B possible</Badge>}
              {req?.security_clearance_required && <Badge color="red">Clearance required</Badge>}
              {req?.us_citizens_only && <Badge color="red">US Citizens only</Badge>}
            </div>

            {/* Compensation */}
            {displaySalary && (
              <div className="mt-3 flex items-center gap-1.5 text-sm font-medium text-emerald-700">
                <DollarSign className="h-4 w-4" />
                {displaySalary}
                {req?.salary_period && req.salary_period !== "unknown" && (
                  <span className="text-xs font-normal text-[var(--color-text-muted)]">/ {req.salary_period}</span>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 shrink-0">
            <button
              onClick={applied ? undefined : handleApply}
              disabled={applying || applied}
              className="rounded-lg px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:brightness-105 disabled:opacity-60"
              style={{ background: applied ? "var(--color-success, #16a34a)" : "var(--color-accent, #1d4ed8)" }}
            >
              {applied ? "Applied ✓" : applying ? "Opening…" : "Apply Now"}
            </button>
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center justify-center gap-1 rounded-lg border border-[var(--color-border-sub)] px-4 py-2 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
                <ExternalLink className="h-3.5 w-3.5" /> View original
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Why matched */}
      {job.why_matched.length > 0 && (
        <Section title="Why this matched" icon={<Star className="h-4 w-4" />}>
          <div className="flex flex-wrap gap-2">
            {job.why_matched.map((reason) => (
              <span key={reason} className="flex items-center gap-1 rounded-full bg-primary/5 border border-primary/20 px-3 py-1 text-xs text-primary">
                <CheckCircle className="h-3 w-3" /> {reason}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Skills & tech stack */}
      {req && (req.programming_languages.length > 0 || req.frameworks.length > 0 || req.cloud_tools.length > 0 || req.ml_ai_skills.length > 0 || req.databases.length > 0 || req.must_have_skills.length > 0) && (
        <Section title="Tech Stack & Skills" icon={<Zap className="h-4 w-4" />}>
          <div className="space-y-3">
            {req.programming_languages.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Languages</p>
                <div className="flex flex-wrap gap-1.5">{req.programming_languages.map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.frameworks.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Frameworks</p>
                <div className="flex flex-wrap gap-1.5">{req.frameworks.map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.cloud_tools.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Cloud & Infrastructure</p>
                <div className="flex flex-wrap gap-1.5">{req.cloud_tools.map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.ml_ai_skills.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">AI / ML</p>
                <div className="flex flex-wrap gap-1.5">{req.ml_ai_skills.map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.databases.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Databases</p>
                <div className="flex flex-wrap gap-1.5">{req.databases.map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.must_have_skills.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Must have</p>
                <div className="flex flex-wrap gap-1.5">{req.must_have_skills.slice(0, 10).map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
            {req.nice_to_have_skills.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[var(--color-text-muted)]">Nice to have</p>
                <div className="flex flex-wrap gap-1.5">{req.nice_to_have_skills.slice(0, 8).map(s => <SkillChip key={s} label={s} />)}</div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Work authorization */}
      {req && (req.visa_sponsorship !== "unknown" || req.opt_allowed !== "unknown" || req.h1b_possible !== "unknown" || req.us_citizens_only || req.security_clearance_required) && (
        <Section title="Work Authorization" icon={<Globe className="h-4 w-4" />}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              { label: "Visa Sponsorship", value: req.visa_sponsorship },
              { label: "OPT Allowed", value: req.opt_allowed },
              { label: "STEM OPT", value: req.stem_opt_allowed },
              { label: "H1B Possible", value: req.h1b_possible },
            ].map(({ label, value }) => value !== "unknown" && (
              <div key={label} className="rounded-lg bg-[var(--color-bg-sunken)] p-3">
                <p className="text-[10px] text-[var(--color-text-muted)]">{label}</p>
                <p className={`mt-0.5 text-sm font-semibold ${value === "yes" || value === "sponsors" ? "text-emerald-600" : value === "no" || value === "no_sponsor" ? "text-red-500" : "text-[var(--color-text-secondary)]"}`}>
                  {value === "yes" ? "Yes ✓" : value === "no" ? "No ✗" : value === "sponsors" ? "Sponsors ✓" : value === "no_sponsor" ? "No ✗" : value}
                </p>
              </div>
            ))}
            {req.us_citizens_only && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-[10px] text-red-600">Restriction</p>
                <p className="mt-0.5 text-sm font-semibold text-red-700">US Citizens Only</p>
              </div>
            )}
            {req.security_clearance_required && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-[10px] text-red-600">Requirement</p>
                <p className="mt-0.5 text-sm font-semibold text-red-700">Clearance Required</p>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Qualifications */}
      {req && (req.education_level || req.min_years_experience || req.experience_years_min || req.certifications.length > 0) && (
        <Section title="Qualifications" icon={<GraduationCap className="h-4 w-4" />}>
          <div className="space-y-2 text-sm text-[var(--color-text-secondary)]">
            {(req.experience_years_min || req.min_years_experience) && (
              <div className="flex items-center gap-2">
                <span className="font-medium text-[var(--color-text-primary)]">Experience:</span>
                {req.experience_years_min && req.experience_years_max
                  ? `${req.experience_years_min}–${req.experience_years_max} years`
                  : `${req.experience_years_min || req.min_years_experience}+ years`}
              </div>
            )}
            {req.education_level && (
              <div className="flex items-center gap-2">
                <span className="font-medium text-[var(--color-text-primary)]">Education:</span>
                {req.education_level.charAt(0).toUpperCase() + req.education_level.slice(1)} degree
              </div>
            )}
            {req.certifications.length > 0 && (
              <div>
                <span className="font-medium text-[var(--color-text-primary)]">Certifications: </span>
                {req.certifications.join(", ")}
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Full description */}
      <Section title="Job Description" icon={<Briefcase className="h-4 w-4" />}>
        <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-text-primary)]">
          {job.description || "No description available."}
        </div>
      </Section>

      {/* Intelligence confidence */}
      {req && req.confidence > 0 && (
        <div className="text-center text-xs text-[var(--color-text-muted)]">
          Intelligence extraction confidence: {Math.round(req.confidence * 100)}%
        </div>
      )}
    </article>
  );
}
