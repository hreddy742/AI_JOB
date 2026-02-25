export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)]">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-4 py-10">{children}</div>
    </main>
  );
}
