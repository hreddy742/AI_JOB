"use client";

import Link from "next/link";

import { GlassCard } from "@/components/ui/GlassCard";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-4 py-10">
      <GlassCard padding="xl" className="w-full">
        <p className="label-lg">Apex Apply</p>
        <h1 className="display-hero mt-3 max-w-2xl">Warm, precise, AI-assisted job execution for serious candidates.</h1>
        <p className="body-lg mt-4 max-w-2xl">
          Navigate roles, tailor resumes, and ship applications with a minimal glass UI tuned for speed and focus.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/auth/login"
            className="inline-flex min-h-[38px] items-center justify-center rounded-[10px] bg-[var(--color-accent)] px-[18px] py-[9px] text-[13.5px] font-medium text-white transition duration-150 hover:-translate-y-px hover:bg-[var(--color-accent-hover)]"
          >
            Sign in
          </Link>
          <Link
            href="/auth/register"
            className="inline-flex min-h-[38px] items-center justify-center rounded-[10px] border border-[var(--color-border-sub)] bg-transparent px-[18px] py-[9px] text-[13.5px] font-medium text-[var(--color-text-secondary)] transition duration-150 hover:bg-[rgba(0,0,0,0.04)]"
          >
            Create account
          </Link>
        </div>
      </GlassCard>
    </main>
  );
}
