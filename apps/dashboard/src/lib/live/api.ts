/**
 * The console's client for the `/v1` API (same origin). Mutations send the session's CSRF token in
 * the header the server names; the session cookie itself is httpOnly and never touched here.
 */
import type { Session } from "@/mocks/types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly retryAfterS: number | null = null,
  ) {
    super(message);
  }
}

let csrf: { header: string; token: string } | null = null;

export function setCsrfFrom(session: Session | null) {
  csrf = session?.csrf ? { header: session.csrf_header, token: session.csrf } : null;
}

async function parse<T>(res: Response): Promise<T> {
  const json = (res.headers.get("content-type") ?? "").includes("application/json");
  const body: unknown = json ? await res.json() : null;
  if (!res.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d?.msg ?? "").join("; ") : res.statusText;
    const retry = Number(res.headers.get("retry-after"));
    throw new ApiError(res.status, message || `HTTP ${res.status}`, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  if (!json) throw new ApiError(res.status, "not an API response");
  return body as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", cache: "no-store", signal, headers: { Accept: "application/json" } });
  return parse<T>(res);
}

export async function apiSend<T>(method: "POST" | "PATCH", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (csrf) headers[csrf.header] = csrf.token;
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return parse<T>(res);
}
