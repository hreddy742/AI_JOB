"use client";

import { useEffect, useState } from "react";
import { ReferralCard } from "@/components/referral-card";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function ReferralsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [jobId, setJobId] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => { if (token) api.listReferrals(token).then((r: any) => setRows(r || [])); }, [token]);

  useEffect(() => {
    if (!token || !taskId) return;
    const timer = setInterval(async () => {
      const s = await api.getReferralTask(token, taskId) as any;
      if (s.status === "completed") {
        clearInterval(timer);
        const latest = await api.listReferrals(token) as any[];
        setRows(latest || []);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [token, taskId]);

  return (
    <div className="space-y-3">
      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        Contacts are auto-discovered from public sources. All email addresses are inferred and unverified. Always confirm contact details before reaching out.
      </div>
      <div className="flex gap-2">
        <input className="rounded border px-3 py-2" placeholder="Job ID" value={jobId} onChange={(e) => setJobId(e.target.value)} />
        <button className="rounded bg-slate-900 px-3 py-2 text-white" onClick={async () => {
          if (!token || !jobId) return;
          const r = await api.discoverReferrals(token, jobId) as { task_id: string };
          setTaskId(r.task_id);
        }}>Discover Referrals</button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((r) => <ReferralCard key={r.id} item={r} onConvert={() => token && api.convertReferral(token, r.id)} onDismiss={() => token && fetch(`/backend/referrals/${r.id}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ status: "dismissed" }) })} />)}
      </div>
    </div>
  );
}
