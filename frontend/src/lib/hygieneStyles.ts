import type { ScoreBand } from "./types";

/**
 * Score-band styling, shared by the history list and the results screen.
 *
 * Written as complete class strings in a lookup rather than composed by
 * interpolation (`` `bg-${band}-100` ``). Tailwind v4 scans source text for
 * complete class names, so an interpolated name is never generated and the
 * colours would silently not exist in the build.
 */
export interface BandStyle {
  chip: string;
  bar: string;
  ring: string;
  label: string;
  /** Icon paired with the label so status never reads by colour alone. */
  icon: string;
}

export const BAND_STYLES: Record<ScoreBand, BandStyle> = {
  good: {
    chip: "bg-emerald-100 text-emerald-900 ring-emerald-300",
    bar: "bg-emerald-500",
    ring: "stroke-emerald-500",
    label: "Good",
    icon: "✓",
  },
  fair: {
    chip: "bg-amber-100 text-amber-900 ring-amber-300",
    bar: "bg-amber-500",
    ring: "stroke-amber-500",
    label: "Fair",
    icon: "!",
  },
  poor: {
    chip: "bg-orange-100 text-orange-900 ring-orange-300",
    bar: "bg-orange-500",
    ring: "stroke-orange-500",
    label: "Needs work",
    icon: "▲",
  },
  bad: {
    chip: "bg-red-100 text-red-900 ring-red-300",
    bar: "bg-red-500",
    ring: "stroke-red-500",
    label: "Poor",
    icon: "✕",
  },
};

export function bandStyle(band: ScoreBand | null | undefined): BandStyle {
  return band ? BAND_STYLES[band] : BAND_STYLES.fair;
}

/** Severity → chip styling for indicator rows. */
export const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-50 text-red-800 ring-red-200",
  moderate: "bg-amber-50 text-amber-800 ring-amber-200",
  low: "bg-gray-100 text-gray-700 ring-gray-200",
};

export function severityStyle(severity: string): string {
  return SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.moderate;
}
