"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, api, resolveImageUrl } from "@/lib/api";
import { bandStyle } from "@/lib/hygieneStyles";
import type { HygieneCheckSummary } from "@/lib/types";

/**
 * Hygiene history: newest first.
 *
 * Unfinished checks are requested alongside completed ones because an
 * abandoned draft is the most likely thing a returning vendor wants to
 * resume -- but they are rendered as a separate banner rather than mixed
 * into the scored list, so a list of results never contains a non-result.
 */

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function HygieneHistoryPage() {
  const router = useRouter();
  const [checks, setChecks] = useState<HygieneCheckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const history = await api.hygieneHistory({
          includeUnfinished: true,
          limit: 40,
        });
        if (!cancelled) setChecks(history);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login?next=/vendor/hygiene");
          return;
        }
        setError(
          err instanceof ApiError ? err.message : "Could not load your history."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-gray-400">
        Loading…
      </div>
    );
  }

  const unfinished = checks.filter((c) => c.status !== "scored");
  const scored = checks.filter((c) => c.status === "scored");

  return (
    <div className="p-5 pb-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Hygiene</h1>
          <p className="mt-1 text-sm text-gray-500">
            Your stall checks and scores over time.
          </p>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
        >
          {error}
        </p>
      )}

      <Link
        href="/vendor/hygiene/new"
        className="mt-5 block w-full rounded-full bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white"
      >
        Start a new check
      </Link>

      {/* Unfinished checks, surfaced separately from results */}
      {unfinished.map((check) => (
        <Link
          key={check.id}
          href={`/vendor/hygiene/${check.id}`}
          className="mt-4 block rounded-xl bg-amber-50 p-4 ring-1 ring-inset ring-amber-200"
        >
          <p className="text-sm font-semibold text-amber-900">
            Unfinished check
          </p>
          <p className="mt-0.5 text-xs text-amber-800">
            {check.missing_views.length > 0
              ? `${check.missing_views.length} photo${
                  check.missing_views.length === 1 ? "" : "s"
                } still needed`
              : "Ready to score"}
          </p>
          <p className="mt-1 text-xs text-amber-700">
            Started {formatDate(check.created_at)} — tap to continue
          </p>
        </Link>
      ))}

      {scored.length === 0 && unfinished.length === 0 && (
        <div className="mt-8 rounded-xl bg-gray-50 p-6 text-center ring-1 ring-inset ring-gray-200">
          <p className="text-sm text-gray-600">No checks yet.</p>
          <p className="mt-1 text-xs text-gray-500">
            Photograph four views of your stall to get a hygiene score.
          </p>
        </div>
      )}

      <ul className="mt-5 space-y-3">
        {scored.map((check) => {
          const style = bandStyle(check.band);
          const thumbnail = resolveImageUrl(check.thumbnail_url);
          return (
            <li key={check.id}>
              <Link
                href={`/vendor/hygiene/${check.id}`}
                className="flex items-center gap-4 rounded-xl bg-white p-3 ring-1 ring-inset ring-gray-200"
              >
                {thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={thumbnail}
                    alt=""
                    className="h-16 w-16 shrink-0 rounded-lg object-cover"
                  />
                ) : (
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-2xl">
                    🏪
                  </div>
                )}

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900">
                    {formatDate(check.scored_at ?? check.created_at)}
                  </p>
                  {/* The band word sits next to the colour, not instead of
                      it: two of the four band colours are low-contrast on a
                      light surface, and a score read only as a colour tells
                      a colourblind vendor nothing. */}
                  <p className="mt-0.5 text-xs text-gray-500">
                    <span className="font-medium text-gray-700">
                      <span aria-hidden="true">{style.icon}</span> {style.label}
                    </span>
                    {" · "}
                    {check.indicator_count === 0
                      ? "no concerns detected"
                      : `${check.indicator_count} finding${
                          check.indicator_count === 1 ? "" : "s"
                        }`}
                  </p>
                </div>

                <span
                  className={`shrink-0 rounded-full px-3 py-1 text-sm font-bold tabular-nums ring-1 ring-inset ${style.chip}`}
                >
                  {check.final_score === null
                    ? "—"
                    : Math.round(check.final_score)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>

      <p className="mt-8 text-center text-[11px] leading-relaxed text-gray-400">
        AI-assisted assessment, not an official certification.
      </p>
    </div>
  );
}
