"use client";

import { useRouter } from "next/navigation";

import { clearToken } from "@/lib/auth";

/**
 * Sign out.
 *
 * Clears the token cookie and returns to the login screen. Note this is a
 * client-side clear only -- the JWT itself remains valid until it expires,
 * so a token captured beforehand would still work. Server-side revocation
 * needs a token denylist, which is deferred along with the rest of the
 * audit-logging work.
 */
export default function SignOutButton() {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => {
        clearToken();
        router.replace("/login");
      }}
      className="w-full rounded px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
    >
      Sign out
    </button>
  );
}
