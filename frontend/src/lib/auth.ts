/**
 * Client-side auth token storage.
 *
 * SECURITY TRADEOFF (MVP+ scope, deliberately chosen):
 * The JWT lives in a plain, JS-readable cookie rather than an HttpOnly one.
 * That is required because two different consumers need it:
 *   1. `src/proxy.ts` (server) reads it to gate /vendor and /reviewer routes.
 *   2. The browser client reads it to set the `Authorization: Bearer` header
 *      when calling FastAPI directly.
 *
 * An HttpOnly cookie would fix (1) but break (2) — the client could no longer
 * read it, so every API call would have to be proxied through a Next Route
 * Handler that forwards the cookie server-side. That is the right eventual
 * design, but it is extra machinery this phase does not need.
 *
 * The cost: any XSS on this origin can exfiltrate the token. Mitigations
 * before this goes in front of real vendors: move to HttpOnly + Route Handler
 * proxying, and/or shorten ACCESS_TOKEN_EXPIRE_MINUTES.
 */

const TOKEN_COOKIE = "token";

/**
 * Mirrors ACCESS_TOKEN_EXPIRE_MINUTES in the backend (7 days). The cookie is
 * deliberately given the same lifetime as the JWT so the two cannot disagree
 * about whether a session is still valid.
 */
const TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

export function setToken(token: string): void {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = [
    `${TOKEN_COOKIE}=${encodeURIComponent(token)}`,
    "path=/",
    `max-age=${TOKEN_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ].join("; ") + secure;
}

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${TOKEN_COOKIE}=([^;]*)`)
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export function clearToken(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
