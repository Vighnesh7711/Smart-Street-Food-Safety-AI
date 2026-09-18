"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import HygieneResultCard from "@/components/hygiene/HygieneResultCard";
import { ApiError, api } from "@/lib/api";
import type { HygieneCheck } from "@/lib/types";

/**
 * Results for one hygiene check.
 *
 * A client component using `useParams()`, which returns plain values rather
 * than the Promise that the `params` page prop delivers in Next.js 16.
 */
export default function HygieneCheckPage() {
  const params = useParams<{ checkId: string }>();
  const router = useRouter();
  const checkId = Number(params?.checkId);

  const [check, setCheck] = useState<HygieneCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!Number.isFinite(checkId)) {
      setError("That check could not be found.");
      setLoading(false);
      return;
    }
    try {
      setCheck(await api.getHygieneCheck(checkId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/login?next=/vendor/hygiene/${checkId}`);
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not load that check."
      );
    } finally {
      setLoading(false);
    }
  }, [checkId, router]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-gray-400">
        Loading…
      </div>
    );
  }

  if (error || !check) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <p className="text-sm text-gray-600">{error ?? "Check not found."}</p>
        <Link
          href="/vendor/hygiene"
          className="mt-4 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white"
        >
          Back to hygiene
        </Link>
      </div>
    );
  }

  // An unfinished check: send the vendor back into the capture flow rather
  // than showing a results screen with no result on it.
  if (check.status !== "scored") {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-3xl">
          📷
        </div>
        <h1 className="text-xl font-bold text-gray-900">Check not finished</h1>
        <p className="mt-2 text-sm text-gray-500">
          {check.coverage.message || "Some photos are still needed."}
        </p>
        <Link
          href="/vendor/hygiene/new"
          className="mt-6 w-full rounded-full bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white"
        >
          Continue this check
        </Link>
      </div>
    );
  }

  return (
    <>
      <HygieneResultCard check={check} />
      <div className="px-5 pb-10">
        <Link
          href="/vendor/hygiene"
          className="block w-full rounded-full border border-gray-300 bg-white px-4 py-3 text-center text-sm font-semibold text-gray-700"
        >
          Back to all checks
        </Link>
      </div>
    </>
  );
}
