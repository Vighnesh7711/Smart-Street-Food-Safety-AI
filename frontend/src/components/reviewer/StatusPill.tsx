"use client";

import type { ReviewBand, ScanStatus } from "@/lib/types";

/**
 * Status rendering for the reviewer dashboard.
 *
 * WHY THIS IS A COMPONENT AND NOT A CSS CLASS
 * -------------------------------------------
 * The visualization guidance is explicit that status colours ship with an
 * icon and a label, never colour alone. Two reasons that matter here
 * specifically:
 *
 *  - Two of the four hygiene band colours sit below 3:1 contrast against a
 *    light surface by design. The icon and the text are what actually carry
 *    the meaning; the colour reinforces it.
 *  - A reviewer scanning a table of 200 rows should not have to distinguish
 *    amber from orange to find the stalls that need attention.
 *
 * Making it a component rather than a convention means a new status display
 * cannot quietly be written as a bare coloured dot.
 *
 * Tailwind class strings are written out in full in the maps below: Tailwind
 * v4 scans source text for complete class names, so an interpolated name is
 * never generated and the colours would silently not exist in the build.
 */

export interface StatusStyle {
  chip: string;
  dot: string;
  icon: string;
  label: string;
}

/** Hygiene band: good / fair / poor / bad, plus "not assessed". */
const BAND_STYLES: Record<ReviewBand, StatusStyle> = {
  good: {
    chip: "bg-[#35C56D]/15 text-[#0B4516] ring-[#35C56D]/30",
    dot: "bg-[#35C56D]",
    icon: "✓",
    label: "Good",
  },
  fair: {
    chip: "bg-[#0B4516]/15 text-[#0B4516] ring-[#0B4516]/30",
    dot: "bg-[#0B4516]",
    icon: "!",
    label: "Fair",
  },
  poor: {
    chip: "bg-[#F59E0B]/15 text-[#10220F] ring-[#F59E0B]/40",
    dot: "bg-[#F59E0B]",
    icon: "▲",
    label: "Needs work",
  },
  bad: {
    chip: "bg-[#E53935]/15 text-[#E53935] ring-[#E53935]/30",
    dot: "bg-[#E53935]",
    icon: "✕",
    label: "Poor",
  },
  none: {
    chip: "bg-surface-soft text-text-primary/60 ring-border-default/10",
    dot: "bg-text-primary/40",
    icon: "—",
    label: "Not assessed",
  },
};

const SCAN_STYLES: Record<ScanStatus, StatusStyle> = {
  Suitable: {
    chip: "bg-[#35C56D]/15 text-[#0B4516] ring-[#35C56D]/30",
    dot: "bg-[#35C56D]",
    icon: "✓",
    label: "Suitable",
  },
  "Potential concern": {
    chip: "bg-[#F59E0B]/15 text-[#10220F] ring-[#F59E0B]/40",
    dot: "bg-[#F59E0B]",
    icon: "!",
    label: "Potential concern",
  },
  "Application mismatch": {
    chip: "bg-[#E53935]/15 text-[#E53935] ring-[#E53935]/30",
    dot: "bg-[#E53935]",
    icon: "✕",
    label: "Application mismatch",
  },
  "Insufficient information": {
    chip: "bg-surface-soft text-text-primary/60 ring-border-default/10",
    dot: "bg-text-primary/40",
    icon: "?",
    label: "Insufficient information",
  },
  "Needs review": {
    chip: "bg-[#FFE714]/30 text-[#10220F] ring-[#FFE714]/50",
    dot: "bg-[#FFE714]",
    icon: "↻",
    label: "Needs review",
  },
};

const UNKNOWN: StatusStyle = {
  chip: "bg-surface-soft text-text-primary/60 ring-border-default/10",
  dot: "bg-text-primary/40",
  icon: "—",
  label: "Unknown",
};

export function bandStyle(band: ReviewBand | null | undefined): StatusStyle {
  return band ? BAND_STYLES[band] ?? UNKNOWN : BAND_STYLES.none;
}

export function scanStyle(status: ScanStatus | null | undefined): StatusStyle {
  return status ? SCAN_STYLES[status] ?? UNKNOWN : UNKNOWN;
}

export function HygieneStatus({
  band,
  score,
}: {
  band: ReviewBand | null | undefined;
  score?: number | null;
}) {
  const style = bandStyle(band);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.chip}`}
    >
      <span aria-hidden="true">{style.icon}</span>
      {/* The label is what carries the meaning; the colour is reinforcement. */}
      <span>{style.label}</span>
      {score !== null && score !== undefined && (
        <span className="font-semibold tabular-nums">{Math.round(score)}</span>
      )}
    </span>
  );
}

export function ScanStatusPill({ status }: { status: ScanStatus | null | undefined }) {
  if (!status) {
    return <span className="text-[11px] font-bold text-text-primary/40 font-['Plus_Jakarta_Sans']">No scans yet</span>;
  }
  const style = scanStyle(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style.chip}`}
    >
      <span aria-hidden="true">{style.icon}</span>
      <span>{style.label}</span>
    </span>
  );
}

export function FlagBadge({ count }: { count: number }) {
  if (count <= 0) {
    return <span className="text-xs text-text-primary/30 font-bold font-['Plus_Jakarta_Sans']">—</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#E53935]/15 px-2.5 py-1 text-[11px] font-bold text-[#E53935] ring-1 ring-inset ring-[#E53935]/30 font-['Plus_Jakarta_Sans']">
      <span aria-hidden="true">⚑</span>
      <span>
        Flagged{count > 1 ? ` (${count})` : ""}
      </span>
    </span>
  );
}

export function ScoreDelta({ delta }: { delta: number | null }) {
  // Null means "no previous assessment", which is not the same as no change.
  if (delta === null || delta === undefined) {
    return <span className="text-[11px] font-bold text-text-primary/40 font-['Plus_Jakarta_Sans']">First check</span>;
  }
  if (delta === 0) {
    return <span className="text-[11px] font-bold text-text-primary/50 font-['Plus_Jakarta_Sans']">No change</span>;
  }
  const improved = delta > 0;
  return (
    <span
      className={`text-[11px] font-bold font-['Plus_Jakarta_Sans'] ${
        improved ? "text-[#35C56D]" : "text-[#E53935]"
      }`}
    >
      <span aria-hidden="true">{improved ? "▲" : "▼"}</span>{" "}
      {improved ? "+" : ""}
      {delta.toFixed(1)} since last check
    </span>
  );
}
