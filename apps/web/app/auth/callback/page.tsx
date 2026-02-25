"use client";

export const dynamic = "force-dynamic";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { useAuthStore } from "@/lib/auth-store";

function AuthCallbackContent() {
  const params = useSearchParams();
  const router = useRouter();
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const refreshToken = useAuthStore((s) => s.refreshToken);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      router.replace("/auth/login?error=google_auth_failed");
      return;
    }

    setAccessToken(token);
    void refreshToken().then(() => {
      const redirect = params.get("redirect") || "/dashboard";
      router.replace(redirect);
    }).catch(() => {
      router.replace("/auth/login?error=google_auth_failed");
    });
  }, [params, router, refreshToken, setAccessToken]);

  return <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">Processing Google sign-in...</div>;
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className="rounded-xl border border-slate-800 bg-slate-900 p-6">Processing Google sign-in...</div>}>
      <AuthCallbackContent />
    </Suspense>
  );
}
