"use client";

export function ReferralCard({ item, onConvert, onDismiss }: { item: { id: string; contact_name?: string; company: string; contact_title?: string; inferred_email?: string; confidence_score?: number; contact_source?: string }; onConvert: () => void; onDismiss: () => void }) {
  return (
    <article className="rounded-xl border p-3">
      <h3 className="font-semibold">{item.contact_name || "Unknown"}</h3>
      <p className="text-sm text-slate-600">{item.company}</p>
      <p className="text-xs text-slate-500">Bio hint - not verified: {item.contact_title || "N/A"}</p>
      <p className="text-xs text-amber-700">Inferred - verify before sending: {item.inferred_email || "N/A"}</p>
      <p className="mt-1 text-xs">Confidence: {Math.round((item.confidence_score || 0) * 100)}%</p>
      <div className="mt-2 flex gap-2">
        <button className="rounded bg-cyan-700 px-2 py-1 text-xs text-white" onClick={onConvert}>Add to CRM</button>
        <button className="rounded bg-slate-200 px-2 py-1 text-xs" onClick={onDismiss}>Dismiss</button>
      </div>
    </article>
  );
}
