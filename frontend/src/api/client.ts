// The only code that talks to the server. Same origin, the session cookie, a CSRF header on
// every non-GET request, every failure as an ApiError, and session-expiry detection.
// A background refresh (the 30-second polls) sends `X-Background-Refresh: 1`, so the server
// does not count it as activity: only the user's own requests keep the session alive.

import type { ErrorBody } from "./types";

export class ApiError extends Error {
  readonly status: number;
  /** The server's message, shown as is ("" when it sent none). */
  readonly detail: string;
  /** Why a request was refused (422). */
  readonly reasons?: string[];
  /** Field name → messages (400 validation errors). */
  readonly fieldErrors?: Record<string, string[]>;

  constructor(
    status: number,
    detail: string,
    extra: { reasons?: string[]; fieldErrors?: Record<string, string[]> } = {},
  ) {
    super(detail || `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.reasons = extra.reasons;
    this.fieldErrors = extra.fieldErrors;
  }
}

const CSRF_COOKIE = "csrftoken";
const ME = "/api/auth/me";
/** Their 403s mean "refused", never "your session ended": there is no session yet. */
const NO_SESSION_CHECK = new Set([ME, "/api/auth/login", "/api/auth/login/verify"]);
export const BACKGROUND_HEADER = "X-Background-Refresh";

let csrfReady: Promise<void> | null = null;
let onSessionExpired: (() => void) | null = null;
let lastActive = 0;

/** When the last request that extends the session (any but a background refresh) answered. */
export function lastActiveRequestAt(): number {
  return lastActive;
}

/** SessionProvider registers what to do when the session has ended (clear, go to sign-in). */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

/** Fetches the CSRF cookie once per page load (again only if that attempt failed). */
export function ensureCsrf(): Promise<void> {
  if (!csrfReady) {
    const attempt = fetch("/api/auth/csrf", { credentials: "same-origin" }).then((response) => {
      if (!response.ok) throw new ApiError(response.status, "");
    });
    attempt.catch(() => {
      if (csrfReady === attempt) csrfReady = null;
    });
    csrfReady = attempt;
  }
  return csrfReady;
}

/** For tests: forget the CSRF fetch and the expiry handler. */
export function resetClientState(): void {
  csrfReady = null;
  onSessionExpired = null;
  lastActive = 0;
}

function readCookie(name: string): string {
  const prefix = `${name}=`;
  const found = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

function toApiError(status: number, body: unknown): ApiError {
  const data: ErrorBody = body && typeof body === "object" ? (body as ErrorBody) : {};
  const detail = typeof data.detail === "string" ? data.detail : "";
  const reasons = Array.isArray(data.reasons) ? data.reasons : undefined;
  let fieldErrors: Record<string, string[]> | undefined;
  if (status === 400) {
    const fields = Object.entries(data).filter(
      ([key, value]) => key !== "detail" && Array.isArray(value),
    );
    if (fields.length) {
      fieldErrors = Object.fromEntries(fields.map(([key, value]) => [key, value as string[]]));
    }
  }
  return new ApiError(status, detail, { reasons, fieldErrors });
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

// A 403 is either "not allowed" or "your session has ended": ask `me` to tell them apart.
async function checkSession(): Promise<void> {
  try {
    const response = await fetch(ME, { credentials: "same-origin" });
    if (!response.ok) onSessionExpired?.();
  } catch {
    // Offline: leave the session alone; the original error is still reported.
  }
}

export interface RequestOptions {
  /** A refresh the user did not ask for: the server does not extend the session for it. */
  background?: boolean;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  { background = false }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (background) headers[BACKGROUND_HEADER] = "1";
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = readCookie(CSRF_COOKIE);
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!background) lastActive = Date.now();
  const data = await readJson(response);
  if (response.ok) return data as T;
  if (response.status === 403 && !NO_SESSION_CHECK.has(path)) await checkSession();
  throw toApiError(response.status, data);
}

export function apiGet<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>("GET", path, undefined, options);
}

export function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>("POST", path, body);
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>("PUT", path, body);
}

/** A query string from the non-empty values ("" and undefined are left out). */
export function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
