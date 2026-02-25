"use client";

import { useEffect, useMemo, useState } from "react";
import { BriefcaseBusiness, FileCheck2, Send, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Grid } from "@/components/layout/Grid";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { GlassCard } from "@/components/ui/GlassCard";
import { JobCard } from "@/components/ui/JobCard";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { ResumeCard } from "@/components/ui/ResumeCard";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { StatCard } from "@/components/ui/StatCard";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type OverviewStats = {
  applications_total: number;
  submitted: number;
  interviewing: number;
};

type CopilotStats = {
  session_count: number;
};

type SearchJob = {
  title: string;
  company: string;
  remote?: boolean;
  location_city?: string;
  location_state?: string;
  location_country?: string;
  salary_min?: number;
  salary_max?: number;
  tags?: string[];
  sponsorship_score?: number;
};
type SearchResponse = { items?: SearchJob[] };

export function DashboardScreen() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const [overview, setOverview] = useState<OverviewStats>({ applications_total: 0, submitted: 0, interviewing: 0 });
  const [copilot, setCopilot] = useState<CopilotStats>({ session_count: 0 });
  const [topJobs, setTopJobs] = useState<SearchJob[]>([]);

  useEffect(() => {
    if (!token) return;
    const query = new URLSearchParams({
      q: "",
      page: "1",
      page_size: "2",
      sort_by: "latest",
      title_match_mode: "fuzzy",
    });

    Promise.all([
      api.getAnalyticsOverview(token).catch(() => ({ applications_total: 0, submitted: 0, interviewing: 0 })),
      api.getAnalyticsCopilot(token).catch(() => ({ session_count: 0 })),
      api.searchJobs(token, query).catch(() => ({ items: [] })),
    ]).then(([overviewRes, copilotRes, jobsRes]) => {
      setOverview({
        applications_total: Number((overviewRes as OverviewStats)?.applications_total || 0),
        submitted: Number((overviewRes as OverviewStats)?.submitted || 0),
        interviewing: Number((overviewRes as OverviewStats)?.interviewing || 0),
      });
      setCopilot({ session_count: Number((copilotRes as CopilotStats)?.session_count || 0) });
      const items = (jobsRes as SearchResponse)?.items;
      setTopJobs(Array.isArray(items) ? items.slice(0, 2) : []);
    });
  }, [token]);

  const displayName = useMemo(() => {
    const full = user?.full_name?.trim();
    if (!full) return "there";
    return full.split(" ")[0];
  }, [user?.full_name]);

  const qualifyMatches = topJobs.length;

  return (
    <div className="space-y-7">
      <PageHeader
        title={`Good afternoon, ${displayName}`}
        subtitle="Live dashboard metrics from your account activity and current job feed."
      />

      <Grid className="grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Qualified Matches" value={String(qualifyMatches)} Icon={BriefcaseBusiness} />
        <StatCard label="Applications Total" value={String(overview.applications_total)} Icon={FileCheck2} iconTone="var(--color-success-soft)" iconColor="var(--color-success)" />
        <StatCard label="Applications Sent" value={String(overview.submitted)} Icon={Send} iconTone="var(--color-warning-soft)" iconColor="var(--color-warning)" />
        <StatCard label="Copilot Sessions" value={String(copilot.session_count)} Icon={Sparkles} iconTone="var(--color-purple-soft)" iconColor="var(--color-purple)" />
      </Grid>

      <div className="grid gap-[18px] xl:grid-cols-[1fr_340px]">
        <div className="space-y-3">
          {topJobs.map((job, idx) => {
            const location = [job.location_city, job.location_state, job.location_country].filter(Boolean).join(", ") || "Location not specified";
            const salary =
              typeof job.salary_min === "number" || typeof job.salary_max === "number"
                ? `$${Math.round(Number(job.salary_min || 0) / 1000)}k - $${Math.round(Number(job.salary_max || 0) / 1000)}k`
                : "Salary not listed";
            return (
              <JobCard
                key={`${job.company}-${job.title}-${idx}`}
                title={job.title}
                company={job.company}
                location={location}
                remote={Boolean(job.remote)}
                salary={salary}
                score={Math.round(Number(job.sponsorship_score || 0) * 100)}
                tags={(job.tags || []).slice(0, 3)}
                isNew={idx === 0}
              />
            );
          })}

          <GlassCard padding="md">
            <h2 className="display-sm">Copilot Conversation</h2>
            <div className="mt-3 space-y-2">
              <ChatBubble role="user" text="Tailor my resume for backend platform roles and keep it impact-focused." />
              <ChatBubble role="ai" text="Use this page's live stats to prioritize applications and then open Copilot for tailored bullet rewrites." />
              <ChatBubble role="ai" typing />
            </div>
          </GlassCard>
        </div>

        <div className="space-y-3">
          <GlassCard padding="md">
            <h3 className="display-sm mb-3">Resume Health</h3>
            <div className="mb-4 flex justify-center">
              <ScoreRing score={0} size="xl" label="overall" />
            </div>
            <div className="space-y-2.5">
              <ProgressBar label="ATS readiness" value={0} variant="semantic" />
              <ProgressBar label="Action verbs" value={0} variant="semantic" />
              <ProgressBar label="Keyword alignment" value={0} variant="semantic" />
              <ProgressBar label="Impact metrics" value={0} variant="semantic" />
              <ProgressBar label="Format clarity" value={0} variant="semantic" />
            </div>
          </GlassCard>

          <ResumeCard
            name="Upload a resume to compute health metrics"
            updated="Not available"
            status="active"
            overall={0}
            ats={0}
          />
        </div>
      </div>
    </div>
  );
}
