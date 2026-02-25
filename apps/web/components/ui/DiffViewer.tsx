"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Badge } from "./Badge";
import { GlassCard } from "./GlassCard";

type DiffLine = {
  type: "added" | "removed" | "unchanged";
  text: string;
};

type DiffLog = {
  section: string;
  changeType: "added" | "removed" | "updated";
  before: string;
  after: string;
  keywords: string;
};

export function DiffViewer({
  original,
  tailored,
  logs
}: {
  original: DiffLine[];
  tailored: DiffLine[];
  logs: DiffLog[];
}) {
  const [open, setOpen] = useState(true);

  const lineClass = (type: DiffLine["type"]): string => {
    if (type === "removed") return "border-l-[3px] border-[var(--color-error)] bg-[rgba(220,38,38,0.08)] text-[var(--color-error)] line-through";
    if (type === "added") return "border-l-[3px] border-[var(--color-success)] bg-[rgba(22,163,74,0.10)] text-[var(--color-success)]";
    return "text-[var(--color-text-primary)]";
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-2">
        <GlassCard padding="sm" className="max-h-[420px] overflow-y-auto">
          <p className="label-md mb-2">Original</p>
          <div className="space-y-1.5">
            {original.map((line, idx) => (
              <p key={`orig-${idx}`} className={`rounded px-2 py-1.5 text-[13px] ${lineClass(line.type)}`}>{line.text}</p>
            ))}
          </div>
        </GlassCard>

        <GlassCard padding="sm" className="max-h-[420px] overflow-y-auto">
          <p className="label-md mb-2">Tailored</p>
          <div className="space-y-1.5">
            {tailored.map((line, idx) => (
              <p key={`tail-${idx}`} className={`rounded px-2 py-1.5 text-[13px] ${lineClass(line.type)}`}>{line.text}</p>
            ))}
          </div>
        </GlassCard>
      </div>

      <GlassCard padding="sm">
        <button type="button" className="flex w-full items-center justify-between" onClick={() => setOpen((v) => !v)}>
          <span className="display-sm">Change Log</span>
          <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open ? (
          <div className="mt-3 space-y-2">
            {logs.map((log, idx) => (
              <div key={`${log.section}-${idx}`} className="rounded-[var(--radius-md)] border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.5)] p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant="purple" size="xs">{log.section}</Badge>
                  <Badge variant={log.changeType === "added" ? "green" : log.changeType === "removed" ? "red" : "amber"} size="xs">{log.changeType}</Badge>
                </div>
                <p className="body-xs">{log.before} ? {log.after}</p>
                <p className="body-xs mt-1">JD keywords matched: {log.keywords}</p>
              </div>
            ))}
          </div>
        ) : null}
      </GlassCard>
    </div>
  );
}
