"use client";

import { useEffect, useState } from "react";
import { OutreachCrmTable } from "@/components/outreach-crm-table";
import { useAuthStore } from "@/lib/store/auth-store";

export default function OutreachPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      fetch("/backend/contacts", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()),
      fetch("/backend/outreach", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()),
    ]).then(([contacts, outreach]) => {
      setRows((outreach || []).map((o: any) => ({ id: o.id, name: contacts.find((c: any) => c.id === o.contact_id)?.name || "Unknown", company: contacts.find((c: any) => c.id === o.contact_id)?.company || "", status: o.status })));
    });
  }, [token]);

  return <OutreachCrmTable rows={rows} />;
}
