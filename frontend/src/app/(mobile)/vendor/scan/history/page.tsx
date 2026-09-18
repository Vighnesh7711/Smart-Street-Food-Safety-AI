"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import type { ScanResult } from "@/lib/types";

function getStatusStyle(status: string) {
  switch (status) {
    case "Suitable":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "Potential concern":
    case "Application mismatch":
      return "bg-amber-100 text-amber-800 ring-amber-200";
    case "Insufficient information":
    case "Needs review":
      return "bg-slate-100 text-slate-800 ring-slate-200";
    default:
      return "bg-gray-100 text-gray-800 ring-gray-200";
  }
}

export default function ScanHistoryPage() {
  const router = useRouter();
  const [history, setHistory] = useState<ScanResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.me();
        if (me.vendor_id === null) {
          router.replace("/vendor/profile/edit");
          return;
        }

        const stalls = await api.myStalls();
        if (stalls.length === 0) {
          router.replace("/vendor/profile/edit");
          return;
        }

        const scans = await api.scanHistory(stalls[0].id, 40);
        if (!cancelled) setHistory(scans);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login?next=/vendor/scan/history");
          return;
        }
        setError(
          err instanceof ApiError ? err.message : "Could not load scan history."
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

  return (
    <div className="p-5 pb-8 min-h-screen bg-gray-50">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scan History</h1>
          <p className="mt-1 text-sm text-gray-500">
            Previously scanned product labels.
          </p>
        </div>
        <Link
          href="/vendor/scan"
          className="rounded-full bg-gray-200 p-2 text-gray-700 hover:bg-gray-300"
          aria-label="Back to scan"
        >
          ✕
        </Link>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200"
        >
          {error}
        </p>
      )}

      {history.length === 0 && !error && (
        <div className="mt-8 rounded-xl bg-white p-6 text-center ring-1 ring-inset ring-gray-200">
          <p className="text-sm text-gray-600">No scans yet.</p>
          <p className="mt-1 text-xs text-gray-500">
            Scan food product labels to see their history here.
          </p>
        </div>
      )}

      <ul className="mt-4 space-y-4">
        {history.map((scan) => (
          <li
            key={scan.id}
            className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-inset ring-gray-200"
          >
            <div className="flex justify-between items-start mb-2">
              <h3 className="font-semibold text-gray-900">
                {scan.product_name || "Unknown Product"}
              </h3>
              <span
                className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium ring-1 ring-inset ${getStatusStyle(
                  scan.status
                )}`}
              >
                {scan.status}
              </span>
            </div>
            
            <p className="text-sm text-gray-700 mb-3">
              {scan.explanation_translated}
            </p>
            
            <div className="flex gap-4 text-xs text-gray-500 border-t border-gray-100 pt-3">
              <div>
                <span className="block font-medium text-gray-700">{Math.round(scan.ocr_confidence * 100)}%</span>
                OCR
              </div>
              <div>
                <span className="block font-medium text-gray-700">{Math.round(scan.match_confidence * 100)}%</span>
                Match
              </div>
              <div className="ml-auto text-right">
                <span className="block text-gray-400">Scanned on</span>
                {new Date(scan.created_at).toLocaleDateString()}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
