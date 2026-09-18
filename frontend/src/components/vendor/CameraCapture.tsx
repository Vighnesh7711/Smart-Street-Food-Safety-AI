"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Full-screen rear-camera capture with a label-alignment guide.
 *
 * MOBILE CONSTRAINTS THAT SHAPE THIS COMPONENT
 * - `navigator.mediaDevices` is only defined in a **secure context**
 *   (https:// or localhost). On a phone pointed at http://192.168.x.x it is
 *   `undefined`, not merely blocked, so this must be feature-detected rather
 *   than relying on the permission error path.
 * - Permission can be denied outright, or there may be no camera at all.
 * - The stream must be stopped on unmount or the camera indicator light
 *   stays on and the battery drains.
 *
 * Because of all three, there is always a file-input fallback: a vendor who
 * cannot use the live camera can still photograph the label with their
 * normal camera app and pick the file.
 */

type CameraState = "idle" | "requesting" | "live" | "denied" | "unavailable";

interface CameraCaptureProps {
  onCapture: (image: Blob) => void;
  /** Disables the shutter while an upload is in flight. */
  busy?: boolean;
  /** Shown over the viewfinder while busy. */
  busyLabel?: string;
}

/** Longest edge, in pixels, that a capture is downscaled to before upload. */
const MAX_CAPTURE_EDGE = 1600;

const JPEG_QUALITY = 0.92;

export default function CameraCapture({
  onCapture,
  busy = false,
  busyLabel = "Reading label…",
}: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [state, setState] = useState<CameraState>("idle");
  const [error, setError] = useState<string | null>(null);

  const stopStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    // Feature detection first: in an insecure context `mediaDevices` is
    // simply undefined, and calling into it would throw a TypeError that
    // looks like a bug rather than a setup problem.
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setState("unavailable");
      setError(
        "Live camera is not available here. This usually means the page is not being served over HTTPS. You can still take a photo with your camera app and choose the file below."
      );
      return;
    }

    setState("requesting");
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;

      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        // iOS refuses to play inline video without these.
        video.setAttribute("playsinline", "true");
        video.muted = true;
        await video.play().catch(() => {
          /* Autoplay rejection is non-fatal; the poster frame still shows. */
        });
      }

      setState("live");
    } catch (err) {
      stopStream();
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setState("denied");
        setError(
          "Camera access was blocked. Allow camera access for this site in your browser settings, or choose a photo from your gallery below."
        );
      } else if (name === "NotFoundError" || name === "OverconstrainedError") {
        setState("unavailable");
        setError(
          "No suitable camera was found on this device. You can choose a photo from your gallery below."
        );
      } else {
        setState("unavailable");
        setError(
          "The camera could not be started. You can choose a photo from your gallery below."
        );
      }
    }
  }, [stopStream]);

  // Release the camera when the component goes away. Without this the
  // hardware stays open and the phone keeps showing the camera indicator.
  useEffect(() => {
    return () => stopStream();
  }, [stopStream]);

  const handleCapture = useCallback(async () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || busy) return;

    const longest = Math.max(video.videoWidth, video.videoHeight);
    const scale =
      longest > MAX_CAPTURE_EDGE ? MAX_CAPTURE_EDGE / longest : 1;
    const width = Math.round(video.videoWidth * scale);
    const height = Math.round(video.videoHeight * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(video, 0, 0, width, height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY)
    );
    if (blob) onCapture(blob);
  }, [busy, onCapture]);

  const handleFilePicked = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) onCapture(file);
      // Reset so picking the same file twice still fires onChange.
      event.target.value = "";
    },
    [onCapture]
  );

  const galleryInput = (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFilePicked}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={busy}
        className="w-full rounded-full border border-border-default/20 bg-white px-4 py-3 text-sm font-bold text-text-primary disabled:opacity-60 font-['Plus_Jakarta_Sans']"
      >
        Upload from Gallery
      </button>
    </>
  );

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-black overflow-y-auto h-[100dvh]">
      {/* Viewfinder */}
      <div className="relative flex-1 min-h-[50vh] overflow-hidden">
        <video
          ref={videoRef}
          playsInline
          muted
          autoPlay
          className="absolute inset-0 h-full w-full object-cover"
        />

        {/* Label-alignment guide. The cutout is drawn with a huge spread
            box-shadow rather than four overlay divs: it dims everything
            outside the frame in one element and keeps the corners fixed to
            the frame at any viewport size. */}
        {state === "live" && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6">
            <div
              className="relative w-full max-w-sm rounded-2xl"
              style={{ aspectRatio: "4 / 3", boxShadow: "0 0 0 9999px rgba(0,0,0,0.6)" }}
            >
              {/* Corner brackets */}
              <span className="absolute -left-1 -top-1 h-8 w-8 rounded-tl-2xl border-l-4 border-t-4 border-white" />
              <span className="absolute -right-1 -top-1 h-8 w-8 rounded-tr-2xl border-r-4 border-t-4 border-white" />
              <span className="absolute -bottom-1 -left-1 h-8 w-8 rounded-bl-2xl border-b-4 border-l-4 border-white" />
              <span className="absolute -bottom-1 -right-1 h-8 w-8 rounded-br-2xl border-b-4 border-r-4 border-white" />
            </div>
            <p className="mt-6 max-w-xs text-center text-sm font-medium text-white drop-shadow">
              Fit the ingredient list inside the frame
            </p>
            <p className="mt-1 max-w-xs text-center text-xs text-white/70">
              Hold steady and make sure there is no glare on the packet
            </p>
          </div>
        )}

        {/* Busy overlay */}
        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-white/30 border-t-white" />
            <p className="mt-4 text-sm font-medium text-white">{busyLabel}</p>
            <p className="mt-1 text-xs text-white/70">
              Reading the label and checking ingredients
            </p>
          </div>
        )}
      </div>

      {/* Controls — kept in the thumb zone at the bottom */}
      <div
        className="shrink-0 bg-black px-6 pb-6 pt-4"
        style={{ paddingBottom: "calc(1.5rem + env(safe-area-inset-bottom))" }}
      >
        {error && (
          <p
            role="alert"
            className="mb-4 rounded-xl bg-white/10 px-3 py-2 text-center text-sm text-white/90"
          >
            {error}
          </p>
        )}

        {state === "idle" && (
          <button
            type="button"
            onClick={startCamera}
            className="w-full rounded-full bg-surface-dark px-4 py-4 text-base font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
          >
            Open camera
          </button>
        )}

        {state === "requesting" && (
          <p className="py-4 text-center text-sm text-white/70">
            Starting camera…
          </p>
        )}

        {state === "live" && (
          <button
            type="button"
            onClick={handleCapture}
            disabled={busy}
            aria-label="Capture label photo"
            className="mx-auto flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-white/20 disabled:opacity-50"
          >
            <span className="h-14 w-14 rounded-full bg-white" />
          </button>
        )}

        {(state === "denied" || state === "unavailable") && (
          <button
            type="button"
            onClick={startCamera}
            className="mb-3 w-full rounded-full bg-surface-dark px-4 py-3 text-sm font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
          >
            Try the camera again
          </button>
        )}

        {/* The gallery fallback is always reachable — it is also the only
            route that works on an insecure origin. */}
        <div className={state === "live" ? "mt-4" : ""}>{galleryInput}</div>
      </div>
    </div>
  );
}
