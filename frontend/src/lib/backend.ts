import type { UserMe } from "./types";

export class ApiError extends Error {
  status: number;
  body?: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function getBackendUrl(): string {
  const raw = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
  return raw.replace(/\/+$/, "");
}

export function backendUrl(path: string): string {
  if (!path.startsWith("/")) path = `/${path}`;
  return `${getBackendUrl()}${path}`;
}

export async function backendFetch<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(backendUrl(path), {
    ...init,
    headers,
    credentials: "include",
    body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await res.json().catch(() => undefined) : await res.text().catch(() => undefined);

  if (!res.ok) {
    const msg = (() => {
      if (body && typeof body === "object") {
        const rec = body as Record<string, unknown>;
        if ("detail" in rec) return String(rec.detail);
      }
      return `Request failed (${res.status})`;
    })();
    throw new ApiError(msg, res.status, body);
  }

  return body as T;
}

export async function getMe(): Promise<UserMe> {
  return backendFetch<UserMe>("/auth/me", { method: "GET" });
}

export async function logout(): Promise<void> {
  await backendFetch("/auth/logout", { method: "POST" });
}
