"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import CameraCapture from "@/components/vendor/CameraCapture";
import ScanResultCard from "@/components/scan/ScanResultCard";
import ProductComparison from "@/components/scan/ProductComparison";
import { ApiError, api } from "@/lib/api";
import type { ScanResult } from "@/lib/types";

/**
 * Vendor scan flow.
 *
 *   loading -> needs_stall | ready -> capturing -> uploading -> result | error
 *
 * The scan endpoint is synchronous, so `uploading` covers the whole
 * pipeline (quality check, OCR, matching, explanation, translation) on the
 * server. The camera view stays mounted underneath the spinner so the
 * vendor does not lose their framing if they retake.
 */

type Phase = "loading" | "needs_stall" | "ready" | "uploading" | "result";

export default function ScanPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [stallId, setStallId] = useState<number | null>(null);
  const [language, setLanguage] = useState<string>("en");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [firstResult, setFirstResult] = useState<ScanResult | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /** Resolve the vendor's stall before offering the camera. */
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const me = await api.me();
        if (cancelled) return;

        if (me.vendor_id === null) {
          setPhase("needs_stall");
          return;
        }
        setLanguage(me.preferred_language ?? "en");

        const stalls = await api.myStalls();
        if (cancelled) return;

        if (stalls.length === 0) {
          setPhase("needs_stall");
          return;
        }
        setStallId(stalls[0].id);
        setPhase("ready");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login?next=/vendor/scan");
          return;
        }
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load your stall details."
        );
        setPhase("ready");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleCapture = useCallback(
    async (image: Blob) => {
      if (stallId === null) return;

      setError(null);
      setPhase("uploading");
      try {
        const scan = await api.scanLabel({
          stallId,
          image,
          language,
        });
        setResult(scan);
        setPhase("result");
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : "The label could not be read. Please try again."
        );
        // Back to the camera so the vendor can immediately retake.
        setPhase("ready");
      }
    },
    [language, stallId]
  );

  const resetComparison = () => {
    setResult(null);
    setFirstResult(null);
    setIsComparing(false);
    setPhase("ready");
  };

  // --- No stall yet ---
  if (phase === "needs_stall") {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-soft text-3xl">
          🏪
        </div>
        <h1 className="text-xl font-extrabold text-text-primary font-['Plus_Jakarta_Sans']">
          Register your stall first
        </h1>
        <p className="mt-2 text-sm text-text-primary/60 font-['Inter']">
          Scans are recorded against your stall, so we need its details before
          you can start scanning product labels.
        </p>
        <Link
          href="/vendor"
          className="mt-6 w-full rounded-full bg-surface-dark px-4 py-3 text-center text-sm font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
        >
          Set up my stall
        </Link>
      </div>
    );
  }

  // --- Loading ---
  if (phase === "loading") {
    return (
      <div className="flex h-full items-center justify-center p-6 text-text-primary/40 font-['Plus_Jakarta_Sans'] font-bold">
        Loading…
      </div>
    );
  }

  // --- Result ---
  if (phase === "result" && result) {
    if (isComparing && firstResult) {
      return (
        <ProductComparison 
          result1={firstResult} 
          result2={result} 
          onReset={resetComparison} 
        />
      );
    }

    return (
      <ScanResultCard
        result={result}
        onRetake={() => {
          setResult(null);
          setPhase("ready");
        }}
        onScanAnother={() => {
          setResult(null);
          setError(null);
          setPhase("ready");
        }}
        onCompare={() => {
          setFirstResult(result);
          setIsComparing(true);
          setResult(null);
          setPhase("ready");
        }}
      />
    );
  }

  // --- Camera (ready / uploading) ---
  return (
    <>
      {error && (
        <div
          role="alert"
          className="absolute left-0 right-0 top-0 z-[70] mx-auto max-w-md p-4"
        >
          <p className="rounded-xl bg-[#E53935]/95 px-3 py-2 text-sm font-bold text-white shadow-[0_2px_8px_rgba(16,34,15,0.06)] font-['Plus_Jakarta_Sans']">
            {error}
          </p>
        </div>
      )}
      
      {/* Top action bar for history */}
      <div className="absolute left-0 right-0 top-0 z-[65] mx-auto max-w-md p-4 flex justify-between items-center pointer-events-none">
        <div className="rounded-xl bg-black/50 backdrop-blur pointer-events-auto">
          <Link
            href="/vendor/scan/history"
            className="block px-4 py-2 text-sm font-medium text-white"
          >
            📋 Scan History
          </Link>
        </div>
        {isComparing && (
        <div className="rounded-xl bg-surface-dark px-3 py-1 shadow-[0_4px_12px_rgba(11,69,22,0.2)] pointer-events-auto text-text-inverse text-[11px] uppercase tracking-widest font-extrabold font-['Plus_Jakarta_Sans']">
            Scan 2nd Product
          </div>
        )}
      </div>

      <CameraCapture
        onCapture={handleCapture}
        busy={phase === "uploading"}
        busyLabel="Reading label…"
      />
    </>
  );
}
