"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, backendFetch, backendUrl } from "../../../../../lib/backend";
import type { Agent } from "../../../../../lib/types";
import { AppShell } from "../../../../../components/AppShell";
import { parseSseStream, safeJsonParse } from "../../../../../lib/sse";

type ChatItem =
  | { kind: "msg"; role: "user" | "assistant"; text: string }
  | { kind: "event"; label: string; detail?: string };

export default function ChatClient({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const assistantIndexRef = useRef<number | null>(null);

  function isRecord(value: unknown): value is Record<string, unknown> {
    return !!value && typeof value === "object";
  }

  const headerSubtitle = useMemo(() => {
    if (!agent) return "";
    return `${agent.model} · temp ${agent.temperature.toFixed(1)}`;
  }, [agent]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    backendFetch<Agent>(`/agents/${agentId}`, { method: "GET" })
      .then((a) => {
        if (cancelled) return;
        setAgent(a);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setError("Agent not found");
        } else {
          setError(e instanceof Error ? e.message : "Failed to load agent");
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [agentId]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setSending(true);
    setError(null);

    setItems((prev) => [...prev, { kind: "msg", role: "user", text }]);

    try {
      const res = await fetch(backendUrl(`/agents/${agentId}/chat`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });

      if (!res.ok || !res.body) {
        const ct = res.headers.get("content-type") || "";
        const detail = ct.includes("application/json")
          ? await res.json().catch(() => null)
          : await res.text().catch(() => null);
        throw new ApiError("Chat request failed", res.status, detail);
      }

      assistantIndexRef.current = null;

      for await (const msg of parseSseStream(res.body)) {
        const payload = safeJsonParse(msg.data);

        if (msg.event === "conversation" && isRecord(payload) && "conversation_id" in payload) {
          const cid = payload.conversation_id;
          if (typeof cid === "string") setConversationId(cid);
          continue;
        }

        if (msg.event === "message_start") {
          setItems((prev) => {
            const next = [...prev, { kind: "msg", role: "assistant", text: "" } as const];
            assistantIndexRef.current = next.length - 1;
            return next;
          });
          continue;
        }

        if (msg.event === "token" && isRecord(payload) && "text" in payload) {
          const t = payload.text;
          if (typeof t === "string" && t) {
            setItems((prev) => {
              const idx = assistantIndexRef.current;
              if (idx === null || idx < 0 || idx >= prev.length) return prev;
              const next = [...prev];
              const cur = next[idx];
              if (cur.kind !== "msg" || cur.role !== "assistant") return prev;
              next[idx] = { ...cur, text: cur.text + t };
              return next;
            });
          }
          continue;
        }

        if (msg.event === "tool_call_start") {
          setItems((prev) => [...prev, { kind: "event", label: "Tool started" }]);
          continue;
        }
        if (msg.event === "tool_call_end") {
          setItems((prev) => [...prev, { kind: "event", label: "Tool finished" }]);
          continue;
        }
        if (msg.event === "tool_call_error") {
          setItems((prev) => [...prev, { kind: "event", label: "Tool error" }]);
          continue;
        }

        if (msg.event === "error") {
          if (isRecord(payload)) {
            const message = payload.message;
            const code = payload.code;
            if (typeof message === "string" && message.trim()) {
              if (typeof code === "string" && code.trim()) {
                setError(`${code}: ${message}`);
              } else {
                setError(message);
              }
              continue;
            }
          }

          setError("The backend reported an error during streaming.");
          continue;
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-zinc-400">
            <Link href="/app" className="hover:text-zinc-200">
              Agents
            </Link>
            <span className="px-2">/</span>
            <span className="text-zinc-200">Chat</span>
          </div>
          <div className="mt-2 text-2xl font-semibold tracking-tight">
            {loading ? "Loading…" : agent?.name || "Chat"}
          </div>
          {headerSubtitle && <div className="mt-1 text-sm text-zinc-400">{headerSubtitle}</div>}
        </div>

        {conversationId && (
          <div className="hidden rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-300 sm:block">
            Conversation {conversationId.slice(0, 8)}…
          </div>
        )}
      </div>

      {error && (
        <div className="mt-5 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100/90">
          {error}
        </div>
      )}

      <div className="mt-6 flex min-h-[70vh] flex-col gap-4">
        <div className="flex-1 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex h-full flex-col">
            <div className="flex-1 space-y-3 overflow-y-auto pr-1">
              {items.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-zinc-950/30 p-4 text-sm text-zinc-300">
                  Start by sending a message. Responses stream in real-time.
                </div>
              ) : (
                items.map((it, idx) => {
                  if (it.kind === "event") {
                    return (
                      <div key={idx} className="text-xs text-zinc-400">
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                          {it.label}
                        </span>
                      </div>
                    );
                  }

                  const isUser = it.role === "user";
                  return (
                    <div key={idx} className={"flex " + (isUser ? "justify-end" : "justify-start")}>
                      <div
                        className={
                          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ring-1 " +
                          (isUser
                            ? "bg-white text-zinc-950 ring-white/10"
                            : "bg-zinc-950/30 text-zinc-100 ring-white/10")
                        }
                      >
                        {it.text || (it.role === "assistant" && sending ? "…" : "")}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="mt-auto shrink-0">
          <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-zinc-950/30 px-3 py-1.5 ring-1 ring-white/5">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message your agent…"
              rows={1}
              className="flex-1 resize-none bg-transparent py-0.5 text-sm leading-5 outline-none placeholder:text-zinc-500"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              disabled={sending}
            />

            <button
              onClick={() => void send()}
              disabled={sending || !input.trim()}
              className="inline-flex h-8 shrink-0 items-center justify-center rounded-full bg-white px-3 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-100 disabled:opacity-60"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
