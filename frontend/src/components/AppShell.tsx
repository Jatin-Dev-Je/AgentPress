"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { ApiError, getMe, logout } from "../lib/backend";
import type { UserMe } from "../lib/types";

export function AppShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const [me, setMe] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const initials = useMemo(() => {
    const name = (me?.name || me?.email || "").trim();
    if (!name) return "U";
    const parts = name.split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "U";
    const b = parts.length > 1 ? parts[parts.length - 1]?.[0] : "";
    return (a + b).toUpperCase();
  }, [me]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getMe()
      .then((u) => {
        if (cancelled) return;
        setMe(u);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(pathname || "/app")}`);
          return;
        }
        setError(e instanceof Error ? e.message : "Failed to load session");
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router, pathname]);

  async function onLogout() {
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(1200px_circle_at_20%_10%,rgba(255,255,255,0.08),transparent_55%),radial-gradient(900px_circle_at_80%_0%,rgba(255,255,255,0.06),transparent_50%)]" />

      <header className="relative border-b border-white/10">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/app" className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-xl bg-white/10 ring-1 ring-white/15" />
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-tight">Agentpress</div>
              <div className="text-xs text-zinc-400">Self-hosted agents</div>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {me && (
              <div className="hidden items-center gap-3 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 sm:flex">
                <div className="grid h-8 w-8 place-items-center rounded-full bg-white/10 text-xs font-semibold ring-1 ring-white/10">
                  {initials}
                </div>
                <div className="min-w-0">
                  <div className="max-w-[220px] truncate text-sm font-medium">
                    {me.name || me.email}
                  </div>
                  <div className="max-w-[220px] truncate text-xs text-zinc-400">{me.email}</div>
                </div>
              </div>
            )}

            <button
              onClick={onLogout}
              className="inline-flex h-10 items-center justify-center rounded-full border border-white/10 bg-white/5 px-4 text-sm font-medium text-zinc-100 transition hover:bg-white/10 disabled:opacity-50"
              disabled={loading}
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="relative mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
        {loading && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <div className="h-5 w-48 animate-pulse rounded bg-white/10" />
            <div className="mt-4 h-4 w-72 animate-pulse rounded bg-white/10" />
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="h-24 animate-pulse rounded-xl bg-white/10" />
              <div className="h-24 animate-pulse rounded-xl bg-white/10" />
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5">
            <div className="text-sm font-semibold">Something went wrong</div>
            <div className="mt-1 text-sm text-red-100/90">{error}</div>
            <button
              onClick={() => router.refresh()}
              className="mt-4 inline-flex h-10 items-center justify-center rounded-full bg-red-500/20 px-4 text-sm font-medium text-red-50 ring-1 ring-red-500/30 transition hover:bg-red-500/25"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && children}
      </main>
    </div>
  );
}
