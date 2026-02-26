/**
 * Centralized API Client
 *
 * Single source of truth for API configuration and base fetch utilities.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Route all API calls through the Next.js proxy (/api_be/* → backend) to avoid CORS.
// The proxy destination is configured in next.config.ts using NEXT_PUBLIC_API_URL.
export const API_BASE = '/api_be/api/v1';

export function getAuthHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('resume_matcher_access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function clearAuthAndRedirect(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('resume_matcher_access_token');
  localStorage.removeItem('resume_matcher_refresh_token');
  window.location.href = '/auth/login';
}

async function withTokenRefresh(
  fn: (token: string | null) => Promise<Response>
): Promise<Response> {
  const token =
    typeof window !== 'undefined'
      ? localStorage.getItem('resume_matcher_access_token')
      : null;

  const res = await fn(token);

  if (res.status !== 401) return res;

  const refreshToken =
    typeof window !== 'undefined'
      ? localStorage.getItem('resume_matcher_refresh_token')
      : null;

  if (!refreshToken) {
    clearAuthAndRedirect();
    return res;
  }

  try {
    const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!refreshRes.ok) {
      clearAuthAndRedirect();
      return res;
    }

    const data = await refreshRes.json();
    localStorage.setItem('resume_matcher_access_token', data.access_token);
    localStorage.setItem('resume_matcher_refresh_token', data.refresh_token);

    return fn(data.access_token);
  } catch {
    clearAuthAndRedirect();
    return res;
  }
}

/**
 * Standard fetch wrapper with common error handling.
 * Injects Authorization header and handles 401 with token refresh.
 * Returns the Response object for flexibility.
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  return withTokenRefresh((token) => {
    const headers = new Headers(options?.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  });
}

/**
 * POST request with JSON body.
 */
export async function apiPost<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * PATCH request with JSON body.
 */
export async function apiPatch<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * PUT request with JSON body.
 */
export async function apiPut<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * DELETE request.
 */
export async function apiDelete(endpoint: string): Promise<Response> {
  return apiFetch(endpoint, { method: 'DELETE' });
}

/**
 * Builds the full upload URL for file uploads.
 */
export function getUploadUrl(): string {
  return `${API_BASE}/resumes/upload`;
}
