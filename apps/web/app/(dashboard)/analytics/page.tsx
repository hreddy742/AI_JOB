"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store/auth-store";

export default function AnalyticsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [overview, setOverview] = useState<any>(null);
  const [copilot, setCopilot] = useState<any>(null);
  const [referrals, setReferrals] = useState<any>(null);

  useEffect(() => {
    if (!token) return;
    fetch("/backend/analytics/overview", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()).then(setOverview);
    fetch("/backend/analytics/copilot", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()).then(setCopilot);
    fetch("/backend/analytics/referrals", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()).then(setReferrals);
  }, [token]);

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <pre className="rounded border p-3 text-xs">{JSON.stringify(overview, null, 2)}</pre>
      <pre className="rounded border p-3 text-xs">{JSON.stringify(copilot, null, 2)}</pre>
      <pre className="rounded border p-3 text-xs">{JSON.stringify(referrals, null, 2)}</pre>
    </div>
  );
}
