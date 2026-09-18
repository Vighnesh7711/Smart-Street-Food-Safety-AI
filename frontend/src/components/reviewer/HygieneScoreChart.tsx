"use client";

import { useState } from "react";

import {
  buildChart,
  CHART_BAND_COLOURS,
  CHART_LAYOUT,
  REFERENCE_SCORE,
  shortDate,
  yForScore,
  type ChartInput,
} from "@/lib/chartScale";

/**
 * Hygiene score history.
 *
 * Hand-rolled SVG rather than a charting library: one series over time is
 * genuinely small, and this keeps the dashboard free of a ~150KB dependency.
 *
 * Form follows the visualization method:
 *   - Line + visible markers. The markers are not decoration: hygiene checks
 *     are discrete assessments, and a bare line would imply continuous
 *     measurement between them.
 *   - Single series, so no legend -- the title names it.
 *   - One y-axis. There is only one measure.
 *   - Grid and axis in recessive chrome; text in text tokens, never the
 *     series colour.
 *   - A reference line at the "needs work" boundary, because that is the
 *     line a reviewer is actually looking for.
 */

const COLOURS = {
  line: "#2a78d6",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
  ink: "#0b0b0b",
  reference: "#d03b3b",
  surface: "#ffffff",
};

export default function HygieneScoreChart({
  history,
}: {
  history: ChartInput[];
}) {
  const [hovered, setHovered] = useState<number | null>(null);

  if (history.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-500 ring-1 ring-inset ring-gray-200">
        No hygiene assessments yet.
      </div>
    );
  }

  const geometry = buildChart(history);
  const referenceY = yForScore(REFERENCE_SCORE);
  const last = geometry.points[geometry.points.length - 1];
  const active = hovered !== null ? geometry.points[hovered] : null;

  return (
    <figure className="rounded-lg bg-white p-4 ring-1 ring-inset ring-gray-200">
      <figcaption className="mb-2 flex items-baseline justify-between">
        <span className="text-sm font-semibold text-gray-900">
          Hygiene score history
        </span>
        <span className="text-xs text-gray-500">
          {history.length} assessment{history.length === 1 ? "" : "s"}
        </span>
      </figcaption>

      <div className="relative">
        <svg
          viewBox={`0 0 ${geometry.width} ${geometry.height}`}
          className="w-full"
          role="img"
          aria-label={`Hygiene score history, ${history.length} assessments, latest ${last.score}`}
          onMouseLeave={() => setHovered(null)}
        >
          {/* Gridlines */}
          {geometry.yTicks.map((tick) => (
            <g key={tick.value}>
              <line
                x1={CHART_LAYOUT.padLeft}
                x2={geometry.width - CHART_LAYOUT.padRight}
                y1={tick.y}
                y2={tick.y}
                stroke={COLOURS.grid}
                strokeWidth={1}
              />
              <text
                x={CHART_LAYOUT.padLeft - 8}
                y={tick.y + 4}
                textAnchor="end"
                fontSize={11}
                fill={COLOURS.muted}
              >
                {tick.value}
              </text>
            </g>
          ))}

          {/* Reference line at the "needs work" boundary */}
          <line
            x1={CHART_LAYOUT.padLeft}
            x2={geometry.width - CHART_LAYOUT.padRight}
            y1={referenceY}
            y2={referenceY}
            stroke={COLOURS.reference}
            strokeWidth={1}
            strokeDasharray="4 4"
            opacity={0.7}
          />
          <text
            x={geometry.width - CHART_LAYOUT.padRight}
            y={referenceY - 5}
            textAnchor="end"
            fontSize={10}
            fill={COLOURS.reference}
          >
            Needs work below {REFERENCE_SCORE}
          </text>

          {/* Crosshair for the hovered point */}
          {active && (
            <line
              x1={active.x}
              x2={active.x}
              y1={CHART_LAYOUT.padTop}
              y2={geometry.height - CHART_LAYOUT.padBottom}
              stroke={COLOURS.axis}
              strokeWidth={1}
            />
          )}

          {/* The series. 2px line, per the mark spec. */}
          {geometry.points.length > 1 && (
            <path
              d={geometry.linePath}
              fill="none"
              stroke={COLOURS.line}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {/* Markers. Radius 5 gives a 10px target, above the 8px floor. */}
          {geometry.points.map((point) => (
            <g key={point.index}>
              {/* Invisible hit target, larger than the mark. */}
              <circle
                cx={point.x}
                cy={point.y}
                r={14}
                fill="transparent"
                onMouseEnter={() => setHovered(point.index)}
                style={{ cursor: "pointer" }}
              />
              <circle
                cx={point.x}
                cy={point.y}
                r={hovered === point.index ? 6 : 5}
                fill={CHART_BAND_COLOURS[point.band]}
                stroke={COLOURS.surface}
                strokeWidth={2}
              />
            </g>
          ))}

          {/* Direct-label the most recent point only, never every point. */}
          <text
            x={last.x}
            y={last.y - 12}
            textAnchor="middle"
            fontSize={12}
            fontWeight={600}
            fill={COLOURS.ink}
          >
            {Math.round(last.score)}
          </text>

          {/* First and last dates only: labelling every point collides. */}
          <text
            x={geometry.points[0].x}
            y={geometry.height - 6}
            textAnchor="start"
            fontSize={11}
            fill={COLOURS.muted}
          >
            {shortDate(geometry.points[0].at)}
          </text>
          {geometry.points.length > 1 && (
            <text
              x={last.x}
              y={geometry.height - 6}
              textAnchor="end"
              fontSize={11}
              fill={COLOURS.muted}
            >
              {shortDate(last.at)}
            </text>
          )}
        </svg>

        {/* Tooltip */}
        {active && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-md bg-gray-900 px-2.5 py-1.5 text-xs text-white shadow-lg"
            style={{
              left: `${(active.x / geometry.width) * 100}%`,
              top: `${(active.y / geometry.height) * 100}%`,
              marginTop: "-3rem",
            }}
          >
            <div className="font-semibold tabular-nums">{active.score} / 100</div>
            <div className="text-white/70">
              {new Date(active.at ?? "").toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </div>
          </div>
        )}
      </div>

      {/* The table is not a fallback for the chart -- it is the exact numbers
          a reviewer needs when acting on a score, and it is what makes the
          chart accessible without relying on colour. */}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-gray-600">
          Show all assessments as a table
        </summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-gray-500">
            <tr>
              <th scope="col" className="py-1 font-medium">
                Date
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Score
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Photos
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Checklist
              </th>
            </tr>
          </thead>
          <tbody className="text-gray-700">
            {history.map((entry, index) => (
              <tr key={index} className="border-t border-gray-100">
                <td className="py-1 tabular-nums">
                  {new Date(entry.at ?? "").toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </td>
                <td className="py-1 text-right font-medium tabular-nums">
                  {entry.score.toFixed(1)}
                </td>
                <td className="py-1 text-right tabular-nums text-gray-500">
                  {(entry as ChartInput & { visual_score?: number }).visual_score?.toFixed(1) ??
                    "—"}
                </td>
                <td className="py-1 text-right tabular-nums text-gray-500">
                  {(entry as ChartInput & { checklist_score?: number | null })
                    .checklist_score?.toFixed(1) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
