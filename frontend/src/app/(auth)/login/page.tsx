import LoginForm from "@/components/auth/LoginForm";

/**
 * Server wrapper that unwraps `searchParams`.
 *
 * In Next.js 16 `searchParams` is a Promise and synchronous access was
 * removed, so it must be awaited. Reading it here (a Server Component) and
 * passing a plain string down avoids `useSearchParams()` in the client,
 * which would require a <Suspense> boundary or the production build fails.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const raw = typeof params.next === "string" ? params.next : undefined;

  /**
   * `next` comes straight from the URL, so it is attacker-controllable.
   * Only same-origin absolute paths are allowed: "//evil.com" and
   * "https://evil.com" are both protocol-relative or absolute URLs that
   * `router.replace` would happily follow off-site (an open redirect).
   */
  const nextPath =
    raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : undefined;

  return <LoginForm nextPath={nextPath} />;
}
