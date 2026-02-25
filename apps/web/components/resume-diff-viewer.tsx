"use client";

type DiffLogEntry = {
  type: string;
  section: string;
  original: string;
  tailored: string;
  jd_keyword_match: string[];
  confidence: number;
};

type ResumeDiffViewerProps = {
  originalText: string;
  tailoredText: string;
  diffLog: DiffLogEntry[];
};

export function ResumeDiffViewer({ originalText, tailoredText, diffLog }: ResumeDiffViewerProps) {
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <section className="rounded-xl border border-slate-200 bg-white p-3">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Original</h3>
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap text-xs text-slate-700">{originalText}</pre>
      </section>

      <section className="rounded-xl border border-cyan-200 bg-cyan-50/40 p-3">
        <h3 className="mb-2 text-sm font-semibold text-cyan-800">Tailored</h3>
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap text-xs text-slate-800">{tailoredText}</pre>
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50/40 p-3">
        <h3 className="mb-2 text-sm font-semibold text-amber-800">Diff Log</h3>
        <div className="max-h-[520px] space-y-2 overflow-auto">
          {diffLog.length === 0 ? (
            <p className="text-xs text-slate-500">No diff entries yet.</p>
          ) : (
            diffLog.map((entry, idx) => (
              <article key={`${entry.section}-${idx}`} className="rounded border border-amber-200 bg-white p-2">
                <p className="text-xs font-semibold text-slate-700">{entry.type} | {entry.section}</p>
                <p className="mt-1 text-xs text-slate-600">Confidence: {entry.confidence}</p>
                <p className="mt-1 text-xs text-slate-700">Original: {entry.original}</p>
                <p className="mt-1 text-xs text-slate-700">Tailored: {entry.tailored}</p>
                {entry.jd_keyword_match?.length ? (
                  <p className="mt-1 text-xs text-cyan-700">Keywords: {entry.jd_keyword_match.join(", ")}</p>
                ) : null}
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
