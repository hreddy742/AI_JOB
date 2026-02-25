import { FileText } from "lucide-react";

import { Badge } from "./Badge";
import { Button } from "./button";
import { GlassCard } from "./GlassCard";
import { ScoreRing } from "./ScoreRing";

export function ResumeCard({
  name,
  updated,
  status,
  overall,
  ats
}: {
  name: string;
  updated: string;
  status: "active" | "draft" | "primary";
  overall: number;
  ats: number;
}) {
  return (
    <GlassCard padding="md" hoverable className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-[260px] flex-1 items-center gap-3">
        <div className="relative h-14 w-12 rounded-[10px] border border-[rgba(37,99,235,0.15)] bg-[linear-gradient(145deg,rgba(219,234,254,0.9),rgba(196,181,253,0.4))] shadow-[0_3px_10px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.9)]">
          <span className="absolute right-0 top-0 h-3 w-3 rounded-bl-md bg-[rgba(37,99,235,0.12)]" />
          <FileText className="mx-auto mt-4 h-4 w-4 text-[var(--color-accent)]" />
        </div>
        <div>
          <p className="text-[14.5px] font-medium">{name}</p>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant={status === "active" ? "green" : status === "draft" ? "amber" : "blue"} size="xs">{status}</Badge>
            <span className="body-xs">Updated {updated}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <ScoreRing score={overall} size="sm" label="Overall" />
        <ScoreRing score={ats} size="sm" label="ATS" />
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm">Tailor</Button>
        <Button size="sm">Review</Button>
      </div>
    </GlassCard>
  );
}
