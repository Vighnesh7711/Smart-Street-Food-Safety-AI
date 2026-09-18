"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, api, fetchQrBlob } from "@/lib/api";
import type { StallQr } from "@/lib/types";

/**
 * "My QR code" — the vendor's printable sticker.
 *
 * Design brief: this screen gets photographed off the phone, or shown to
 * someone printing a sticker. So it is a plain white card, maximum size, with
 * nothing overlapping the code and no dark mode inversion (a QR on a dark
 * background scans unreliably and prints badly).
 *
 * The code is also shown as large monospace text. That is the fallback for a
 * damaged or unreadable sticker -- the vendor or the customer can type it.
 */
export default function VendorQrPage() {
  const router = useRouter();
  const [qr, setQr] = useState<StallQr | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    (async () => {
      try {
        const me = await api.me();
        if (me.vendor_id === null) {
          if (!cancelled) {
            setError("Register your stall first to get a QR code.");
            setLoading(false);
          }
          return;
        }

        const stalls = await api.myStalls();
        if (stalls.length === 0) {
          if (!cancelled) {
            setError("Register your stall first to get a QR code.");
            setLoading(false);
          }
          return;
        }

        const details = await api.getStallQr(stalls[0].id);
        const blob = await fetchQrBlob(stalls[0].id);
        objectUrl = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setQr(details);
        setImageUrl(objectUrl);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login?next=/vendor/qr");
          return;
        }
        setError(
          err instanceof ApiError ? err.message : "Could not load your QR code."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      // Object URLs pin the blob in memory until revoked.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [router]);

  const handleDownload = useCallback(async () => {
    if (!qr) return;
    setDownloading(true);
    try {
      const blob = await fetchQrBlob(qr.stall_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `stall-${qr.code}.png`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      // Revoke on the next tick: revoking synchronously can cancel the
      // download in some browsers before it has read the blob.
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not download the QR code."
      );
    } finally {
      setDownloading(false);
    }
  }, [qr]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-gray-400">
        Loading…
      </div>
    );
  }

  if (error || !qr) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-3xl">
          🔳
        </div>
        <p className="text-sm text-gray-600">
          {error ?? "No QR code available."}
        </p>
        <Link
          href="/vendor"
          className="mt-6 w-full rounded-full bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white"
        >
          Set up my stall
        </Link>
      </div>
    );
  }

  return (
    <div className="p-5 pb-8">
      <h1 className="text-xl font-bold text-gray-900">My QR code</h1>
      <p className="mt-1 text-sm text-gray-500">
        Print this and display it at your stall. Customers scan it to see your
        hygiene score.
      </p>

      {/* The card: pure white, generous padding, nothing overlapping. */}
      <div className="mt-5 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-inset ring-gray-200">
        {imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={`QR code for ${qr.code}`}
            className="mx-auto block w-full max-w-xs"
          />
        )}
        <p className="mt-3 text-center font-mono text-lg font-bold tracking-widest text-gray-900">
          {qr.code}
        </p>
        <p className="mt-1 text-center text-xs text-gray-500">
          If the code will not scan, this can be typed in manually.
        </p>
      </div>

      <button
        type="button"
        onClick={handleDownload}
        disabled={downloading}
        className="mt-5 w-full rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
      >
        {downloading ? "Preparing…" : "Download PNG"}
      </button>

      <p className="mt-4 break-all text-center text-xs text-gray-400">
        {qr.public_url}
      </p>
    </div>
  );
}
