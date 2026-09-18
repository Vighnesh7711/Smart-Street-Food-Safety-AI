/**
 * Chart geometry for the hygiene score history.
 *
 * Pure functions, no React and no DOM, so the maths is unit-testable. That
 * matters more here than it looks: a zero-range domain or a bad index
 * produces a silently blank chart rather than an error, and a blank chart on
 * a compliance dashboard reads as "no data" when the data is right there.
 */

import type { ScoreBand } from "./types";

export interface ChartInput {
  score: number;
  at: string | null;
  band: ScoreBand;
}

export interface ChartPoint extends ChartInput {
  index: number;
  x: number;
  y: number;
}

export interface AxisTick {
  value: number;
  y: number;
}

export interface ChartGeometry {
  width: number;
  height: number;
  points: ChartPoint[];
  linePath: string;
  yTicks: AxisTick[];
  /** Domain actually used, after degenerate-range handling. */
  domain: { min: number; max: number };
}

export const CHART_LAYOUT = {
  width: 640,
  height: 200,
  padLeft: 40,
  padRight: 16,
  padTop: 14,
  padBottom: 26,
} as const;

/**
 * Score domain.
 *
 * Fixed at 0–100 rather than fitted to the data. A hygiene score is bounded
 * and its band boundaries (40/60/80) are what a reviewer reads against, so a
 * fitted axis would exaggerate a 2-point change into a dramatic slope and
 * make the band lines meaningless.
 */
export const SCORE_DOMAIN = { min: 0, max: 100 } as const;

/** Y gridlines, and the boundary the dashboard calls out. */
export const Y_TICK_VALUES = [0, 20, 40, 60, 80, 100] as const;

/** Below this, a stall is in the "needs work" bands. */
export const REFERENCE_SCORE = 60;

export function xForIndex(index: number, count: number): number {
  const { width, padLeft, padRight } = CHART_LAYOUT;
  const usable = width - padLeft - padRight;
  if (count <= 1) {
    // A single assessment sits centred rather than pinned to the left edge,
    // which would look like the start of a trend that does not exist.
    return padLeft + usable / 2;
  }
  return padLeft + (usable * index) / (count - 1);
}

export function yForScore(
  score: number,
  domain: { min: number; max: number } = SCORE_DOMAIN
): number {
  const { height, padTop, padBottom } = CHART_LAYOUT;
  const usable = height - padTop - padBottom;

  const span = domain.max - domain.min;
  // Degenerate domain -- every score identical, or an explicit zero-span.
  // Without this the division is by zero and every point becomes NaN, which
  // SVG renders as nothing at all.
  if (span <= 0) return padTop + usable / 2;

  const clamped = Math.max(domain.min, Math.min(domain.max, score));
  return padTop + usable * (1 - (clamped - domain.min) / span);
}

export function buildChart(
  history: ChartInput[],
  domain: { min: number; max: number } = SCORE_DOMAIN
): ChartGeometry {
  const points: ChartPoint[] = history.map((entry, index) => ({
    ...entry,
    index,
    x: xForIndex(index, history.length),
    y: yForScore(entry.score, domain),
  }));

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");

  return {
    width: CHART_LAYOUT.width,
    height: CHART_LAYOUT.height,
    points,
    linePath,
    yTicks: Y_TICK_VALUES.map((value) => ({ value, y: yForScore(value, domain) })),
    domain,
  };
}

/**
 * Box bounding every detection, in the same coordinate space as the boxes.
 *
 * Returns null when nothing has a box, so the caller can fall back to listing
 * findings rather than drawing an empty overlay.
 */
export function unionBox(
  boxes: Array<number[] | null | undefined>
): { x: number; y: number; width: number; height: number } | null {
  const valid = boxes.filter(
    (box): box is number[] => Array.isArray(box) && box.length === 4
  );
  if (valid.length === 0) return null;

  const xs1 = valid.map((box) => box[0]);
  const ys1 = valid.map((box) => box[1]);
  const xs2 = valid.map((box) => box[2]);
  const ys2 = valid.map((box) => box[3]);

  const x = Math.min(...xs1);
  const y = Math.min(...ys1);
  return {
    x,
    y,
    width: Math.max(...xs2) - x,
    height: Math.max(...ys2) - y,
  };
}

/** Short date for an axis label, e.g. "12 Sep". */
export function shortDate(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
}

/**
 * Marker colour by band.
 *
 * The chart deliberately reuses the status palette rather than a series
 * colour: the band IS a status, and a marker coloured like a data series
 * would imply it encodes identity rather than health.
 */
export const CHART_BAND_COLOURS: Record<ScoreBand, string> = {
  good: "#0ca30c",
  fair: "#fab219",
  poor: "#ec835a",
  bad: "#d03b3b",
};
