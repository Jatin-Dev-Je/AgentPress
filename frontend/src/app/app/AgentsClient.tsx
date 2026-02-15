"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, backendFetch } from "../../lib/backend";
import type { Agent } from "../../lib/types";
import { AppShell } from "../../components/AppShell";

type CreateAgentBody = {
  name: string;
  model: string;
  system_prompt: string;
  temperature: number;
};

export default function AgentsClient() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => agents.find((a) => a.id === selectedId) || null,
    [agents, selectedId],
  );

  const [form, setForm] = useState<CreateAgentBody>({
    name: "",
    model: "ollama",
    system_prompt: "You are helpful.",
    temperature: 0.7,
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    backendFetch<Agent[]>("/agents", { method: "GET" })
      .then((list) => {
        if (cancelled) return;
        setAgents(list);
        setSelectedId(list[0]?.id || null);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          // AppShell handles auth redirect.
          setLoading(false);
          return;
        }
        setError(e instanceof Error ? e.message : "Failed to load agents");
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function createAgent() {
    const name = form.name.trim();
    if (!name) {
      setError("Agent name is required");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await backendFetch<Agent>("/agents", {
        method: "POST",
        json: {
          ...form,
          name,
        },
      });
      setAgents((prev) => [created, ...prev]);
      setSelectedId(created.id);
      setForm((f) => ({ ...f, name: "" }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create agent");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">Agents</div>
              <div className="text-xs text-zinc-400">Select or create an agent</div>
            </div>
          </div>

          <div className="mt-4 grid gap-3">
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="New agent name"
              className="h-11 w-full rounded-2xl border border-white/10 bg-zinc-950/30 px-3 text-sm outline-none ring-0 placeholder:text-zinc-500 focus:border-white/20"
            />
            <div className="grid grid-cols-2 gap-3">
              <select
                value={form.model}
                onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
                className="h-11 w-full rounded-2xl border border-white/10 bg-zinc-950/30 px-3 text-sm outline-none focus:border-white/20"
              >
                <option value="ollama">ollama</option>
                <option value="openai">openai</option>
                <option value="anthropic">anthropic</option>
              </select>
              <input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature}
                onChange={(e) => setForm((f) => ({ ...f, temperature: Number(e.target.value) }))}
                className="h-11 w-full rounded-2xl border border-white/10 bg-zinc-950/30 px-3 text-sm outline-none focus:border-white/20"
              />
            </div>
            <textarea
              value={form.system_prompt}
              onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
              rows={4}
              className="w-full resize-none rounded-2xl border border-white/10 bg-zinc-950/30 px-3 py-2 text-sm outline-none placeholder:text-zinc-500 focus:border-white/20"
            />

            <button
              onClick={createAgent}
              disabled={saving}
              className="inline-flex h-11 items-center justify-center rounded-2xl bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-100 disabled:opacity-60"
            >
              {saving ? "Creating…" : "Create agent"}
            </button>

            {error && (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-100/90">
                {error}
              </div>
            )}
          </div>

          <div className="mt-6">
            {loading ? (
              <div className="space-y-2">
                <div className="h-10 animate-pulse rounded-xl bg-white/10" />
                <div className="h-10 animate-pulse rounded-xl bg-white/10" />
                <div className="h-10 animate-pulse rounded-xl bg-white/10" />
              </div>
            ) : agents.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-zinc-300">
                No agents yet. Create your first agent above.
              </div>
            ) : (
              <div className="grid gap-2">
                {agents.map((a) => {
                  const active = a.id === selectedId;
                  return (
                    <button
                      key={a.id}
                      onClick={() => setSelectedId(a.id)}
                      className={
                        "w-full rounded-2xl border px-3 py-2 text-left transition " +
                        (active
                          ? "border-white/20 bg-white/10"
                          : "border-white/10 bg-white/5 hover:bg-white/10")
                      }
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold">{a.name}</div>
                          <div className="truncate text-xs text-zinc-400">{a.model}</div>
                        </div>
                        <div className="text-xs text-zinc-500">{a.temperature.toFixed(1)}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/5 p-6">
          {!selected ? (
            <div>
              <div className="text-sm font-semibold">Select an agent</div>
              <div className="mt-1 text-sm text-zinc-400">
                Choose an agent from the list to start a chat.
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xl font-semibold tracking-tight">{selected.name}</div>
                  <div className="mt-1 text-sm text-zinc-400">
                    Model: <span className="text-zinc-200">{selected.model}</span> · Temp:{" "}
                    <span className="text-zinc-200">{selected.temperature.toFixed(1)}</span>
                  </div>
                </div>

                <Link
                  href={`/app/agents/${selected.id}/chat`}
                  className="inline-flex h-11 items-center justify-center rounded-2xl bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-100"
                >
                  Open chat
                </Link>
              </div>

              <div className="mt-6 flex-1 rounded-2xl border border-white/10 bg-zinc-950/30 p-4">
                <div className="text-xs font-semibold text-zinc-300">System prompt</div>
                <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-200/90">
                  {selected.system_prompt || "(empty)"}
                </div>
              </div>

              <div className="mt-4 text-xs text-zinc-500">
                Streaming chat and tool visibility are enabled in the chat view.
              </div>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
