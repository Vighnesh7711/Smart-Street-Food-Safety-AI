"use client";

import { bandStyle, severityStyle } from "@/lib/hygieneStyles";
import { resolveImageUrl } from "@/lib/api";
import type { HygieneCheck, ScoreBand } from "@/lib/types";

/**
 * Hygiene result screen content: score, findings, checklist, disclaimer.
 *
 * The "AI-assisted, not an official certification" note is rendered here
 * unconditionally rather than being dismissible or tucked into a details
 * element. A vendor showing this screen to a customer or an officer must
 * never be able to present it as a certificate, and the backend also ships
 * the same text in `disclaimer` so an API consumer cannot drop it silently.
 */

function ScoreDial({ score, band }: { score: number; band: ScoreBand }) {
  const style = bandStyle(band);
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 120 120"
        className="h-36 w-36 -rotate-90"
        role="img"
        aria-label={`Hygiene score ${Math.round(clamped)} out of 100`}
      >
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="12"
          className="stroke-gray-200"
        />
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          className={style.ring}
        />
      </svg>
      <div className="-mt-24 text-center">
        <div className="text-4xl font-bold tabular-nums text-gray-900">
          {Math.round(clamped)}
        </div>
        <div className="text-xs text-gray-500">out of 100</div>
      </div>
      <span
        className={`mt-16 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${style.chip}`}
      >
        <span aria-hidden="true">{style.icon}</span>
        {style.label}
      </span>
    </div>
  );
}

export default function HygieneResultCard({ check }: { check: HygieneCheck }) {
  const score = check.score;
  const band = score?.band ?? "fair";

  return (
    <div className="p-5 pb-8">
      {score ? (
        <ScoreDial score={score.final_score} band={band} />
      ) : (
        <p className="text-center text-gray-500">
          This check has not been scored yet.
        </p>
      )}

      {score && (
        <dl className="mt-6 grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-gray-50 p-3 text-center ring-1 ring-inset ring-gray-200">
            <dt className="text-[11px] text-gray-500">From photos (70%)</dt>
            <dd className="text-lg font-semibold tabular-nums text-gray-900">
              {Math.round(score.visual_score)}
            </dd>
          </div>
          <div className="rounded-xl bg-gray-50 p-3 text-center ring-1 ring-inset ring-gray-200">
            <dt className="text-[11px] text-gray-500">From checklist (30%)</dt>
            <dd className="text-lg font-semibold tabular-nums text-gray-900">
              {score.checklist_score === null
                ? "—"
                : Math.round(score.checklist_score)}
            </dd>
          </div>
        </dl>
      )}

      {/* Findings */}
      <h2 className="mt-8 text-sm font-semibold text-gray-900">
        What we noticed
        {check.indicators_found.length > 0 && (
          <span className="ml-1 font-normal text-gray-400">
            ({check.indicators_found.length})
          </span>
        )}
      </h2>

      {check.indicators_found.length === 0 ? (
        <p className="mt-2 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900 ring-1 ring-inset ring-emerald-200">
          No hygiene concerns were detected in the photos you submitted.
        </p>
      ) : (
        <>
          <ul className="mt-2 space-y-2">
            {check.indicators_found.map((finding) => {
              const viewLabel = finding.view.replace(/_/g, " ");
              const isExpectedHere = finding.penalty === 0;
              return (
                <li
                  key={`${finding.code}-${finding.view}`}
                  className="rounded-xl bg-white p-3 ring-1 ring-inset ring-gray-200"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {finding.display_name}
                      </p>
                      <p className="mt-0.5 text-xs capitalize text-gray-500">
                        in the {viewLabel}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${severityStyle(
                        finding.severity
                      )}`}
                    >
                      {isExpectedHere ? "expected here" : `-${Math.round(finding.penalty)}`}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          
          <h2 className="mt-6 text-sm font-semibold text-gray-900">
            Recommended Actions
          </h2>
          <ul className="mt-2 space-y-2 rounded-xl bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-inset ring-amber-200">
            {Array.from(new Set(check.indicators_found.map(f => {
              switch (f.code) {
                case "uncovered_food": return "Cover exposed food to protect from contamination.";
                case "surface_clutter": return "Clear preparation surface and organize items.";
                case "unclean_surface": return "Clean and sanitize all preparation surfaces.";
                case "bare_hands_food_contact": return "Use gloves or utensils when handling food.";
                case "pest_presence": return "Take immediate pest control measures.";
                case "poor_ventilation": return "Improve ventilation in the cooking area.";
                case "waste_overflow": return "Empty and clean waste bins regularly.";
                case "dirty_utensils": return "Wash utensils thoroughly after each use.";
                default: return `Address the issue: ${f.display_name.toLowerCase()}.`;
              }
            }))).map((recommendation, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-amber-500">•</span>
                <span>{recommendation}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* Photos */}
      <h2 className="mt-8 text-sm font-semibold text-gray-900">
        Your photos
      </h2>
      <ul className="mt-2 grid grid-cols-2 gap-3">
        {check.images.map((image) => {
          const url = resolveImageUrl(image.image_url);
          return (
            <li key={image.id} className="overflow-hidden rounded-xl ring-1 ring-gray-200">
              {url && (
                // Plain <img>: these are user uploads served by the API, not
                // local assets, so next/image would add no optimisation and
                // would need every API host allow-listed.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={url}
                  alt={image.view_display_name}
                  className="h-28 w-full object-cover"
                />
              )}
              <p className="px-2 py-1.5 text-[11px] capitalize text-gray-600">
                {image.view_display_name}
              </p>
            </li>
          );
        })}
      </ul>

      {/* Checklist */}
      {check.checklist.length > 0 && (
        <>
          <h2 className="mt-8 text-sm font-semibold text-gray-900">
            Your answers
          </h2>
          <ul className="mt-2 space-y-1.5">
            {check.checklist.map((row) => (
              <li
                key={row.code}
                className="flex items-start gap-2 text-sm text-gray-700"
              >
                <span
                  aria-hidden="true"
                  className={row.satisfied ? "text-emerald-600" : "text-gray-400"}
                >
                  {row.satisfied ? "✓" : "○"}
                </span>
                <span>{row.label}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* Mandatory advisory notice. Not dismissible. */}
      <p className="mt-8 rounded-xl bg-slate-100 p-4 text-xs leading-relaxed text-slate-700 ring-1 ring-inset ring-slate-300">
        <span className="font-semibold">Please note: </span>
        {check.disclaimer}
      </p>
    </div>
  );
}
