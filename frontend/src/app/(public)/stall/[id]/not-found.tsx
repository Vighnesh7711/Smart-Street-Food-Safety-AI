import Link from "next/link";

/**
 * Shown for both an unknown code and a revoked one.
 *
 * Deliberately says the same thing for each: the page must not reveal
 * whether a stall exists, only that this code does not resolve.
 */
export default function StallNotFound() {
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center bg-gray-50 px-6 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-200 text-3xl">
        🔍
      </div>
      <h1 className="text-xl font-bold text-gray-900">
        No stall found for this code
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        The QR code may be damaged, or it may belong to a stall that is no
        longer registered. Try scanning it again, or ask the vendor for their
        code.
      </p>
      <Link
        href="/"
        className="mt-6 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white"
      >
        Go to home
      </Link>
    </div>
  );
}
