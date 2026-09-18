"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ScanStatusPill } from "@/components/reviewer/StatusPill";
import { resolveImageUrl, ApiError } from "@/lib/api";
import { reviewerApi } from "@/lib/reviewerApi";
import type { ScanResult } from "@/lib/types";

export default function ScanInvestigationPage() {
  const params = useParams<{ scanId: string }>();
  const router = useRouter();
  const scanId = Number(params?.scanId);

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(scanId)) {
      setError("That scan could not be found.");
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setScan(await reviewerApi.scanDetail(scanId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/login?next=/reviewer/scans/${scanId}`);
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not load this scan."
      );
    } finally {
      setLoading(false);
    }
  }, [router, scanId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <p className="text-sm text-gray-400 p-8">Loading…</p>;
  }

  if (error || !scan) {
    return (
      <div className="p-8">
        <p className="text-sm text-gray-700">{error ?? "Scan not found."}</p>
        <button
          onClick={() => router.back()}
          className="mt-4 inline-block text-sm font-medium text-blue-700 hover:underline"
        >
          ← Go back
        </button>
      </div>
    );
  }

  const url = resolveImageUrl(scan.scan_image_url);

  return (
    <div>
      <button
        onClick={() => router.back()}
        className="text-sm font-medium text-blue-700 hover:underline"
      >
        ← Back
      </button>

      <div className="mt-4 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Scan Investigation #{scan.id}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {new Date(scan.created_at).toLocaleString("en-IN", {
              day: "numeric",
              month: "short",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
            {" · "}
            <Link href={`/reviewer/${scan.stall_id}`} className="text-blue-600 hover:underline">
              View Stall #{scan.stall_id}
            </Link>
          </p>
        </div>
        <div className="text-right">
          <ScanStatusPill status={scan.status} />
          {scan.retake_required && (
            <p className="mt-1 text-xs text-amber-600 font-medium">
              Retake required
            </p>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left Column: Image and OCR */}
        <div className="space-y-6">
          <section className="rounded-lg bg-white p-5 ring-1 ring-inset ring-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Original Image</h2>
            <div className="rounded-lg bg-gray-100 p-2 overflow-hidden flex justify-center">
              {url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={url}
                  alt="Scanned product label"
                  className="max-h-96 object-contain"
                />
              ) : (
                <div className="flex h-48 w-full items-center justify-center text-sm text-gray-500">
                  Image unavailable
                </div>
              )}
            </div>

            {scan.image_quality && (
              <div className="mt-4 border-t border-gray-100 pt-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Image Quality</h3>
                <dl className="mt-2 grid grid-cols-2 gap-2 text-sm text-gray-800">
                  <div>Brightness: {scan.image_quality.metrics?.brightness?.toFixed(1) ?? "—"}</div>
                  <div>Sharpness: {scan.image_quality.metrics?.sharpness?.toFixed(1) ?? "—"}</div>
                  {scan.image_quality.issues && scan.image_quality.issues.length > 0 && (
                    <div className="col-span-2 text-amber-700 mt-1">
                      Issues: {scan.image_quality.issues.join(", ").replace(/_/g, " ")}
                    </div>
                  )}
                </dl>
              </div>
            )}
          </section>

          <section className="rounded-lg bg-white p-5 ring-1 ring-inset ring-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">OCR Extraction</h2>
            <div className="flex items-center gap-4 text-sm text-gray-700 mb-3">
              <div>
                <span className="font-medium">Confidence:</span> {Math.round(scan.ocr_confidence * 100)}%
              </div>
              <div>
                <span className="font-medium">Language:</span> {scan.language_code.toUpperCase()}
              </div>
            </div>
            <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-800 whitespace-pre-wrap font-mono ring-1 ring-inset ring-gray-200">
              {scan.ingredient_text || "No text extracted."}
            </div>
          </section>
        </div>

        {/* Right Column: Ingredients and Rules */}
        <div className="space-y-6">
          <section className="rounded-lg bg-white p-5 ring-1 ring-inset ring-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Analysis Result</h2>
            <div className="rounded bg-blue-50 p-4 ring-1 ring-blue-100">
              <p className="text-sm text-blue-900 font-medium">{scan.explanation}</p>
            </div>
            
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded bg-gray-50 p-3 ring-1 ring-gray-200">
                <div className="text-xs text-gray-500 uppercase">Match Conf</div>
                <div className="mt-1 text-lg font-semibold tabular-nums text-gray-900">
                  {Math.round(scan.match_confidence * 100)}%
                </div>
              </div>
              <div className="rounded bg-gray-50 p-3 ring-1 ring-gray-200">
                <div className="text-xs text-gray-500 uppercase">Rule Strength</div>
                <div className="mt-1 text-lg font-semibold tabular-nums text-gray-900">
                  {Math.round(scan.rule_strength * 100)}%
                </div>
              </div>
              <div className="rounded bg-gray-50 p-3 ring-1 ring-gray-200">
                <div className="text-xs text-gray-500 uppercase">Final Conf</div>
                <div className="mt-1 text-lg font-semibold tabular-nums text-gray-900">
                  {Math.round(scan.confidence_score * 100)}%
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-lg bg-white p-5 ring-1 ring-inset ring-gray-200">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">
              Ingredient Evidence ({scan.matched_ingredients?.length || 0})
            </h2>
            
            {(!scan.matched_ingredients || scan.matched_ingredients.length === 0) ? (
              <p className="text-sm text-gray-500">No ingredients matched.</p>
            ) : (
              <ul className="space-y-3">
                {scan.matched_ingredients.map((match, i) => (
                  <li key={i} className="rounded-md border border-gray-200 p-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="font-semibold text-gray-900">{match.canonical_name}</span>
                        {match.matched_alias && match.matched_alias !== match.canonical_name && (
                          <span className="ml-2 text-xs text-gray-500">
                            (matched via "{match.matched_alias}")
                          </span>
                        )}
                      </div>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        match.risk_level === "forbidden" 
                          ? "bg-red-100 text-red-800" 
                          : match.risk_level === "discouraged"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-emerald-100 text-emerald-800"
                      }`}>
                        {match.risk_level}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
