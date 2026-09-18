"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import QrScanner from "@/components/qr/QrScanner";
import { describeScanRejection, stallCodeFromScan } from "@/lib/qr";

/**
 * Consumer entry point: scan a stall's QR code.
 *
 * Scanning lands on `/stall/<code>`, which is public and unauthenticated --
 * so a consumer who uses their own camera app never needs this screen at
 * all. It exists for people already in the app, and because it works when
 * their camera app does not recognise the link.
 *
 * Manual code entry is offered alongside the camera rather than only after a
 * failure: on an insecure origin the camera is simply unavailable, and a
 * dead-end screen at the front door of the consumer experience is worse than
 * a text field nobody usually needs.
 */
export default function ConsumerHome() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [navigating, setNavigating] = useState(false);
  const [manualCode, setManualCode] = useState("");

  const goToCode = useCallback(
    (raw: string) => {
      const code = stallCodeFromScan(raw);
      if (!code) {
        // Never navigate on a guess: a wrong code shows a different stall's
        // hygiene record to someone standing at a stall.
        setError(describeScanRejection(raw));
        return;
      }
      setError(null);
      // Pause the scanner: without this the camera keeps decoding the same
      // sticker and firing repeat navigations during the transition.
      setNavigating(true);
      router.push(`/stall/${code}`);
    },
    [router]
  );

  const handleManualSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    goToCode(manualCode);
  };

  return (
    <div className="p-5 pb-8">
      <h1 className="text-2xl font-bold text-gray-900">Scan a stall</h1>
      <p className="mt-1 text-sm text-gray-500">
        Point your camera at the QR code displayed at the stall to see its
        hygiene assessment.
      </p>

      <div className="mt-5">
        <QrScanner onResult={goToCode} paused={navigating} />
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-inset ring-amber-200"
        >
          {error}
        </p>
      )}

      {/* Manual fallback */}
      <form onSubmit={handleManualSubmit} className="mt-6">
        <label
          htmlFor="manual-code"
          className="block text-sm font-semibold text-gray-900"
        >
          Or type the code
        </label>
        <p className="mb-2 mt-1 text-xs text-gray-500">
          The code is printed under the QR sticker.
        </p>
        <div className="flex gap-2">
          <input
            id="manual-code"
            type="text"
            value={manualCode}
            onChange={(event) => setManualCode(event.target.value)}
            placeholder="e.g. AB12CD34EF"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            className="min-w-0 flex-1 rounded-xl border-0 px-4 py-3 font-mono text-base uppercase text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:font-sans placeholder:normal-case placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-600"
          />
          <button
            type="submit"
            className="shrink-0 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white"
          >
            Go
          </button>
        </div>
      </form>

      <p className="mt-8 rounded-xl bg-slate-100 p-3 text-[11px] leading-relaxed text-slate-600 ring-1 ring-inset ring-slate-200">
        Assessments shown are AI-assisted and are not an official
        certification.
      </p>
    </div>
  );
}
