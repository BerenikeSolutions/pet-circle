"use client";

// ─── Chart geometry constants ─────────────────────────────────────────────────
/** SVG canvas width, matching pus-cell chart in JSX reference. */
const VW = 358;
/** SVG canvas height. */
const VH = 108;
/** Y-position of the baseline (x-axis). */
const BASE_Y = 88;
/** Fixed bar width in px, matching the JSX reference. */
const BAR_W = 28;
/** Left/right padding so edge bars don't clip. */
const PAD = 11;
/** Maximum drawable bar height (from baseline up to label area). */
const MAX_BAR_H = 66;
/** Minimum bar height for zero/nil values so they remain visible. */
const MIN_BAR_H = 3;

// ─── Color map ────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  red: "#FF3B30",
  amber: "#FF9500",
  green: "#34C759",
};

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BarChartBar {
  /** X-axis label shown below the bar (e.g., "Dec'23", "Feb 26"). */
  label: string;
  /**
   * Numeric value used to determine bar height.
   * Use the midpoint or upper bound of a range (e.g., 8 for "7–8 HPF").
   */
  val: number;
  /** Text rendered above the bar (e.g., "7–8", "nil"). */
  display: string;
  /** Colour bucket: "red" | "amber" | "green". */
  status: "red" | "amber" | "green";
}

export interface BarChartProps {
  /** Ordered bars from left (oldest) to right (newest). */
  bars: BarChartBar[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Compute bar height proportional to maxVal, clamped to MIN/MAX bounds. */
function barHeight(val: number, maxVal: number): number {
  if (maxVal === 0) return MIN_BAR_H;
  return Math.max(MIN_BAR_H, Math.round((val / maxVal) * MAX_BAR_H));
}

/**
 * Vertical bar chart for lab values over time (e.g., pus cells / HPF).
 *
 * Bars are colour-coded by the caller-supplied `status` field.
 * Renders a baseline at BASE_Y, bar heights scaled to the maximum value in
 * the dataset, value labels above each bar, and date labels on the x-axis.
 *
 * Matches the pus-cell bar chart in PetDashboard_3103_4.jsx.
 */
export default function BarChart({ bars }: BarChartProps) {
  if (bars.length === 0) return null;

  const n = bars.length;
  const maxVal = Math.max(...bars.map((b) => b.val), 1);

  // Distribute bar x positions evenly across the canvas.
  const step = n > 1 ? (VW - PAD * 2 - BAR_W) / (n - 1) : 0;
  const barX = (i: number) => PAD + i * step;

  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      style={{ width: "100%", display: "block" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Baseline */}
      <line
        x1="0"
        y1={BASE_Y}
        x2={VW}
        y2={BASE_Y}
        stroke="#E8E4DF"
        strokeWidth="1"
      />

      {bars.map((b, i) => {
        const color = STATUS_COLOR[b.status] ?? "#8A8A8A";
        const h = barHeight(b.val, maxVal);
        const x = barX(i);
        const y = BASE_Y - h;
        const cx = x + BAR_W / 2;

        return (
          <g key={i}>
            {/* Bar */}
            <rect x={x} y={y} width={BAR_W} height={h} rx="3" fill={color} />
            {/* Value label above bar */}
            <text
              x={cx}
              y={y - 3}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="8.5"
              fontWeight="600"
              fill={color}
            >
              {b.display}
            </text>
            {/* X-axis date label */}
            <text
              x={cx}
              y={VH - 6}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="8"
              fill="#8A8A8A"
            >
              {b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
