"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function ApplicationDetailPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const [audit, setAudit] = useState<any>(null);

  useEffect(() => {
    if (!token) return;
    fetch(`/backend/applications/${params.id}/audit`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setAudit)
      .catch(() => setAudit({ application_id: params.id, automation_log: [] }));
  }, [token, params.id]);

  return (
    <div>
      <h1 className="text-xl font-bold">Application Audit</h1>
      <pre className="mt-2 whitespace-pre-wrap text-xs">{JSON.stringify(audit, null, 2)}</pre>
    </div>
  );
}
