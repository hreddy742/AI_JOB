"use client";

import { Download, Sparkles } from "lucide-react";
import { useState } from "react";

import Button from "@/components/premium/ui/Button";
import Card, { CardDescription, CardTitle } from "@/components/premium/ui/Card";
import { Textarea } from "@/components/premium/ui/Input";

export default function TailoredResumeEditor({ jobDescription, beforeText, afterText }) {
  const [editable, setEditable] = useState(afterText);

  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_1.2fr]">
      <Card>
        <CardTitle className="mb-2">Selected Job Description</CardTitle>
        <pre className="whitespace-pre-wrap text-sm text-muted">{jobDescription}</pre>
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Tailored Resume Preview</CardTitle>
          <div className="flex gap-2">
            <Button variant="secondary">
              <Sparkles className="h-4 w-4" /> Explain Changes
            </Button>
            <Button>
              <Download className="h-4 w-4" /> Export PDF
            </Button>
          </div>
        </div>
        <CardDescription className="mb-2">Diff view with inline editing.</CardDescription>
        <div className="grid gap-2 md:grid-cols-2">
          <div className="rounded-md border border-border bg-slate-100/50 p-2 text-sm dark:bg-slate-800/40">
            <p className="mb-1 text-xs font-semibold uppercase text-muted">Before</p>
            <pre className="whitespace-pre-wrap">{beforeText}</pre>
          </div>
          <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-2 text-sm">
            <p className="mb-1 text-xs font-semibold uppercase text-emerald-600">After</p>
            <Textarea value={editable} onChange={(e) => setEditable(e.target.value)} className="min-h-56 bg-white/80 dark:bg-slate-900/70" />
          </div>
        </div>
      </Card>
    </div>
  );
}
