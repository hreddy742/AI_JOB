"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function ProfilePage() {
  const token = useAuthStore((s) => s.accessToken);
  const [form, setForm] = useState<any>({ first_name: "", last_name: "", target_roles: [], target_locations: [], work_authorization: "other" });

  useEffect(() => { if (token) api.getProfile(token).then(setForm).catch(() => undefined); }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    await api.upsertProfile(token, form);
    alert("Profile saved");
  }

  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      <div className="rounded border border-cyan-200 bg-cyan-50 p-3 text-sm">This information is used to auto-fill job applications. Keep it accurate.</div>
      <div className="grid gap-2 md:grid-cols-2">
        <input className="rounded border p-2" placeholder="First name" value={form.first_name || ""} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
        <input className="rounded border p-2" placeholder="Last name" value={form.last_name || ""} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
        <input className="rounded border p-2" placeholder="Phone" value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <input className="rounded border p-2" placeholder="Location" value={form.current_location || ""} onChange={(e) => setForm({ ...form, current_location: e.target.value })} />
        <input className="rounded border p-2" placeholder="LinkedIn URL" value={form.linkedin_url || ""} onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} />
        <input className="rounded border p-2" placeholder="GitHub URL" value={form.github_url || ""} onChange={(e) => setForm({ ...form, github_url: e.target.value })} />
      </div>
      <textarea className="w-full rounded border p-2" rows={4} placeholder="Bio" value={form.summary_bio || ""} onChange={(e) => setForm({ ...form, summary_bio: e.target.value })} />
      <button className="rounded bg-cyan-700 px-4 py-2 text-white">Save Profile</button>
    </form>
  );
}
