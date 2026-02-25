"use client";

import Link from "next/link";
import { type FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField, Input, InputWithIcon } from "@/components/ui/input";
import { api } from "@/lib/api-client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

type PasswordChecks = {
  length: boolean;
  upper: boolean;
  lower: boolean;
  digit: boolean;
  special: boolean;
};

function evaluatePassword(password: string): PasswordChecks {
  return {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    digit: /\d/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{}|;':\",.<>?/\\]/.test(password)
  };
}

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const [loading, setLoading] = useState(false);

  const checks = useMemo(() => evaluatePassword(password), [password]);
  const score = Object.values(checks).filter(Boolean).length;

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await api.register({ email, password, full_name: fullName });
      setSuccess(true);
      const timer = setInterval(() => {
        setCooldown((value) => {
          if (value <= 1) {
            clearInterval(timer);
            return 0;
          }
          return value - 1;
        });
      }, 1000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Registration failed";
      setError(message.toLowerCase().includes("internal") ? "Registration failed due to a server issue. Please try again." : message);
    } finally {
      setLoading(false);
    }
  }

  async function resend(): Promise<void> {
    if (cooldown > 0) return;
    try {
      await api.resendVerification(email);
      setCooldown(60);
    } catch {
      setError("Could not resend verification email right now.");
    }
  }

  if (success) {
    return (
      <div className="w-full max-w-lg">
        <div className="apex-glass-card p-6 text-center sm:p-7">
          <p className="label-lg">Email Verification</p>
          <h1 className="display-lg mt-2">Check your inbox</h1>
          <p className="body-sm mt-2">
            We sent a verification link to <span className="font-medium text-[var(--color-accent)]">{email}</span>
          </p>
          <p className="body-xs mt-1">Verification links expire in 24 hours.</p>
          <Button className="mt-4" onClick={resend} disabled={cooldown > 0}>
            {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend email"}
          </Button>
        </div>
      </div>
    );
  }

  const checksView = [
    [checks.length, "8+ characters"],
    [checks.upper, "Uppercase letter"],
    [checks.lower, "Lowercase letter"],
    [checks.digit, "Number"],
    [checks.special, "Special character"]
  ] as const;

  return (
    <div className="w-full max-w-lg">
      <div className="apex-glass-card p-6 sm:p-7">
        <p className="label-lg">Create Account</p>
        <h1 className="display-lg mt-2">Join Apex Apply</h1>
        <p className="body-sm mt-1">Set up your profile and start AI-assisted job execution.</p>

        <a
          href={`${API_BASE}/auth/google`}
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
          <FormField label="Full Name">
            <Input placeholder="Your name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </FormField>

          <FormField label="Email">
            <Input type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </FormField>

          <FormField label="Password">
            <InputWithIcon
              type={showPassword ? "text" : "password"}
              placeholder="Create password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              rightAction={
                <button type="button" className="text-xs" onClick={() => setShowPassword((v) => !v)}>
                  {showPassword ? "Hide" : "Show"}
                </button>
              }
              required
            />
          </FormField>

          <FormField label="Confirm Password">
            <Input type="password" placeholder="Confirm password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
          </FormField>

          <div className="grid grid-cols-5 gap-1">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className={`h-2 rounded ${score > i ? "bg-[var(--color-success)]" : "bg-[var(--color-bg-sunken)]"}`} />
            ))}
          </div>

          <ul className="space-y-1 text-xs text-[var(--color-text-secondary)]">
            {checksView.map(([ok, label]) => (
              <li key={label}>{ok ? "[OK]" : "[ ]"} {label}</li>
            ))}
          </ul>

          {error ? <div className="rounded-[var(--radius-md)] bg-[var(--color-error-soft)] p-2.5 text-sm text-[var(--color-error)]">{error}</div> : null}

          <Button className="w-full" loading={loading} disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </Button>
        </form>

        <p className="body-sm mt-4">
          Already have an account?{" "}
          <Link href="/auth/login" className="text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
