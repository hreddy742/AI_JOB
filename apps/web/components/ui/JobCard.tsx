"use client";

import { Bookmark } from "lucide-react";

import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import { Button } from "./button";
import { GlassCard } from "./GlassCard";

export function JobCard({
  title,
  company,
  location,
  remote,
  salary,
  score,
  tags,
  isNew
}: {
  title: string;
  company: string;
  location: string;
  remote?: boolean;
  salary: string;
  score: number;
  tags: string[];
  isNew?: boolean;
}) {
  const scoreColor = score >= 90 ? "var(--color-success)" : score >= 75 ? "var(--color-accent)" : score >= 50 ? "var(--color-warning)" : "var(--color-error)";
  const scoreBg = score >= 90 ? "var(--color-success-soft)" : score >= 75 ? "var(--color-accent-soft)" : score >= 50 ? "var(--color-warning-soft)" : "var(--color-error-soft)";

  return (
    <GlassCard variant="interactive" padding="sm" className="group">
      <button aria-label="Bookmark job" className="absolute right-3 top-3 hidden rounded-full p-1 text-[var(--color-text-muted)] transition hover:bg-[rgba(0,0,0,0.05)] group-hover:inline-flex">
        <Bookmark size={14} />
      </button>
      <div className="flex items-start gap-3">
        <Avatar name={company} size="lg" company />
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <h3 className="truncate text-[14.5px] font-medium text-[var(--color-text-primary)]">{title}</h3>
            {isNew ? <Badge variant="blue" size="xs" showDot>NEW</Badge> : null}
          </div>
          <p className="body-sm mt-0.5">
            {company} · {location} {remote ? <Badge variant="purple" size="xs">Remote</Badge> : null}
          </p>
        </div>
        <div className="rounded-[var(--radius-md)] px-2.5 py-1.5 text-center" style={{ background: scoreBg }}>
          <p className="text-base" style={{ fontFamily: "var(--font-display)", color: scoreColor }}>{score}%</p>
          <p className="text-[10px] text-[var(--color-text-muted)]">match</p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <Badge key={tag} size="xs">{tag}</Badge>
          ))}
        </div>
        <p className="text-[12.5px] font-medium text-[var(--color-text-secondary)]">{salary}</p>
      </div>

      <div className="pointer-events-none mt-2 flex justify-end opacity-0 transition duration-200 group-hover:opacity-100">
        <Button size="sm" className="pointer-events-auto">Quick apply</Button>
      </div>
    </GlassCard>
  );
}
