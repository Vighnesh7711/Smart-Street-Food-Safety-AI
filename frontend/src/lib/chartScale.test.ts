import { describe, expect, it } from "vitest";

import {
  buildChart,
  CHART_LAYOUT,
  REFERENCE_SCORE,
  shortDate,
  unionBox,
  xForIndex,
  yForScore,
  SCORE_DOMAIN,
} from "./chartScale";
import type { ScoreBand } from "./types";

/**
 * The chart's geometry is the one piece of the dashboard where a mistake
 * produces a silently blank panel rather than an error -- and a blank chart
 * on a compliance screen reads as "no data" when the data is right there.
 */

function point(score: number, band: ScoreBand = "good") {
  return { score, at: "2026-09-12T10:00:00Z", band };
}

describe("yForScore", () => {
  it("maps the domain ends to the plot edges", () => {
    const top = yForScore(100);
    const bottom = yForScore(0);
    expect(top).toBeCloseTo(CHART_LAYOUT.padTop);
    expect(bottom).toBeCloseTo(CHART_LAYOUT.height - CHART_LAYOUT.padBottom);
  });

  it("is inverted: a higher score is a smaller y", () => {
    expect(yForScore(90)).toBeLessThan(yForScore(10));
  });

  it("clamps scores outside the domain into the plot", () => {
    // A score above 100 would otherwise draw outside the SVG viewBox and
    // disappear.
    expect(yForScore(150)).toBeCloseTo(CHART_LAYOUT.padTop);
    expect(yForScore(-50)).toBeCloseTo(
      CHART_LAYOUT.height - CHART_LAYOUT.padBottom
    );
  });

  it("does not divide by zero on a degenerate domain", () => {
    // Every score identical, or an explicit zero-span. Without a guard this
    // is NaN, and NaN coordinates render as nothing at all.
    const result = yForScore(70, { min: 70, max: 70 });
    expect(Number.isFinite(result)).toBe(true);
  });

  it("handles an inverted domain without producing NaN", () => {
    expect(Number.isFinite(yForScore(50, { min: 100, max: 0 }))).toBe(true);
  });
});

describe("xForIndex", () => {
  it("centres a single point rather than pinning it left", () => {
    // Pinned left, one assessment looks like the start of a trend that does
    // not exist.
    const x = xForIndex(0, 1);
    const usable = CHART_LAYOUT.width - CHART_LAYOUT.padLeft - CHART_LAYOUT.padRight;
    expect(x).toBeCloseTo(CHART_LAYOUT.padLeft + usable / 2);
  });

  it("spans the usable width for several points", () => {
    expect(xForIndex(0, 3)).toBeCloseTo(CHART_LAYOUT.padLeft);
    expect(xForIndex(2, 3)).toBeCloseTo(
      CHART_LAYOUT.width - CHART_LAYOUT.padRight
    );
  });

  it("is monotonically increasing", () => {
    const xs = [0, 1, 2, 3, 4].map((i) => xForIndex(i, 5));
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
  });
});

describe("buildChart", () => {
  it("returns an empty geometry for no history", () => {
    const geometry = buildChart([]);
    expect(geometry.points).toEqual([]);
    expect(geometry.linePath).toBe("");
  });

  it("still returns axis ticks for an empty history", () => {
    // The axes are drawn from the fixed domain, not from the data, so an
    // empty chart still renders a frame rather than collapsing.
    expect(buildChart([]).yTicks.length).toBeGreaterThan(0);
  });

  it("produces a finite point for every entry", () => {
    const geometry = buildChart([point(80), point(60), point(70)]);
    for (const p of geometry.points) {
      expect(Number.isFinite(p.x)).toBe(true);
      expect(Number.isFinite(p.y)).toBe(true);
    }
  });

  it("keeps every point inside the plot area", () => {
    const geometry = buildChart([point(0), point(50), point(100)]);
    for (const p of geometry.points) {
      expect(p.y).toBeGreaterThanOrEqual(CHART_LAYOUT.padTop);
      expect(p.y).toBeLessThanOrEqual(
        CHART_LAYOUT.height - CHART_LAYOUT.padBottom
      );
      expect(p.x).toBeGreaterThanOrEqual(CHART_LAYOUT.padLeft);
      expect(p.x).toBeLessThanOrEqual(
        CHART_LAYOUT.width - CHART_LAYOUT.padRight
      );
    }
  });

  it("handles identical scores without producing NaN", () => {
    // A flat line is the common case for a stable stall -- and the case most
    // likely to divide by a zero range.
    const geometry = buildChart([point(75), point(75), point(75)]);
    for (const p of geometry.points) {
      expect(Number.isFinite(p.y)).toBe(true);
    }
    expect(new Set(geometry.points.map((p) => p.y)).size).toBe(1);
  });

  it("builds a path that starts with a move and continues with lines", () => {
    const path = buildChart([point(80), point(60)]).linePath;
    expect(path.startsWith("M")).toBe(true);
    expect(path).toContain("L");
    // Two points, one line segment.
    expect(path.match(/L/g)).toHaveLength(1);
  });

  it("uses the fixed 0-100 domain by default", () => {
    // A fitted axis would turn a 2-point move into a dramatic slope and make
    // the band reference line meaningless.
    expect(buildChart([point(88), point(90)]).domain).toEqual(SCORE_DOMAIN);
  });

  it("places the reference score within the plot", () => {
    const y = yForScore(REFERENCE_SCORE);
    expect(y).toBeGreaterThan(CHART_LAYOUT.padTop);
    expect(y).toBeLessThan(CHART_LAYOUT.height - CHART_LAYOUT.padBottom);
  });
});

describe("unionBox", () => {
  it("returns null when nothing has a box", () => {
    // The caller falls back to listing findings rather than drawing an empty
    // overlay.
    expect(unionBox([])).toBeNull();
    expect(unionBox([null, undefined])).toBeNull();
  });

  it("returns the single box unchanged", () => {
    expect(unionBox([[10, 20, 30, 40]])).toEqual({
      x: 10,
      y: 20,
      width: 20,
      height: 20,
    });
  });

  it("spans multiple boxes", () => {
    expect(unionBox([[10, 20, 30, 40], [50, 60, 90, 100]])).toEqual({
      x: 10,
      y: 20,
      width: 80,
      height: 80,
    });
  });

  it("ignores malformed boxes rather than producing NaN", () => {
    expect(unionBox([[1, 2, 3], null, [0, 0, 10, 10]])).toEqual({
      x: 0,
      y: 0,
      width: 10,
      height: 10,
    });
  });
});

describe("shortDate", () => {
  it("formats a date", () => {
    expect(shortDate("2026-09-12T10:00:00Z")).toMatch(/Sep/);
  });

  it("returns empty for null rather than Invalid Date", () => {
    expect(shortDate(null)).toBe("");
  });
});
