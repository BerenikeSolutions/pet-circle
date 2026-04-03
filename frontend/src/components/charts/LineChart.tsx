"use client";

import { useId } from "react";

// ─── Chart geometry constants ─────────────────────────────────────────────────
/** SVG canvas dimensions matching the platelet/weight charts in the JSX reference. */
const VW = 358;
const VH = 96;
const PAD_L = 20;
const PAD_R = 20;
/** Space at the top for value labels above first/highest point. */
const PAD_T = 14;
/** Space at the bottom for x-axis date labels. */
const PAD_B = 14;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LineChartPoint {
  /** X-axis label displayed below the point (e.g., "Nov'23", "Jun"). */
  label: string;
  /** Numeric value used for vertical positioning. */
  val: number;
  /**
   * Optional display string rendered above the dot.
   * Defaults to `String(val)` if omitted (e.g., "178K" vs 178).
   */
  display?: string;
  /** Optional dot color override for threshold-based charts. */
  color?: string;
}

export interface LineChartProps {
  /** Ordered data points from left (oldest) to right (newest). */
  points: LineChartPoint[];
  /**
   * When provided, a dashed green horizontal reference line is drawn
   * (e.g., 200 for platelet normal threshold of 200K).
   */
  referenceValue?: number;
  /** Label shown alongside the reference line (e.g., "200K normal"). */
  referenceLabel?: string;
  /** Optional override for the line stroke color. */
  strokeColor?: string;
  /** Optional override for the area fill gradient color. */
  fillColor?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Map a numeric value to an SVG y-coordinate within the draw area. */
function toY(val: number, yMin: number, yRange: number): number {
  const drawH = VH - PAD_T - PAD_B;
  return PAD_T + drawH - ((val - yMin) / yRange) * drawH;
}

/** Dot color: last point is always red; others are amber. */
function defaultDotColor(index: number, total: number): string {
  return index === total - 1 ? "#FF3B30" : "#FF9F1C";
}

/**
 * Weight-trend / lab-result line chart — pure SVG, no external dependencies.
 *
 * Renders an amber gradient fill under the line, connects data points with a
 * rounded polyline, and marks the final point red to signal the latest reading.
 * An optional dashed green reference line can be overlaid (e.g., 200K normal
 * for platelet charts).
 *
 * Matches the weight-trend and platelet charts in PetDashboard_3103_4.jsx.
 */
export default function LineChart({
  points,
  referenceValue,
  referenceLabel,
  strokeColor = "#FF9F1C",
  fillColor = "#FF9F1C",
}: LineChartProps) {
  // Stable, unique ID for the SVG gradient — prevents collisions when multiple
  // LineChart instances appear on the same page.
  const uid = useId();
  const gradId = `lc-fill-${uid.replace(/:/g, "")}`;

  if (points.length === 0) return null;

  const vals = points.map((p) => p.val);
  const dataMin = Math.min(...vals);
  const dataMax = Math.max(...vals);

  // Extend the y-range to include the reference line so it stays on-canvas.
  const yMin = referenceValue !== undefined ? Math.min(dataMin, referenceValue) : dataMin;
  const yMax = referenceValue !== undefined ? Math.max(dataMax, referenceValue) : dataMax;
  // Guard against flat data (all same value).
  const yRange = yMax - yMin || 1;

  const n = points.length;
  const drawW = VW - PAD_L - PAD_R;

  // Evenly distribute x positions across the draw width.
  const xs = points.map((_, i) =>
    n === 1 ? PAD_L + drawW / 2 : PAD_L + (i / (n - 1)) * drawW
  );
  const ys = points.map((p) => toY(p.val, yMin, yRange));

  const polylinePoints = xs.map((x, i) => `${x},${ys[i]}`).join(" ");

  // Polygon for the amber gradient fill — closes at the baseline.
  const baseY = VH - PAD_B;
  const polygonPoints = [
    ...xs.map((x, i) => `${x},${ys[i]}`),
    `${xs[n - 1]},${baseY}`,
    `${xs[0]},${baseY}`,
  ].join(" ");

  const refY =
    referenceValue !== undefined ? toY(referenceValue, yMin, yRange) : null;

  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      style={{ width: "100%", display: "block" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={fillColor} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Reference line: dashed green (e.g., platelet normal threshold) */}
      {refY !== null && (
        <>
          <line
            x1={PAD_L}
            y1={refY}
            x2={VW - PAD_R}
            y2={refY}
            stroke="#34C759"
            strokeWidth="1"
            strokeDasharray="4 3"
            opacity="0.5"
          />
          {referenceLabel && (
            <text
              x={VW - PAD_R - 4}
              y={refY - 3}
              textAnchor="end"
              fontFamily="Inter,sans-serif"
              fontSize="9"
              fill="#34C759"
              fontWeight="600"
            >
              {referenceLabel}
            </text>
          )}
        </>
      )}

      {/* Amber gradient fill under the line */}
      <polygon points={polygonPoints} fill={`url(#${gradId})`} />

      {/* Main trend line */}
      <polyline
        points={polylinePoints}
        fill="none"
        stroke={strokeColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Data points with value labels and x-axis labels */}
      {points.map((p, i) => {
        const color = p.color ?? defaultDotColor(i, n);
        const displayVal = p.display ?? String(p.val);
        return (
          <g key={i}>
            <circle
              cx={xs[i]}
              cy={ys[i]}
              r="4"
              fill={color}
              stroke="white"
              strokeWidth="1.5"
            />
            {/* Value above dot */}
            <text
              x={xs[i]}
              y={ys[i] - 6}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="9"
              fill={color}
              fontWeight="600"
            >
              {displayVal}
            </text>
            {/* X-axis date label */}
            <text
              x={xs[i]}
              y={VH - 2}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="8"
              fill="#8A8A8A"
            >
              {p.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
