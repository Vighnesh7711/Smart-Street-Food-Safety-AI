"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import FlagDialog from "@/components/reviewer/FlagDialog";
import HygieneScoreChart from "@/components/reviewer/HygieneScoreChart";
import StallImageGallery from "@/components/reviewer/StallImageGallery";
import {
  FlagBadge,
  HygieneStatus,
  ScanStatusPill,
  ScoreDelta,
} from "@/components/reviewer/StatusPill";
import { ApiError } from "@/lib/api";
import { reviewerApi } from "@/lib/reviewerApi";
import type { VendorDetail } from "@/lib/types";

/**
 * Vendor detail: the full record for one stall.
 *
 * A client component using `useParams()`, which returns plain values rather
 * than the Promise the `params` page prop delivers in Next.js 16.
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

export default function VendorDetailPage() {
  const params = useParams<{ stallId: string }>();
  const router = useRouter();
  const stallId = Number(params?.stallId);

  const [detail, setDetail] = useState<VendorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flagging, setFlagging] = useState(false);
  const [resolving, setResolving] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(stallId)) {
      setError("That stall could not be found.");
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setDetail(await reviewerApi.vendorDetail(stallId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/login?next=/reviewer/${stallId}`);
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not load this stall."
      );
    } finally {
      setLoading(false);
    }
  }, [router, stallId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const resolve = async (flagId: number) => {
    const note = window.prompt("Optional resolution note:");
    if (note === null) return; // Cancelled
    
    setResolving(flagId);
    try {
      await reviewerApi.resolveFlag(flagId, note || undefined);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not resolve that flag."
      );
    } finally {
      setResolving(null);
    }
  };

  if (loading) {
    return <p className="text-sm text-gray-400">Loading…</p>;
  }

  if (error || !detail) {
    return (
      <div>
        <p className="text-sm text-gray-700">{error ?? "Stall not found."}</p>
        <Link
          href="/reviewer"
          className="mt-4 inline-block text-sm font-medium text-blue-700 hover:underline"
        >
          ← Back to vendors
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Link
        href="/reviewer"
        className="text-sm font-medium text-blue-700 hover:underline"
      >
        ← Back to vendors
      </Link>

      {/* Header */}
      <div className="mt-4 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {detail.stall_name}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {detail.food_category ?? "Uncategorised"}
            {detail.vendor_name ? ` · ${detail.vendor_name}` : ""}
          </p>
          {detail.address && (
            <p className="mt-0.5 text-sm text-gray-500">{detail.address}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setFlagging(true)}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
        >
          Flag for follow-up
        </button>
      </div>

      {/* Current state */}
      <div className="mt-6 grid grid-cols-4 gap-4">
        <div className="rounded-lg bg-white px-4 py-3 ring-1 ring-inset ring-gray-200">
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Current score
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-gray-900">
            {detail.current_score === null
              ? "—"
              : detail.current_score.toFixed(1)}
          </dd>
          {detail.current_band && (
            <div className="mt-2">
              <HygieneStatus band={detail.current_band} />
            </div>
          )}
          {detail.hygiene_history.length > 0 && (
            <div className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500">
              <p>Visual: {detail.hygiene_history[detail.hygiene_history.length - 1].visual_score.toFixed(1)}</p>
              <p>Checklist: {detail.hygiene_history[detail.hygiene_history.length - 1].checklist_score?.toFixed(1) ?? "—"}</p>
              <p className="mt-1">Formula: v{detail.hygiene_history[detail.hygiene_history.length - 1].formula_version}</p>
            </div>
          )}
        </div>

        <div className="rounded-lg bg-white px-4 py-3 ring-1 ring-inset ring-gray-200">
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Change
          </dt>
          <dd className="mt-3">
            <ScoreDelta delta={detail.score_delta} />
          </dd>
        </div>

        <div className="rounded-lg bg-white px-4 py-3 ring-1 ring-inset ring-gray-200">
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Assessments
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-gray-900">
            {detail.hygiene_history.length}
          </dd>
        </div>

        <div className="rounded-lg bg-white px-4 py-3 ring-1 ring-inset ring-gray-200">
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Label checks
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-gray-900">
            {detail.scan_history.length}
          </dd>
        </div>
      </div>

      {/* Flags */}
      {detail.open_flags.length > 0 && (
        <section className="mt-6 rounded-lg bg-red-50 p-5 ring-1 ring-inset ring-red-200">
          <h2 className="flex items-center gap-3 text-sm font-semibold text-red-900">
            Open flags <FlagBadge count={detail.open_flags.length} />
          </h2>
          <ul className="mt-3 space-y-3">
            {detail.open_flags.map((flag) => (
              <li
                key={flag.id}
                className="flex items-start justify-between gap-6 rounded-md bg-white p-3"
              >
                <div>
                  <p className="text-sm text-gray-900">{flag.reason}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    Raised by {flag.created_by_name ?? "unknown"} on{" "}
                    {formatDateTime(flag.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void resolve(flag.id)}
                  disabled={resolving === flag.id}
                  className="shrink-0 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {resolving === flag.id ? "Resolving…" : "Mark resolved"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Score history */}
      <section className="mt-6">
        <HygieneScoreChart
          history={detail.hygiene_history.map((point) => ({
            score: point.score,
            at: point.assessed_at,
            band: point.band,
            visual_score: point.visual_score,
            checklist_score: point.checklist_score,
          }))}
        />
      </section>

      {/* Scan history */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-gray-900">
          Label check history
          <span className="ml-2 font-normal text-gray-500">
            ({detail.scan_history.length})
          </span>
        </h2>

        {detail.scan_history.length === 0 ? (
          <div className="mt-3 rounded-lg bg-white p-8 text-center ring-1 ring-inset ring-gray-200">
            <p className="text-sm text-gray-500">
              No product labels have been scanned yet.
            </p>
          </div>
        ) : (
          <div className="mt-3 overflow-hidden rounded-lg bg-white ring-1 ring-inset ring-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {["Result", "Ingredients", "Confidence", "Language", "Date", ""].map(
                    (label, index) => (
                      <th
                        key={label || "action"}
                        scope="col"
                        className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 ${
                          index >= 1 && index <= 2 ? "text-right" : "text-left"
                        }`}
                      >
                        {label}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {detail.scan_history.map((scan) => (
                  <tr key={scan.scan_id}>
                    <td className="px-4 py-3">
                      <ScanStatusPill status={scan.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-600">
                      {scan.ingredient_count}
                    </td>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-600">
                      {scan.confidence_score === null
                        ? "—"
                        : `${Math.round(scan.confidence_score * 100)}%`}
                    </td>
                    <td className="px-4 py-3 text-sm uppercase text-gray-600">
                      {scan.language_code}
                      {scan.translation_failed && (
                        <span
                          className="ml-1 text-amber-600"
                          title="Translation was unavailable; English was shown"
                        >
                          ⚠
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm tabular-nums text-gray-600">
                      {formatDateTime(scan.scanned_at)}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-right">
                      <Link 
                        href={`/reviewer/scans/${scan.scan_id}`}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Investigate
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Stall images */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-gray-900">
          Submitted stall photos
          <span className="ml-2 font-normal text-gray-500">
            ({detail.images.length})
          </span>
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Detected indicators are boxed on the photo and listed beneath it.
        </p>
        <div className="mt-3">
          <StallImageGallery images={detail.images} />
        </div>
      </section>

      {flagging && (
        <FlagDialog
          stallId={detail.stall_id}
          stallName={detail.stall_name}
          onClose={() => setFlagging(false)}
          onFlagged={() => {
            setFlagging(false);
            void load();
          }}
        />
      )}
    </div>
  );
}
