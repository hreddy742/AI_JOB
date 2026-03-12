"use client";

import { type ChangeEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useAuthStore } from "@/lib/store/auth-store";
import { api } from "@/lib/api-client";

type IngestionHealthSource = {
  source: string;
  active_jobs: number;
  runs_24h: number;
  new_jobs_24h: number;
  minutes_since_last_run: number | null;
  stale: boolean;
};

type RerankSummary = {
  attempts: number;
  applied: number;
  timeout: number;
  failed: number;
  apply_rate: number;
  timeout_rate: number;
  average_latency_ms: number;
};

type RerankStatusPayload = {
  summary?: Partial<RerankSummary>;
};

type RerankReadinessPayload = {
  ready_to_enable_reranking: boolean;
  reasons?: string[];
};

type RerankConfigPayload = {
  default_enabled?: boolean;
  tenant_override?: boolean | null;
  effective_enabled?: boolean;
};

type AlertsStatusPayload = {
  counts?: { ready?: number; pending?: number; failed_dlq?: number };
};

export default function SettingsPage() {
  const STORAGE_KEY = "apex-settings-preferences";
  const token = useAuthStore((s) => s.accessToken);
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("America/Chicago");
  const [alerts, setAlerts] = useState(true);
  const [autoTailor, setAutoTailor] = useState(false);
  const [alertBudget, setAlertBudget] = useState("10");
  const [matchSensitivity, setMatchSensitivity] = useState("balanced");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [health, setHealth] = useState<IngestionHealthSource[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [rerankStatus, setRerankStatus] = useState<Partial<RerankSummary> | null>(null);
  const [rerankReadiness, setRerankReadiness] = useState<RerankReadinessPayload | null>(null);
  const [rerankConfig, setRerankConfig] = useState<RerankConfigPayload | null>(null);
  const [rerankLoading, setRerankLoading] = useState(false);
  const [rerankSaving, setRerankSaving] = useState(false);
  const [rerankError, setRerankError] = useState<string | null>(null);
  const [alertsStatus, setAlertsStatus] = useState<AlertsStatusPayload | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [martsRefreshing, setMartsRefreshing] = useState(false);
  const [martsMessage, setMartsMessage] = useState<string | null>(null);

  // Load name from real profile on mount
  useEffect(() => {
    if (!token) return;
    api.getProfile(token).then((p: any) => {
      const full = [p?.first_name, p?.last_name].filter(Boolean).join(" ");
      if (full) setName(full);
      if (typeof p?.alerts_active === "boolean") setAlerts(p.alerts_active);
      if (p?.alert_budget_per_day) setAlertBudget(String(p.alert_budget_per_day));
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadIngestionHealth() {
    if (!token) return;
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = (await api.getIngestionHealth(token)) as { sources?: IngestionHealthSource[] };
      setHealth(data.sources || []);
    } catch (err) {
      setHealth([]);
      const msg = err instanceof Error ? err.message : "Failed to load ingestion health";
      setHealthError(msg.includes("403") || msg.toLowerCase().includes("admin") ? "admin_only" : msg);
    } finally {
      setHealthLoading(false);
    }
  }

  async function loadRerankHealth() {
    if (!token) return;
    setRerankLoading(true);
    setRerankError(null);
    try {
      const [statusRes, readinessRes, configRes] = await Promise.all([
        api.getRerankStatus(token, 7) as Promise<RerankStatusPayload>,
        api.getRerankReadiness(token, {
          days: 7,
          min_attempts: 100,
          max_timeout_rate: 0.05,
          max_failure_rate: 0.02,
          max_average_latency_ms: 800,
        }) as Promise<RerankReadinessPayload>,
        api.getRerankConfig(token) as Promise<RerankConfigPayload>,
      ]);
      setRerankStatus(statusRes.summary || null);
      setRerankReadiness(readinessRes);
      setRerankConfig(configRes);
    } catch (err) {
      setRerankStatus(null);
      setRerankReadiness(null);
      setRerankConfig(null);
      const msg = err instanceof Error ? err.message : "Failed to load rerank health";
      setRerankError(msg.includes("403") || msg.toLowerCase().includes("admin") ? "admin_only" : msg);
    } finally {
      setRerankLoading(false);
    }
  }

  async function setRerankOverride(enabled: boolean | null) {
    if (!token) return;
    setRerankSaving(true);
    try {
      const state = (await api.updateRerankConfig(token, enabled)) as RerankConfigPayload;
      setRerankConfig(state);
      await loadRerankHealth();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update rerank setting";
      setRerankError(msg);
    } finally {
      setRerankSaving(false);
    }
  }

  async function loadAlertsStatus() {
    if (!token) return;
    setAlertsLoading(true);
    setAlertsError(null);
    try {
      const data = (await api.getAlertsStatus(token)) as AlertsStatusPayload;
      setAlertsStatus(data);
    } catch (err) {
      setAlertsStatus(null);
      const msg = err instanceof Error ? err.message : "Failed to load alert delivery status";
      setAlertsError(msg.includes("403") || msg.toLowerCase().includes("admin") ? "admin_only" : msg);
    } finally {
      setAlertsLoading(false);
    }
  }

  async function refreshAnalyticsMarts() {
    if (!token) return;
    setMartsRefreshing(true);
    setMartsMessage(null);
    try {
      await api.refreshAnalyticsMarts(token);
      setMartsMessage("Analytics marts refreshed.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to refresh analytics marts";
      setMartsMessage(msg);
    } finally {
      setMartsRefreshing(false);
    }
  }

  useEffect(() => {
    void loadIngestionHealth();
    void loadRerankHealth();
    void loadAlertsStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        timezone?: string;
        autoTailor?: boolean;
        matchSensitivity?: string;
      };
      if (typeof parsed.timezone === "string") setTimezone(parsed.timezone);
      if (typeof parsed.autoTailor === "boolean") setAutoTailor(parsed.autoTailor);
      if (typeof parsed.matchSensitivity === "string") setMatchSensitivity(parsed.matchSensitivity);
    } catch {
      // Ignore malformed local settings and fall back to defaults.
    }
  }, []);

  async function saveSettings(): Promise<void> {
    setSaveState("saving");
    setSaveMessage(null);
    try {
      if (token) {
        const budgetValue = alertBudget === "unlimited" ? 100000 : Number.parseInt(alertBudget, 10);
        const nameParts = name.trim().split(/\s+/).filter(Boolean);
        await api.patchProfile(token, {
          first_name: nameParts[0] || "",
          last_name: nameParts.slice(1).join(" ") || "",
          alerts_active: alerts,
          alert_budget_per_day: Number.isFinite(budgetValue) ? budgetValue : 10,
        });
      }
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          timezone,
          autoTailor,
          matchSensitivity,
          updatedAt: new Date().toISOString(),
        })
      );
      setSaveState("saved");
      setSaveMessage("Profile and alerts saved to your account. Device preferences saved locally.");
    } catch {
      setSaveState("error");
      setSaveMessage("Could not save settings. Please try again.");
    }
  }

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
        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">Name is account-level. Timezone is saved only on this device.</p>
      </Card>
      <Card>
        <CardTitle className="mb-2">Automation Controls</CardTitle>
        <CardDescription className="mb-2">Tune how proactive Jobright AI Copilot should be when opportunities arrive.</CardDescription>
        <label className="mb-2 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={alerts} onChange={(e) => setAlerts(e.target.checked)} />
          Instant notifications for high-match jobs
        </label>
        <div className="mb-2 grid gap-2 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-xs text-[var(--color-text-secondary)]">Max alerts per day</p>
            <Select value={alertBudget} onChange={(e: ChangeEvent<HTMLSelectElement>) => setAlertBudget(e.target.value)}>
              <option value="3">3</option>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="unlimited">Unlimited</option>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-xs text-[var(--color-text-secondary)]">Match sensitivity</p>
            <Select value={matchSensitivity} onChange={(e: ChangeEvent<HTMLSelectElement>) => setMatchSensitivity(e.target.value)}>
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </Select>
          </div>
        </div>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoTailor} onChange={(e) => setAutoTailor(e.target.checked)} />
          Auto-generate resume tailoring suggestions
        </label>
        <p className="mb-3 text-xs text-[var(--color-text-secondary)]">Alert settings are account-level. Match sensitivity and auto-tailor preference are saved on this device.</p>
        <Button onClick={() => void saveSettings()} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving..." : "Save Settings"}
        </Button>
        {saveMessage ? <p className={saveState === "error" ? "mt-2 text-xs text-red-600" : "mt-2 text-xs text-emerald-600"}>{saveMessage}</p> : null}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between gap-2">
          <CardTitle>Ingestion Health (Admin)</CardTitle>
          <Button variant="secondary" onClick={() => void loadIngestionHealth()} disabled={healthLoading}>
            {healthLoading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        {healthError === "admin_only" ? (
          <p className="text-xs text-[var(--color-text-secondary)]">Admin access required to view ingestion health.</p>
        ) : healthError ? (
          <div className="mb-2 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">{healthError}</div>
        ) : null}
        {healthError !== "admin_only" && (
          <div className="overflow-auto rounded border border-[var(--color-border-sub)]">
            <table className="w-full min-w-[680px] text-left text-xs">
              <thead className="bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]">
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
                  <tr key={row.source} className="border-t border-[var(--color-border-sub)]">
                    <td className="px-3 py-2 text-[var(--color-text-primary)]">{row.source}</td>
                    <td className="px-3 py-2 text-[var(--color-text-primary)]">{row.active_jobs}</td>
                    <td className="px-3 py-2 text-[var(--color-text-primary)]">{row.runs_24h}</td>
                    <td className="px-3 py-2 text-[var(--color-text-primary)]">{row.new_jobs_24h}</td>
                    <td className="px-3 py-2 text-[var(--color-text-primary)]">{row.minutes_since_last_run ?? "-"}</td>
                    <td className="px-3 py-2">
                      <span className={row.stale ? "text-amber-600" : "text-emerald-600"}>
                        {row.stale ? "stale" : "healthy"}
                      </span>
                    </td>
                  </tr>
                ))}
                {!healthLoading && health.length === 0 && !healthError ? (
                  <tr className="border-t border-[var(--color-border-sub)]">
                    <td className="px-3 py-3 text-[var(--color-text-muted)]" colSpan={6}>
                      No health records yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between gap-2">
          <CardTitle>Rerank Rollout Health (Admin)</CardTitle>
          <Button variant="secondary" onClick={() => void loadRerankHealth()} disabled={rerankLoading}>
            {rerankLoading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        {rerankError === "admin_only" ? (
          <p className="text-xs text-[var(--color-text-secondary)]">Admin access required to view rerank health.</p>
        ) : rerankError ? (
          <div className="mb-2 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">{rerankError}</div>
        ) : null}
        {rerankError !== "admin_only" && (
          <div className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded border border-[var(--color-border-sub)] p-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Attempts (7d)</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">{rerankStatus?.attempts ?? 0}</p>
              </div>
              <div className="rounded border border-[var(--color-border-sub)] p-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Apply Rate</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {Math.round(Number(rerankStatus?.apply_rate ?? 0) * 100)}%
                </p>
              </div>
              <div className="rounded border border-[var(--color-border-sub)] p-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Timeout Rate</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {Math.round(Number(rerankStatus?.timeout_rate ?? 0) * 100)}%
                </p>
              </div>
              <div className="rounded border border-[var(--color-border-sub)] p-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Avg Latency</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {Math.round(Number(rerankStatus?.average_latency_ms ?? 0))} ms
                </p>
              </div>
            </div>
            <div className="rounded border border-[var(--color-border-sub)] p-2 text-xs">
              <span
                className={
                  rerankReadiness?.ready_to_enable_reranking ? "font-semibold text-emerald-600" : "font-semibold text-amber-600"
                }
              >
                {rerankReadiness?.ready_to_enable_reranking ? "Ready to enable reranking" : "Not ready to enable reranking"}
              </span>
              {rerankConfig && (
                <p className="mt-1 text-[var(--color-text-secondary)]">
                  Effective flag: {rerankConfig.effective_enabled ? "enabled" : "disabled"} | Override:{" "}
                  {rerankConfig.tenant_override === null || rerankConfig.tenant_override === undefined
                    ? "none"
                    : rerankConfig.tenant_override
                    ? "enabled"
                    : "disabled"}
                </p>
              )}
              {rerankReadiness?.reasons && rerankReadiness.reasons.length > 0 && (
                <p className="mt-1 text-[var(--color-text-secondary)]">
                  Blocking reasons: {rerankReadiness.reasons.join(", ")}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={rerankSaving || !rerankReadiness?.ready_to_enable_reranking}
                  onClick={() => void setRerankOverride(true)}
                >
                  {rerankSaving ? "Saving..." : "Enable Override"}
                </Button>
                <Button variant="secondary" disabled={rerankSaving} onClick={() => void setRerankOverride(false)}>
                  Disable Override
                </Button>
                <Button variant="secondary" disabled={rerankSaving} onClick={() => void setRerankOverride(null)}>
                  Clear Override
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between gap-2">
          <CardTitle>Alert Delivery Status (Admin)</CardTitle>
          <Button variant="secondary" onClick={() => void loadAlertsStatus()} disabled={alertsLoading}>
            {alertsLoading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        {alertsError === "admin_only" ? (
          <p className="text-xs text-[var(--color-text-secondary)]">Admin access required to view alert delivery status.</p>
        ) : alertsError ? (
          <div className="mb-2 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700">{alertsError}</div>
        ) : null}
        {alertsError !== "admin_only" && (
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded border border-[var(--color-border-sub)] p-2">
              <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Ready</p>
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{alertsStatus?.counts?.ready ?? 0}</p>
            </div>
            <div className="rounded border border-[var(--color-border-sub)] p-2">
              <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Pending</p>
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{alertsStatus?.counts?.pending ?? 0}</p>
            </div>
            <div className="rounded border border-[var(--color-border-sub)] p-2">
              <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-secondary)]">Failed DLQ</p>
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{alertsStatus?.counts?.failed_dlq ?? 0}</p>
            </div>
          </div>
        )}
      </Card>
      <Card>
        <div className="mb-2 flex items-center justify-between gap-2">
          <CardTitle>Analytics Marts (Admin)</CardTitle>
          <Button variant="secondary" onClick={() => void refreshAnalyticsMarts()} disabled={martsRefreshing}>
            {martsRefreshing ? "Refreshing..." : "Refresh Marts"}
          </Button>
        </div>
        <p className="text-xs text-[var(--color-text-secondary)]">
          Refreshes materialized views used by analytics endpoints for faster dashboards.
        </p>
        {martsMessage ? <p className="mt-2 text-xs text-[var(--color-text-primary)]">{martsMessage}</p> : null}
      </Card>
    </div>
  );
}
