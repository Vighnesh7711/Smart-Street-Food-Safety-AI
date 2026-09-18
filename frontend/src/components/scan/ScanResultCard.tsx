"use client";

import { useState } from "react";

import type { ScanResult, ScanStatus } from "@/lib/types";

/**
 * The scan verdict card.
 *
 * Tailwind class names are written out in full in the maps below rather
 * than composed by interpolation (`` `bg-${color}-100` ``). Tailwind v4
 * scans source text for complete class strings, so an interpolated name is
 * never generated and the colours would silently not exist in the build.
 */

interface StatusStyle {
  badge: string;
  accent: string;
  icon: string;
  headline: string;
}

const STATUS_STYLES: Record<ScanStatus, StatusStyle> = {
  Suitable: {
    badge: "bg-[#35C56D]/15 text-[#0B4516] ring-[#35C56D]/30",
    accent: "border-[#35C56D]",
    icon: "✓",
    headline: "Suitable",
  },
  "Potential concern": {
    badge: "bg-[#F59E0B]/15 text-[#10220F] ring-[#F59E0B]/40",
    accent: "border-[#F59E0B]",
    icon: "!",
    headline: "Potential concern",
  },
  "Application mismatch": {
    badge: "bg-[#E53935]/15 text-[#E53935] ring-[#E53935]/30",
    accent: "border-[#E53935]",
    icon: "✕",
    headline: "Application mismatch",
  },
  "Insufficient information": {
    badge: "bg-surface-soft text-text-primary/60 ring-border-default/10",
    accent: "border-text-primary/40",
    icon: "?",
    headline: "Insufficient information",
  },
  "Needs review": {
    badge: "bg-[#FFE714]/30 text-[#10220F] ring-[#FFE714]/50",
    accent: "border-[#FFE714]",
    icon: "↻",
    headline: "Needs review",
  },
};

/** Fallback so an unknown status from a newer backend still renders. */
const UNKNOWN_STYLE: StatusStyle = {
  badge: "bg-surface-soft text-text-primary/60 ring-border-default/10",
  accent: "border-text-primary/40",
  icon: "?",
  headline: "Result",
};

