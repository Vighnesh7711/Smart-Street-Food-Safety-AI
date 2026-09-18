"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * QR scanner for the consumer shell.
 *
 * Uses `qr-scanner`, which prefers the browser's native `BarcodeDetector`
 * where it exists (Chrome/Android -- fast, no WASM) and falls back to a
 * bundled worker elsewhere (iOS Safari, Firefox). The alternative, `jsqr`,
 * would mean driving video frames by hand with requestAnimationFrame for no
 * accuracy benefit.
 *
 * MOBILE CONSTRAINTS, same as every camera surface in this app:
 * `navigator.mediaDevices` only exists in a secure context (https:// or
 * localhost). Over `http://192.168.x.x` it is `undefined`, not merely
 * blocked. The camera is therefore feature-detected and, when unavailable,
 * the caller is told plainly and offered manual code entry -- this is the
 * entry point for the whole consumer experience, so it must not present as
 * a dead end.
 */

type ScannerState = "idle" | "requesting" | "scanning" | "denied" | "unavailable";

interface QrScannerProps {
  /**
   * Called with the raw decoded text. The caller decides whether it is a
   * stall code -- parsing lives in lib/qr.ts so it can be unit-tested.
   */
  onResult: (text: string) => void;
  /** Paused while the caller is navigating, so the camera does not keep
   * decoding and firing duplicate results. */
  paused?: boolean;
}

export default function QrScanner({ onResult, paused = false }: QrScannerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const scannerRef = useRef<unknown>(null);
  const [state, setState] = useState<ScannerState>("idle");
  const [error, setError] = useState<string | null>(null);

  // Keeps the latest callback without re-creating the scanner, which would
  // restart the camera on every parent render.
  const onResultRef = useRef(onResult);
  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  const stop = useCallback(() => {
    const scanner = scannerRef.current as { stop?: () => void; destroy?: () => void } | null;
    if (scanner) {
      try {
        scanner.stop?.();
        scanner.destroy?.();
      } catch {
        // Already torn down; nothing useful to do.
      }
      scannerRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const start = useCallback(async () => {
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setState("unavailable");
      setError(
        "The camera is not available here. This usually means the page is not being served over HTTPS."
      );
      return;
    }

    const video = videoRef.current;
    if (!video) return;

    setState("requesting");
    setError(null);

    try {
      const { default: QrScanner } = await import("qr-scanner");
      const scanner = new QrScanner(
        video,
        (result: { data: string }) => onResultRef.current(result.data),
        {
          preferredCamera: "environment",
          highlightScanRegion: true,
          highlightCodeOutline: true,
          // Native BarcodeDetector is much faster where available; the
          // worker fallback is used automatically when it is not.
          returnDetailedScanResult: true,
        }
      );
      scannerRef.current = scanner;
      await scanner.start();
      setState("scanning");
    } catch (err) {
      stop();
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setState("denied");
        setError(
          "Camera access was blocked. Allow camera access for this site in your browser settings."
        );
      } else {
        setState("unavailable");
        setError("The camera could not be started on this device.");
      }
    }
  }, [stop]);

  // Release the camera on unmount, or the indicator light stays on and the
  // battery drains.
  useEffect(() => stop, [stop]);

  useEffect(() => {
    const scanner = scannerRef.current as { stop?: () => void; start?: () => Promise<void> } | null;
    if (!scanner) return;
    if (paused) {
      scanner.stop?.();
    } else {
      void scanner.start?.().catch(() => undefined);
    }
  }, [paused]);

  return (
    <div className="flex flex-col">
      <div className="relative aspect-square w-full overflow-hidden rounded-2xl bg-gray-900">
        <video
          ref={videoRef}
          playsInline
          muted
          className="h-full w-full object-cover"
        />

        {state !== "scanning" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
            {state === "requesting" ? (
              <p className="text-sm text-white/80">Starting camera…</p>
            ) : (
              <>
                <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-white/10 text-2xl">
                  🔳
                </div>
                <p className="text-sm text-white/80">
                  {error ??
                    "Point your camera at the stall's QR code."}
                </p>
                {(state === "idle" ||
                  state === "denied" ||
                  state === "unavailable") && (
                  <button
                    type="button"
                    onClick={start}
                    className="mt-4 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white"
                  >
                    {state === "idle" ? "Open camera" : "Try again"}
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
