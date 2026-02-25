"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField, Input, InputWithIcon } from "@/components/ui/input";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";
const DIRECT_API_BASE = process.env.NEXT_PUBLIC_API_DIRECT_URL ?? "http://localhost:8001";

function normalizeAuthError(message: string): string {
  const raw = message.toLowerCase();
  if (raw.includes("internal server error") || raw.includes("request failed: 500")) {
    return "Sign in failed due to a server issue. Please try again in a moment.";
  }
  if (raw.includes("invalid") && raw.includes("credential")) {
    return "Incorrect email or password.";
  }
  if (raw.includes("network") || raw.includes("failed to fetch") || raw.includes("connect")) {
    return "Cannot reach the server right now. Check your connection and try again.";
  }
  return message;
}

function LoginContent() {
  const params = useSearchParams();
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const redirectTo = useMemo(() => params.get("redirect") || "/dashboard", [params]);
  const resolvedApiBase = useMemo(() => {
    if (typeof window === "undefined") return API_BASE;
    if (!API_BASE.startsWith("/")) return API_BASE;
    const host = window.location.hostname.toLowerCase();
    const port = window.location.port;
    if ((host === "localhost" || host === "127.0.0.1") && port === "3001") {
      return DIRECT_API_BASE;
    }
    return API_BASE;
  }, []);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push(redirectTo);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Connection error. Please try again.";
      if (message.includes("email_not_verified") || message.includes("verify your email")) {
        setInfo("Please verify your email before signing in.");
      } else {
        setError(normalizeAuthError(message));
      }
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification(): Promise<void> {
    if (!email || loading) return;
    try {
      await api.resendVerification(email);
      setInfo("Verification email sent if account exists.");
    } catch {
      setError("Could not resend verification email right now.");
    }
  }

  return (
    <div className="w-full max-w-md">
      <div className="apex-glass-card p-6 sm:p-7">
        {params.get("session_expired") === "true" ? (
          <div className="mb-4 rounded-[var(--radius-md)] bg-[var(--color-warning-soft)] p-3 text-sm text-[var(--color-warning)]">
            Your session expired. Please sign in again.
          </div>
        ) : null}

        <p className="label-lg">Welcome Back</p>
        <h1 className="display-lg mt-2">Sign in</h1>
        <p className="body-sm mt-1">Access your job pipeline and AI workspace.</p>

        <a
          href={`${resolvedApiBase}/auth/google`}
          className="mt-4 inline-flex min-h-[38px] w-full items-center justify-center rounded-[10px] border border-[var(--color-border-sub)] bg-[rgba(255,255,255,0.9)] px-4 py-2 text-[13.5px] font-medium text-[var(--color-text-primary)] transition hover:bg-white"
        >
          Continue with Google
        </a>

        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-[var(--color-border-sub)]" />
          <span className="label-sm">or</span>
          <div className="h-px flex-1 bg-[var(--color-border-sub)]" />
        </div>

        <form className="space-y-3" onSubmit={onSubmit}>
          <FormField label="Email">
            <Input type="email" autoFocus placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} disabled={loading} required />
          </FormField>

          <FormField label="Password">
            <InputWithIcon
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              rightAction={
                <button type="button" className="text-xs" onClick={() => setShowPassword((v) => !v)}>
                  {showPassword ? "Hide" : "Show"}
                </button>
              }
              required
            />
          </FormField>

          <div className="text-right text-sm">
            <Link href="/auth/forgot-password" className="text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]">
              Forgot password?
            </Link>
          </div>

          {error ? <div className="rounded-[var(--radius-md)] bg-[var(--color-error-soft)] p-2.5 text-sm text-[var(--color-error)]">{error}</div> : null}

          {info ? (
            <div className="rounded-[var(--radius-md)] bg-[var(--color-accent-soft)] p-2.5 text-sm text-[var(--color-accent)]">
              {info}{" "}
              <button type="button" className="underline" onClick={resendVerification}>
                Resend verification email
              </button>
            </div>
          ) : null}

          <Button className="w-full" loading={loading} disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>

        <p className="body-sm mt-4">
          Don&apos;t have an account?{" "}
          <Link href="/auth/register" className="text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="apex-glass-card p-6">Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
