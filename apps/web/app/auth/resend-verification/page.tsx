"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api-client";

export default function ResendVerificationPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setLoading(true);
    try {
      const res = await api.resendVerification(email);
      setMessage(res.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="w-full max-w-md space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-6" onSubmit={onSubmit}>
      <h1 className="text-2xl font-semibold">Resend verification email</h1>
      <input className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      {message ? <div className="rounded-md bg-blue-500/20 p-2 text-sm text-blue-200">{message}</div> : null}
      <button className="w-full rounded-md bg-blue-600 px-3 py-2" disabled={loading}>{loading ? "Sending..." : "Resend Link"}</button>
      <Link href="/auth/login" className="block text-center text-sm text-sky-300 underline">Back to Sign In</Link>
    </form>
  );
}
