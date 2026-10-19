/** Thin fetch wrapper. The website authenticates with the HttpOnly login cookie (same origin). */

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, init);
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, data?.error?.code ?? 'http_error', data?.error?.message ?? `HTTP ${res.status}`);
  }
  return data as T;
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  if (body instanceof FormData) return api<T>(path, { method: 'POST', body });
  return api<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');
