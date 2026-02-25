"use client";

export const dynamic = "force-dynamic";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api-client";

function strength(password: string): number {
  return [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
    /[!@#$%^&*()_+\-=\[\]{}|;':\",.<>?/\\]/.test(password),
  ].filter(Boolean).length;
}

function ResetPasswordContent() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    if (!token) router.replace("/auth/forgot-password");
  }, [token, router]);

  useEffect(() => {
    if (!done) return;
    if (countdown <= 0) {
      router.replace("/auth/login");
      return;
    }
    const t = setTimeout(() => setCountdown((v) => v - 1), 1000);
    return () => clearTimeout(t);
  }, [done, countdown, router]);

  const score = useMemo(() => strength(password), [password]);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!token) return;
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch {
      setError("This link is invalid or expired");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return <div className="rounded-xl border border-emerald-700 bg-emerald-900/30 p-6">?? Password updated! All other devices have been signed out. Redirecting in {countdown}s...</div>;
  }

  return (
    <form className="w-full max-w-md space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-6" onSubmit={onSubmit}>
      <h1 className="text-2xl font-semibold">Set new password</h1>
      <div className="relative">
        <input className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 pr-14" type={show ? "text" : "password"} placeholder="New Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-xs" onClick={() => setShow((v) => !v)}>{show ? "Hide" : "Show"}</button>
      </div>
      <div className="grid grid-cols-5 gap-1">{[0,1,2,3,4].map((i) => <div key={i} className={`h-2 rounded ${score > i ? "bg-emerald-400" : "bg-slate-700"}`} />)}</div>
      <input className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2" type="password" placeholder="Confirm Password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
      {error ? <div className="rounded-md bg-red-500/20 p-2 text-sm text-red-200">{error}</div> : null}
      <button className="w-full rounded-md bg-blue-600 px-3 py-2" disabled={loading}>{loading ? "Updating..." : "Update Password"}</button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="rounded-xl border border-slate-800 bg-slate-900 p-6">Loading...</div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}
