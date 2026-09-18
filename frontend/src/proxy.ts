import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route protection for the authenticated areas.
 *
 * NOTE: this file is `proxy.ts`, not `middleware.ts`. Next.js 16 renamed the
 * convention — `middleware.ts` and `export function middleware()` are
 * deprecated, and the export must now be named `proxy`. The file must sit
 * next to `app/` (here, in `src/`), and there can only be one per project.
 *
 * This is a coarse gate, not authorization: it only checks that *a* token
 * cookie exists. It cannot validate the signature, and it does not know the
 * user's role. Real authorization happens on the backend, where every
 * endpoint enforces roles via `require_roles` — a client that forges its way
 * past this redirect still gets 401/403 from FastAPI.
 */

const AUTH_COOKIE = "token";

/** Path prefixes that require a signed-in user. */
const PROTECTED_PREFIXES = ["/vendor", "/reviewer", "/consumer"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (!isProtected) return NextResponse.next();

  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (token) return NextResponse.next();

  // Preserve where they were headed so login can send them back.
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/vendor/:path*", "/reviewer/:path*", "/consumer/:path*"],
};
