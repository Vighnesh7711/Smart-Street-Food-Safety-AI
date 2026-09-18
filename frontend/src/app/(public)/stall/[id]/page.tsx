import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { fetchPublicStall } from "@/lib/api";
import { bandStyle } from "@/lib/hygieneStyles";
import type { PublicStallProfile, ScanStatus } from "@/lib/types";

/**
 * Public, unauthenticated stall profile.
 *
 * Server component on purpose: the data is public, so there is no token to
 * attach and nothing sensitive that could reach the client bundle. It also
 * means the page arrives rendered rather than flashing a loading state at
 * someone standing in front of the stall.
 *
 * In Next.js 16 `params` is a Promise and must be awaited.
 *
 * WHAT THIS PAGE MUST NOT DO
 * --------------------------
 * The `id` segment is the stall's random QR code, not its serial id, so
 * stalls cannot be enumerated. Everything shown comes from the backend's
 * allow-list schema (backend/app/schemas/public.py) -- no vendor details, no
 * address, no photographs. If a field is needed here, it has to be added to
 * that allow-list deliberately.
 */

/** Status chip colours for the label-check line. Static strings only:
 * Tailwind v4 scans source text, so an interpolated name would never be
 * generated. */
const SCAN_STATUS_STYLES: Record<ScanStatus, string> = {
  Suitable: "bg-emerald-100 text-emerald-900 ring-emerald-300",
  "Potential concern": "bg-amber-100 text-amber-900 ring-amber-300",
  "Application mismatch": "bg-red-100 text-red-900 ring-red-300",
  "Insufficient information": "bg-slate-200 text-slate-800 ring-slate-300",
  "Needs review": "bg-blue-100 text-blue-900 ring-blue-300",
};

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const profile = await fetchPublicStall(id);
    if (!profile) return { title: "Stall not found" };
    return {
      title: `${profile.stall_name} — Food Safety`,
      description:
        "Hygiene assessment and label-check results for this stall. " +
        "AI-assisted, not an official certification.",
      // A stall profile is public, but there is no reason to have it indexed
      // and turned into a searchable registry of named businesses.
      robots: { index: false, follow: false },
    };
  } catch {
    return { title: "Stall" };
  }
}

function HygienePanel({ profile }: { profile: PublicStallProfile }) {
  const hygiene = profile.hygiene;

  if (!hygiene) {
    return (
      <section className="rounded-2xl bg-slate-50 p-5 ring-1 ring-inset ring-slate-200">
        <h2 className="text-sm font-semibold text-slate-900">
          Hygiene assessment
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          This stall has not been assessed yet.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Assessments are submitted by the vendor and reviewed over time.
        </p>
      </section>
    );
  }

  const style = bandStyle(hygiene.band);
  const assessed = formatDate(hygiene.assessed_at);

  return (
    <section className="rounded-2xl bg-white p-5 ring-1 ring-inset ring-gray-200">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">
            Hygiene assessment
          </h2>
          {assessed && (
            <p className="mt-1 text-xs text-gray-500">
              Assessed {assessed}
            </p>
          )}
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold tabular-nums text-gray-900">
            {Math.round(hygiene.score)}
          </div>
          <div className="text-[11px] text-gray-500">out of 100</div>
        </div>
      </div>

      <span
        className={`mt-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${style.chip}`}
      >
        <span aria-hidden="true">{style.icon}</span>
        {style.label}
      </span>

      {/* Note what is NOT here: no interpretation, no "excellent standards".
          The score is one assessment on one date, and the page says exactly
          that rather than characterising the stall. */}
      <p className="mt-3 text-xs leading-relaxed text-gray-500">
        Based on the vendor&apos;s most recent submitted photos. This is one
        assessment, not a rating of the food.
      </p>
    </section>
  );
}

import ReportConcernForm from "@/components/consumer/ReportConcernForm";

export default async function StallPublicProfile({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let profile: PublicStallProfile | null = null;
  let failed = false;

  try {
    profile = await fetchPublicStall(id);
  } catch {
    // Distinguish "the backend is unreachable" from "no such stall". Telling
    // someone standing at a stall that it does not exist, when the truth is
    // that our server is down, is a much worse error than showing a retry.
    failed = true;
  }

  // Unknown and revoked codes both land here, with the same page.
  if (!failed && profile === null) notFound();

  if (failed || !profile) {
    return (
      <div className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-3xl">
          ⚠️
        </div>
        <h1 className="text-xl font-bold text-gray-900">
          Could not load this stall
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          The service is temporarily unavailable. Please try again in a moment.
        </p>
      </div>
    );
  }

  const scan = profile.last_scan;
  const scanDate = formatDate(scan?.scanned_at ?? null);

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto w-full max-w-md bg-white shadow-sm">
        {/* Header */}
        <header className="border-b border-gray-100 px-6 pb-6 pt-10">
          <h1 className="text-2xl font-bold text-gray-900">
            {profile.stall_name}
          </h1>
          {profile.food_category && (
            <p className="mt-1 text-sm text-gray-500">
              {profile.food_category}
            </p>
          )}
        </header>

        <div className="space-y-4 px-6 py-6">
          <HygienePanel profile={profile} />

          {/* Last label check */}
          <section className="rounded-2xl bg-white p-5 ring-1 ring-inset ring-gray-200">
            <h2 className="text-sm font-semibold text-gray-900">
              Last label check
            </h2>

            {scan ? (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span
                  className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${
                    SCAN_STATUS_STYLES[scan.status] ??
                    "bg-slate-200 text-slate-800 ring-slate-300"
                  }`}
                >
                  {scan.status}
                </span>
                {scanDate && (
                  <span className="text-xs text-gray-500">{scanDate}</span>
                )}
              </div>
            ) : (
              <p className="mt-2 text-sm text-gray-600">
                No packaged products have been checked yet.
              </p>
            )}

            {/* The product name is deliberately absent — see
                backend/app/schemas/public.py for why. */}
            <p className="mt-3 text-xs leading-relaxed text-gray-500">
              Result of the most recent packaged-product ingredient check.
            </p>
          </section>

          {/* Advisory notice. Rendered unconditionally, not dismissible, and
              also returned by the API so a client cannot omit it. */}
          <p
            role="note"
            className="rounded-2xl bg-slate-100 p-4 text-xs leading-relaxed text-slate-700 ring-1 ring-inset ring-slate-300"
          >
            <span className="font-semibold">Please note: </span>
            {profile.disclaimer}
          </p>
          
          {/* Report Concern Component */}
          <ReportConcernForm stallCode={id} />
        </div>
      </main>
    </div>
  );
}
