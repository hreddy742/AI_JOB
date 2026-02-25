"use client";

import { type ChangeEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useAuthStore } from "@/lib/store/auth-store";

type IngestionHealthSource = {
  source: string;
  active_jobs: number;
  runs_24h: number;
  new_jobs_24h: number;
  minutes_since_last_run: number | null;
  stale: boolean;
};

export default function SettingsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [name, setName] = useState("Harsha Reddy");
  const [timezone, setTimezone] = useState("America/Chicago");
  const [alerts, setAlerts] = useState(true);
  const [autoTailor, setAutoTailor] = useState(false);
  const [health, setHealth] = useState<IngestionHealthSource[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  async function loadIngestionHealth() {
    if (!token) return;
    setHealthLoading(true);
    setHealthError(null);
    try {
      const res = await fetch("/backend/admin/ingestion/health", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { sources?: IngestionHealthSource[] };
      setHealth(data.sources || []);
    } catch (err) {
      setHealth([]);
      setHealthError(err instanceof Error ? err.message : "Failed to load ingestion health");
    } finally {
      setHealthLoading(false);
    }
  }

  useEffect(() => {
    void loadIngestionHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Settings</h1>
      <Card>
        <CardTitle className="mb-2">Profile Preferences</CardTitle>
        <div className="grid gap-2 sm:grid-cols-2">
          <Input value={name} onChange={(e: ChangeEvent<HTMLInputElement>) => setName(e.target.value)} placeholder="Full name" />
          <Select value={timezone} onChange={(e: ChangeEvent<HTMLSelectElement>) => setTimezone(e.target.value)}>
            <option>America/Chicago</option>
            <option>America/New_York</option>
            <option>America/Los_Angeles</option>
          </Select>
        </div>
      </Card>
      <Card>
        <CardTitle className="mb-2">Automation Controls</CardTitle>
        <CardDescription className="mb-2">Tune how proactive Jobright AI Copilot should be when opportunities arrive.</CardDescription>
        <label className="mb-2 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={alerts} onChange={(e) => setAlerts(e.target.checked)} />
          Instant notifications for high-match jobs
        </label>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoTailor} onChange={(e) => setAutoTailor(e.target.checked)} />
          Auto-generate resume tailoring suggestions
        </label>
        <Button>Save Settings</Button>
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between gap-2">
          <CardTitle>Ingestion Health (Admin)</CardTitle>
          <Button variant="secondary" onClick={() => void loadIngestionHealth()} disabled={healthLoading}>
            {healthLoading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        {healthError ? <div className="mb-2 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-200">{healthError}</div> : null}
        <div className="overflow-auto rounded border border-white/10">
          <table className="w-full min-w-[680px] text-left text-xs">
            <thead className="bg-white/5 text-slate-300">
              <tr>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Active Jobs</th>
                <th className="px-3 py-2">Runs (24h)</th>
                <th className="px-3 py-2">New (24h)</th>
                <th className="px-3 py-2">Minutes Since Run</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {health.map((row) => (
                <tr key={row.source} className="border-t border-white/5">
                  <td className="px-3 py-2">{row.source}</td>
                  <td className="px-3 py-2">{row.active_jobs}</td>
                  <td className="px-3 py-2">{row.runs_24h}</td>
                  <td className="px-3 py-2">{row.new_jobs_24h}</td>
                  <td className="px-3 py-2">{row.minutes_since_last_run ?? "-"}</td>
                  <td className="px-3 py-2">{row.stale ? "stale" : "healthy"}</td>
                </tr>
              ))}
              {!healthLoading && health.length === 0 && !healthError ? (
                <tr className="border-t border-white/5">
                  <td className="px-3 py-3 text-slate-400" colSpan={6}>
                    No health records yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
