import { api } from './client';
import type { ChatRequest } from './types';
import { parseSseStream, safeJsonParse } from './sse';

export type ChatStreamHandler = (event: { event: string; data: unknown }) => void;

export async function streamChat(agentId: string, body: ChatRequest, onEvent: ChatStreamHandler, signal?: AbortSignal) {
  const controller = new AbortController();
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const res = await api.post(`/agents/${agentId}/chat`, body, {
    responseType: 'stream',
    signal: controller.signal,
    headers: { Accept: 'text/event-stream' },
  });

  // Axios can't stream body directly in browser; fall back to fetch for SSE
  const fetchRes = await fetch(`${api.defaults.baseURL}/agents/${agentId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    credentials: 'include',
    signal: controller.signal,
  });

  if (!fetchRes.ok || !fetchRes.body) {
    throw new Error('Chat stream failed');
  }

  (async () => {
    for await (const msg of parseSseStream(fetchRes.body)) {
      onEvent({ event: msg.event, data: safeJsonParse(msg.data) });
    }
  })().catch(() => controller.abort());

  return () => controller.abort();
}
