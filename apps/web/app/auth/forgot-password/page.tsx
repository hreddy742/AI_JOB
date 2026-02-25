"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api-client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 text-center">
        <div className="text-4xl">??</div>
        <h1 className="mt-2 text-2xl font-semibold">Check your email</h1>
        <p className="mt-2 text-sm text-slate-300">If {email} has an account, you&apos;ll receive a reset link shortly.</p>
        <p className="text-sm text-slate-400">The link expires in 1 hour. Check spam if you don&apos;t see it.</p>
        <Link className="mt-4 inline-block text-sky-300 underline" href="/auth/login">Back to Sign In</Link>
      </div>
    );
  }

  return (
    <form className="w-full max-w-md space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-6" onSubmit={onSubmit}>
      <h1 className="text-2xl font-semibold">Forgot password</h1>
      <input className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={loading} />
      <button className="w-full rounded-md bg-blue-600 px-3 py-2" disabled={loading}>{loading ? "Sending..." : "Send Reset Link"}</button>
      <Link href="/auth/login" className="block text-center text-sm text-sky-300 underline">Back to Sign In</Link>
    </form>
  );
}
