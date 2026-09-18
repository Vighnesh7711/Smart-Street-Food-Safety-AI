"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { reviewerApi } from "@/lib/reviewerApi";
import type { FlagRecord, FlagStatus } from "@/lib/types";

/**
 * Flagged stalls.
 *
 * Open flags by default, with resolved history behind a toggle. A list that
 * only ever grows stops being a to-do list, which is why flags have a
 * lifecycle at all.
 */

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function FlaggedPage() {
  const router = useRouter();
  const [status, setStatus] = useState<FlagStatus>("open");
  const [flags, setFlags] = useState<FlagRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolving, setResolving] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await reviewerApi.flags({ status, limit: 100 });
      setFlags(response.items);
      setTotal(response.total);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login?next=/reviewer/flagged");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not load flags.");
    } finally {
      setLoading(false);
    }
  }, [router, status]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const resolve = async (flag: FlagRecord) => {
    setResolving(flag.id);
    try {
      await reviewerApi.resolveFlag(flag.id);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not resolve that flag."
      );
    } finally {
      setResolving(null);
    }
  };

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Flagged stalls</h1>
          <p className="mt-1 text-sm text-gray-600">
            Stalls a reviewer has asked to follow up on.
          </p>
        </div>

        <div className="flex rounded-md ring-1 ring-inset ring-gray-300">
          {(["open", "resolved"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setStatus(value)}
              aria-pressed={status === value}
              className={`px-4 py-2 text-sm font-medium capitalize ${
                status === value
                  ? "bg-gray-900 text-white"
                  : "bg-white text-gray-700 hover:bg-gray-50"
              } ${value === "open" ? "rounded-l-md" : "rounded-r-md"}`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
        >
          {error}
        </p>
      )}

      <p className="mt-6 text-sm text-gray-500">
        {loading
          ? "Loading…"
          : `${total} ${status} flag${total === 1 ? "" : "s"}`}
      </p>

      {!loading && flags.length === 0 && (
        <div className="mt-4 rounded-lg bg-white p-12 text-center ring-1 ring-inset ring-gray-200">
          <p className="text-sm font-medium text-gray-900">
            {status === "open" ? "Nothing flagged." : "No resolved flags yet."}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {status === "open"
              ? "Stalls you flag from the vendors table appear here."
              : "Resolved flags are kept so you can see what was dealt with."}
          </p>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {flags.map((flag) => (
          <li
            key={flag.id}
            className="rounded-lg bg-white p-5 ring-1 ring-inset ring-gray-200"
          >
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <Link
                    href={`/reviewer/${flag.stall_id}`}
                    className="text-sm font-semibold text-gray-900 hover:text-blue-700"
                  >
                    {flag.stall_name ?? `Stall #${flag.stall_id}`}
                  </Link>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
                      flag.status === "open"
                        ? "bg-red-50 text-red-900 ring-red-200"
                        : "bg-emerald-50 text-emerald-900 ring-emerald-200"
                    }`}
                  >
                    {flag.status === "open" ? "⚑ Open" : "✓ Resolved"}
                  </span>
                </div>

                <p className="mt-2 text-sm text-gray-800">{flag.reason}</p>

                <p className="mt-2 text-xs text-gray-500">
                  Raised by {flag.created_by_name ?? "unknown"} on{" "}
                  {formatDateTime(flag.created_at)}
                </p>

                {flag.status === "resolved" && (
                  <p className="mt-1 text-xs text-gray-500">
                    Resolved by {flag.resolved_by_name ?? "unknown"} on{" "}
                    {formatDateTime(flag.resolved_at)}
                    {flag.resolution_note ? ` — ${flag.resolution_note}` : ""}
                  </p>
                )}
              </div>

              {flag.status === "open" && (
                <button
                  type="button"
                  onClick={() => void resolve(flag)}
                  disabled={resolving === flag.id}
                  className="shrink-0 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {resolving === flag.id ? "Resolving…" : "Mark resolved"}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
