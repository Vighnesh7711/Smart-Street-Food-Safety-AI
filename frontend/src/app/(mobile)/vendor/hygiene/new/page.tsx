"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import CameraCapture from "@/components/vendor/CameraCapture";
import ChecklistForm from "@/components/hygiene/ChecklistForm";
import { ApiError, api, resolveImageUrl } from "@/lib/api";
import type { HygieneCheck, HygieneConfig } from "@/lib/types";

/**
 * Guided capture: one screen per required view, then the checklist, then the
 * score.
 *
 *   loading -> needs_stall | capturing -> checklist -> scoring -> results
 *
 * The next view is always taken from the server's `coverage.next_view`
 * rather than tracked locally. That keeps the client from disagreeing with
 * the backend about what is still missing -- including after a retake, a
 * dropped connection, or the vendor backgrounding the app mid-flow.
 */

type Phase = "loading" | "needs_stall" | "capturing" | "checklist" | "scoring" | "done";

export default function NewHygieneCheckPage() {
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>("loading");
  const [config, setConfig] = useState<HygieneConfig | null>(null);
  const [check, setCheck] = useState<HygieneCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  // Guards against a double submit from an impatient double-tap on the
  // capture button, which would otherwise upload the same frame twice.
  const inFlight = useRef(false);

  const bootstrap = useCallback(async () => {
    try {
      const [cfg, me] = await Promise.all([api.hygieneConfig(), api.me()]);
      setConfig(cfg);

      if (me.vendor_id === null) {
        setPhase("needs_stall");
        return;
      }
      const stalls = await api.myStalls();
      if (stalls.length === 0) {
        setPhase("needs_stall");
        return;
      }

      const started = await api.startHygieneCheck(stalls[0].id);
      setCheck(started);
      setPhase(started.coverage.ok ? "checklist" : "capturing");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login?next=/vendor/hygiene/new");
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "Could not start the check."
      );
      setPhase("capturing");
    }
  }, [router]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void bootstrap();
  }, [bootstrap]);

  const handleCapture = useCallback(
    async (image: Blob) => {
      if (!check || inFlight.current) return;
      const view = check.coverage.next_view;
      if (!view) return;

      inFlight.current = true;
      setUploading(true);
      setError(null);

      try {
        const updated = await api.uploadHygieneView({
          checkId: check.id,
          view,
          image,
          fileName: `${view}.jpg`,
        });
        setCheck(updated);
        if (updated.coverage.ok) setPhase("checklist");
      } catch (err) {
        // The duplicate-photo rejection lands here, with a message naming
        // which view the photo already matched.
        setError(
          err instanceof ApiError
            ? err.message
            : "That photo could not be used. Please try again."
        );
      } finally {
        inFlight.current = false;
        setUploading(false);
      }
    },
    [check]
  );

  const handleChecklist = useCallback(
    async (answers: Record<string, boolean>) => {
      if (!check) return;
      setPhase("scoring");
      setError(null);
      try {
        await api.submitHygieneChecklist(check.id, answers);
        await api.completeHygieneCheck(check.id);
        router.replace(`/vendor/hygiene/${check.id}`);
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : "Your photos could not be scored. Please try again."
        );
        setPhase("checklist");
      }
    },
    [check, router]
  );

  // --- No stall ---
  if (phase === "needs_stall") {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-3xl">
          🏪
        </div>
        <h1 className="text-xl font-bold text-gray-900">
          Register your stall first
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Hygiene checks are recorded against your stall.
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

  if (phase === "loading" || !config) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-gray-400">
        Loading…
      </div>
    );
  }

  // --- Scoring in flight (detection + scoring happen server-side) ---
  if (phase === "scoring") {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
        <p className="mt-4 text-sm font-medium text-gray-700">
          Checking your stall…
        </p>
        <p className="mt-1 text-xs text-gray-500">
          Looking at all four photos
        </p>
      </div>
    );
  }

  // --- Checklist ---
  if (phase === "checklist") {
    return (
      <>
        {error && <ErrorBanner message={error} />}
        <ChecklistForm
          items={config.checklist_items}
          submitting={false}
          onSubmit={handleChecklist}
        />
      </>
    );
  }

  // --- Capture ---
  const coverage = check?.coverage;
  const currentView = coverage?.next_view ?? null;
  const viewMeta = config.required_views.find((v) => v.value === currentView);
  const done = coverage?.present.length ?? 0;
  const total = config.required_views.length;

  return (
    <>
      {error && <ErrorBanner message={error} />}

      {/* Progress + prompt, above the viewfinder so the instruction is the
          last thing read before framing the shot. */}
      <div className="pointer-events-none absolute left-0 right-0 top-0 z-[55] mx-auto max-w-md p-4">
        <div className="rounded-2xl bg-black/70 p-3 backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-white/80">
              Step {Math.min(done + 1, total)} of {total}
            </span>
            <div className="flex gap-1" aria-hidden="true">
              {config.required_views.map((view, index) => (
                <span
                  key={view.value}
                  className={`h-1.5 w-6 rounded-full ${
                    index < done ? "bg-emerald-400" : "bg-white/30"
                  }`}
                />
              ))}
            </div>
          </div>
          <p className="mt-2 text-sm font-semibold text-white">
            {viewMeta?.prompt ?? "Photograph your stall"}
          </p>
          <p className="text-xs text-white/70">{viewMeta?.hint}</p>
        </div>

        {/* Completed views, so the vendor can see what is already captured */}
        {check && check.images.length > 0 && (
          <div className="mt-2 flex gap-2">
            {check.images.map((image) => {
              const url = resolveImageUrl(image.image_url);
              return (
                <span
                  key={image.id}
                  className="h-10 w-14 overflow-hidden rounded-md ring-2 ring-emerald-400"
                  title={image.view_display_name}
                >
                  {url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={url}
                      alt={image.view_display_name}
                      className="h-full w-full object-cover"
                    />
                  )}
                </span>
              );
            })}
          </div>
        )}
      </div>

      <CameraCapture
        onCapture={handleCapture}
        busy={uploading}
        busyLabel="Checking photo…"
      />
    </>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="absolute left-0 right-0 top-0 z-[60] mx-auto max-w-md p-4"
    >
      <p className="rounded-xl bg-red-600/95 px-3 py-2 text-sm text-white shadow-lg">
        {message}
      </p>
    </div>
  );
}