function ConfidenceMeter({ value }: { value: number }) {
  const percent = Math.round(Math.max(0, Math.min(1, value)) * 100);
  // Three bands rather than a continuous colour: a vendor reads this at a
  // glance, and "is this reading trustworthy" is the only question it needs
  // to answer.
  const bar =
    percent >= 70 ? "bg-[#35C56D]" : percent >= 45 ? "bg-[#F59E0B]" : "bg-[#E53935]";

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-bold text-text-primary/50 font-['Plus_Jakarta_Sans'] uppercase tracking-widest">
          Reading confidence
        </span>
        <span className="text-xs font-semibold text-text-primary/70 font-['Inter']">{percent}%</span>
      </div>
      <div
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-border-default/10"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Reading confidence"
      >
        <div className={`h-full ${bar}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function ScanResultCard({
  result,
  onRetake,
  onScanAnother,
  onCompare,
}: {
  result: ScanResult;
  onRetake: () => void;
  onScanAnother: () => void;
  onCompare?: () => void;
}) {
  const [showEnglish, setShowEnglish] = useState(false);

  const style = STATUS_STYLES[result.status] ?? UNKNOWN_STYLE;
  const hasTranslation =
    result.explanation_translated !== result.explanation &&
    result.language_code !== "en";

  // The translated text is primary; the toggle reveals the canonical English
  // so a vendor can check the wording against what a reviewer will see.
  const body = showEnglish ? result.explanation : result.explanation_translated;

  return (
    <div className="p-5 pb-8">
      {/* Status */}
      <div className={`border-l-4 ${style.accent} pl-4`}>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${style.badge}`}
        >
          <span aria-hidden="true">{style.icon}</span>
          {style.headline}
        </span>
      </div>

      {/* Translation fallback notice. Only shown when translation actually
          failed, not when the vendor's language is English. */}
      {result.translation_failed && (
        <p className="mt-4 rounded-xl bg-[#FFE714]/15 px-3 py-2 text-[11px] font-medium text-[#10220F] ring-1 ring-inset ring-[#FFE714]/30 font-['Inter']">
          Translation is unavailable right now — showing the original English.
        </p>
      )}

      {/* Explanation */}
      <div className="mt-5">
        <p className="whitespace-pre-line text-[15px] leading-relaxed text-text-primary font-['Inter']">
          {body}
        </p>

        {hasTranslation && (
          <button
            type="button"
            onClick={() => setShowEnglish((previous) => !previous)}
            aria-pressed={showEnglish}
            className="mt-3 text-sm font-bold text-surface-dark underline font-['Plus_Jakarta_Sans'] hover:text-[#10220F]"
          >
            {showEnglish ? "Show translated version" : "Show original English"}
          </button>
        )}
      </div>

      {/* Advice */}
      {result.recommendations.length > 0 && (
        <div className="mt-5 rounded-xl bg-surface-soft p-4 ring-1 ring-inset ring-border-default/10">
          <h2 className="text-sm font-extrabold text-text-primary font-['Plus_Jakarta_Sans']">
            What you can do
          </h2>
          <ul className="mt-3 space-y-2">
            {result.recommendations.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-text-primary/70 font-['Inter'] font-medium">
                <span aria-hidden="true" className="text-surface-dark font-bold">
                  •
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Retake prompt. Driven by the server's retake_required flag rather
          than the status string, so adding a status cannot silently change
          whether this prompt appears. */}
      {result.retake_required && (
        <button
          type="button"
          onClick={onRetake}
          className="mt-5 w-full rounded-full bg-surface-dark px-4 py-3 text-sm font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
        >
          Retake photo
        </button>
      )}

      {/* Matched ingredients */}
      {result.matched_ingredients.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-extrabold text-text-primary font-['Plus_Jakarta_Sans']">
            Ingredients recognised
            <span className="ml-1 font-bold text-text-primary/40 font-['Inter']">
              ({result.matched_ingredients.length})
            </span>
          </h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {result.matched_ingredients.map((ingredient) => {
              const risky =
                ingredient.risk_level === "high" ||
                ingredient.risk_level === "moderate";
              return (
                <li
                  key={ingredient.ingredient_id}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-inset font-['Inter'] ${
                    risky
                      ? "bg-[#F59E0B]/15 text-[#10220F] ring-[#F59E0B]/40"
                      : "bg-surface-soft text-text-primary/70 ring-border-default/10"
                  }`}
                  title={`Matched "${ingredient.matched_text ?? ""}" via ${
                    ingredient.match_method
                  }`}
                >
                  {ingredient.canonical_name}
                  {ingredient.match_method === "fuzzy" && (
                    // Surfaced deliberately: a fuzzy match is the likeliest
                    // place for a wrong verdict to originate.
                    <span className="ml-1 text-[#F59E0B] font-bold">≈</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Diagnostics */}
      <div className="mt-8 space-y-3 rounded-xl bg-surface-soft p-5 ring-1 ring-inset ring-border-default/10">
        <ConfidenceMeter value={result.confidence_score ?? 0} />
        <dl className="grid grid-cols-3 gap-2 text-center pt-3 mt-3 border-t border-border-default/10">
          {[
            { label: "Text read", value: result.ocr_confidence },
            { label: "Ingredient match", value: result.match_confidence },
            { label: "Rule strength", value: result.rule_strength },
          ].map((metric) => (
            <div key={metric.label}>
              <dt className="text-[10px] leading-tight text-text-primary/40 font-bold uppercase tracking-widest font-['Plus_Jakarta_Sans'] mb-1">
                {metric.label}
              </dt>
              <dd className="text-sm font-semibold text-text-primary/70 font-['Inter']">
                {metric.value === null
                  ? "—"
                  : `${Math.round(metric.value * 100)}%`}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Image problems, when the photo was rejected pre-OCR */}
      {result.image_quality && result.image_quality.issues.length > 0 && (
        <div className="mt-4 rounded-xl bg-surface-soft p-4 text-xs font-medium text-text-primary/70 ring-1 ring-inset ring-border-default/10 font-['Inter']">
          <span className="font-bold text-text-primary font-['Plus_Jakarta_Sans']">Photo issues: </span>
          {result.image_quality.issues.join(", ").replace(/_/g, " ")}
        </div>
      )}

      {/* Ingredient text as read, for verification against the packet */}
      {result.ingredient_text && (
        <details className="mt-5">
          <summary className="cursor-pointer text-sm font-bold text-text-primary/60 font-['Plus_Jakarta_Sans'] hover:text-text-primary transition-colors">
            Text read from the label
          </summary>
          <p className="mt-3 whitespace-pre-line rounded-xl bg-surface-soft p-4 text-[13px] font-medium text-text-primary/70 ring-1 ring-inset ring-border-default/10 font-['Inter'] leading-relaxed">
            {result.ingredient_text}
          </p>
        </details>
      )}

      {onCompare && (
        <button
          type="button"
          onClick={onCompare}
          className="mt-6 w-full rounded-full bg-surface-dark px-4 py-3 text-sm font-bold text-text-inverse font-['Plus_Jakarta_Sans'] shadow-[0_4px_12px_rgba(11,69,22,0.2)]"
        >
          Compare with another product
        </button>
      )}

      <button
        type="button"
        onClick={onScanAnother}
        className="mt-3 w-full rounded-full border border-border-default/20 bg-white px-4 py-3 text-sm font-bold text-text-primary font-['Plus_Jakarta_Sans']"
      >
        Scan another product
      </button>
    </div>
  );
}
