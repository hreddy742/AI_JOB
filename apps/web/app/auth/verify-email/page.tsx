"use client";

export const dynamic = "force-dynamic";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";

function VerifyEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const [state, setState] = useState<"loading" | "success" | "expired" | "invalid" | "already_used">("loading");
  const setAccessToken = useAuthStore((s) => s.setAccessToken);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("invalid");
      return;
    }

    void api.verifyEmail(token)
      .then((res) => {
        setAccessToken(res.access_token);
        setState("success");
        setTimeout(() => router.push("/dashboard"), 3000);
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message.toLowerCase() : "";
        if (message.includes("expired")) setState("expired");
        else if (message.includes("already-used")) setState("already_used");
        else setState("invalid");
      });
  }, [params, router, setAccessToken]);

  if (state === "loading") return <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">Verifying your email...</div>;
  if (state === "success") return <div className="rounded-xl border border-emerald-700 bg-emerald-900/30 p-6">?? Email verified! Redirecting in 3s...</div>;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
      <p className="mb-4">{state === "expired" ? "Link expired" : state === "already_used" ? "This link was already used. Try logging in." : "Invalid link"}</p>
      <a href="/auth/resend-verification" className="rounded bg-blue-600 px-3 py-2">Request new verification link</a>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="rounded-xl border border-slate-800 bg-slate-900 p-6">Verifying your email...</div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
