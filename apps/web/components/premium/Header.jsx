"use client";

import { useEffect, useState } from "react";
import { Bell, MoonStar, Sun } from "lucide-react";

import { AIStatusIndicator } from "@/components/ui/ai-status-indicator";
import Button from "@/components/premium/ui/Button";
import { Select } from "@/components/premium/ui/Input";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function Header({ user, mode, onToggleTheme }) {
  const token = useAuthStore((s) => s.accessToken);
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const displayName = user?.full_name || user?.email || "Account";
  const displayEmail = user?.email || "";
  const avatarSeed = user?.full_name || user?.email || "A";

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem("active_resume_id") : null;
    if (stored) setSelectedResumeId(stored);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadResumes() {
      if (!token) return;
      try {
        const items = await api.listResumes(token);
        if (cancelled) return;
        const sorted = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setResumes(sorted);
        if (!selectedResumeId && sorted.length > 0) {
          const nextId = sorted[0].id;
          setSelectedResumeId(nextId);
          if (typeof window !== "undefined") {
            window.localStorage.setItem("active_resume_id", nextId);
            window.dispatchEvent(new CustomEvent("active-resume-changed", { detail: { resumeId: nextId } }));
          }
        }
      } catch {
        if (!cancelled) setResumes([]);
      }
    }
    void loadResumes();
    return () => {
      cancelled = true;
    };
  }, [token, selectedResumeId]);

  return (
    <header className="rounded-xl border border-border bg-card p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs text-muted">Welcome back</p>
          <p className="font-display text-lg font-semibold">{displayName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AIStatusIndicator status="Online" />
          <Select
            className="w-52"
            value={selectedResumeId}
            onChange={(e) => {
              const nextId = e.target.value;
              setSelectedResumeId(nextId);
              if (typeof window !== "undefined") {
                window.localStorage.setItem("active_resume_id", nextId);
                window.dispatchEvent(new CustomEvent("active-resume-changed", { detail: { resumeId: nextId } }));
              }
            }}
          >
            <option value="" disabled>
              Select resume
            </option>
            {resumes.map((resume) => (
              <option key={resume.id} value={resume.id}>
                {resume.label || `Resume v${resume.version}`} ({resume.file_name})
              </option>
            ))}
          </Select>
          <Button variant="secondary" className="p-2">
            <Bell className="h-4 w-4" />
          </Button>
          <Button variant="secondary" className="p-2" onClick={onToggleTheme}>
            {mode === "dark" ? <Sun className="h-4 w-4" /> : <MoonStar className="h-4 w-4" />}
          </Button>
          <div className="flex items-center gap-2 rounded-full border border-border px-2 py-1">
            <div className="h-7 w-7 rounded-full bg-primary/20 text-center text-xs leading-7 text-primary">{avatarSeed[0].toUpperCase()}</div>
            {displayEmail ? <span className="hidden text-sm sm:inline">{displayEmail}</span> : null}
          </div>
        </div>
      </div>
    </header>
  );
}
