"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, backendUrl, getBackendUrl, getMe } from "../../lib/backend";

type Provider = "google" | "github";

export default function LoginClient({
  nextUrl,
  error,
}: {
  nextUrl?: string;
  error?: string;
}) {
  const router = useRouter();
  const next = nextUrl || "/app";

  const [loading, setLoading] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);

  const backend = useMemo(() => getBackendUrl(), []);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then(() => {
        if (cancelled) return;
        router.replace(next);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          setSessionChecked(true);
          return;
        }
        setFatal(e instanceof Error ? e.message : "Failed to check session");
        setSessionChecked(true);
      });

    return () => {
      cancelled = true;
    };
  }, [router, next]);

  function start(provider: Provider) {
    setLoading(true);
    setFatal(null);
    window.location.href = backendUrl(`/auth/oauth/${provider}/login`);
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(1200px_circle_at_20%_10%,rgba(255,255,255,0.09),transparent_55%),radial-gradient(900px_circle_at_80%_0%,rgba(255,255,255,0.06),transparent_50%)]" />

      <div className="relative mx-auto grid min-h-screen w-full max-w-6xl grid-cols-1 items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-2">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-2xl bg-white/10 ring-1 ring-white/15" />
            <div>
              <div className="text-xl font-semibold tracking-tight">Agentpress</div>
              <div className="text-sm text-zinc-400">Self-hosted AI agents with plugins</div>
            </div>
          </div>

          <h1 className="mt-8 text-4xl font-semibold leading-tight tracking-tight">
            A modern workspace for agents.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-zinc-300/90">
            Create agents, chat with streaming responses, and execute tools safely — all on infrastructure you control.
          </p>

          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="text-sm font-semibold">Local-first</div>
            <div className="mt-1 text-sm text-zinc-400">
              Your credentials stay in your environment. Your data stays on your machine.
            </div>
          </div>

          <div className="mt-6 text-xs text-zinc-500">
            Backend: <span className="text-zinc-300">{backend}</span>
          </div>
        </div>

        <div className="lg:justify-self-end">
          <div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-6 ring-1 ring-white/5">
            <div className="text-lg font-semibold tracking-tight">Sign in</div>
            <div className="mt-1 text-sm text-zinc-400">Continue with a provider to start using Agentpress.</div>

            {!sessionChecked && (
              <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-zinc-300">
                Checking session…
              </div>
            )}

            {fatal && (
              <div className="mt-6 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100/90">
                {fatal}
              </div>
            )}

            {error && (
              <div className="mt-6 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-100/90">
                Sign-in failed. Please try again.
              </div>
            )}

            <div className="mt-6 grid gap-3">
              <button
                onClick={() => start("google")}
                disabled={loading || !sessionChecked}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 disabled:opacity-60"
              >
                Continue with Google
              </button>

              <button
                onClick={() => start("github")}
                disabled={loading || !sessionChecked}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-zinc-100 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 disabled:opacity-60"
              >
                Continue with GitHub
              </button>
            </div>

            <div className="mt-6 text-xs text-zinc-500">
              By continuing, you agree to run this software on your own infrastructure.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
