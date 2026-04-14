"use client";

// ─── Chart geometry constants ─────────────────────────────────────────────────
/** SVG canvas width, matches tick/flea cadence chart in JSX reference. */
const VW = 358;
/** SVG canvas height (extended for legend). */
const VH_BASE = 152;
/** Left/right padding so edge dots don't clip. */
const PAD = 14;
/** Y-position of the connecting line and dot centres. */
const LINE_Y = 68;
/** Dot circle radius. */
const DOT_R = 10;
/** Y-position of date labels below dots. */
const DATE_Y = LINE_Y + DOT_R + 14;
/** Y-position of gap-duration labels between consecutive dots (above line). */
const GAP_LABEL_Y = LINE_Y - 18;
/** Y start of critical gap brackets (above gap-duration labels). */
const BRACKET_BASE_Y = LINE_Y - 14;
/** Height step to stack multiple brackets upward. */
const BRACKET_STEP = 16;
/** Y start of legend. */
const LEGEND_Y = DATE_Y + 22;

// ─── Color helpers ────────────────────────────────────────────────────────────

/**
 * Dot fill colour based on gap from the previous dose.
 * Matches the green / amber / red rule described in the task spec.
 */
function gapColor(weeks: number): string {
  if (weeks <= 6) return "#34C759";   // on time
  if (weeks <= 12) return "#FF9500";  // delayed
  return "#FF3B30";                   // critical
}

/**
 * Colour for the small gap-duration text label between consecutive dots.
 * Uses amber-orange for delays beyond 12 weeks, grey for acceptable gaps.
 */
function gapTextColor(weeks: number): string {
  return weeks > 12 ? "#FF9500" : "#8A8A8A";
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DotPlotDose {
  /** Dose number rendered inside the circle. */
  n: number;
  /** X-axis date label. */
  label: string;
  /**
   * Weeks elapsed since the previous dose.
   * Determines the dot colour and gap-duration label colour.
   * Omit for the first dose.
   */
  gapWeeks?: number;
  /**
   * Gap-duration text shown between this dot and the previous one
   * (above the connecting line). E.g., "7w".
   * Defaults to `gapWeeks + "w"` when gapWeeks is provided.
   */
  gapLabel?: string;
  /**
   * When true the dot renders as a dashed grey circle with "?" inside,
   * indicating an upcoming / not-yet-administered dose.
   */
  isUpcoming?: boolean;
}

export interface DotPlotCriticalGap {
  /**
   * Zero-based index of the dose that starts the gap
   * (the gap spans from dose[fromIndex] to dose[toIndex]).
   */
  fromIndex: number;
  toIndex: number;
  /** Label text, e.g., "15w gap". */
  label: string;
}

export interface DotPlotLegendItem {
  fill: string;
  label: string;
  dashed?: boolean;
}

export interface DotPlotSVGProps {
  doses: DotPlotDose[];
  /**
   * Red bracket annotations highlighting critical protection gaps.
   * Stacked upward when multiple brackets overlap.
   */
  criticalGaps?: DotPlotCriticalGap[];
  /**
   * Optional legend rows. If omitted, a default green/amber/red legend
   * matching the JSX reference is rendered.
   */
  legend?: DotPlotLegendItem[];
  /**
   * Pill-style footnote shown beneath the chart
   * (e.g., "⚠ Gaps coincide with Anaplasma reactivation").
   */
  footer?: string;
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

/** Evenly distribute n dots across the usable canvas width. */
function dotXPositions(n: number): number[] {
  if (n === 0) return [];
  if (n === 1) return [PAD];
  return Array.from({ length: n }, (_, i) =>
    PAD + (i / (n - 1)) * (VW - PAD * 2)
  );
}

const DEFAULT_LEGEND: DotPlotLegendItem[] = [
  { fill: "#34C759", label: "≤6w on time" },
  { fill: "#FF9500", label: "7–12w delayed" },
  { fill: "#FF3B30", label: ">12w critical" },
  { fill: "none",    label: "upcoming", dashed: true },
];

/**
 * Dot-plot for tick/flea (or other recurring) dose cadence.
 *
 * Numbered circles are colour-coded by gap duration from the previous dose.
 * Optional red bracket annotations highlight critical protection gaps.
 * Small gap-duration labels float above the connecting line between consecutive
 * dots.
 *
 * Matches the tick & flea prevention cadence chart in
 * PetDashboard_3103_4.jsx.
 */
export default function DotPlotSVG({
  doses,
  criticalGaps = [],
  legend,
  footer,
}: DotPlotSVGProps) {
  if (doses.length === 0) return null;

  const xs = dotXPositions(doses.length);
  const legendItems = legend ?? DEFAULT_LEGEND;
  const legendRows = Math.ceil(legendItems.length / 2);

  // Sort critical gaps ascending by their bracket height so higher (older) gaps
  // get a higher y-offset and don't collide with lower ones.
  const sortedGaps = [...criticalGaps].sort((a, b) => a.fromIndex - b.fromIndex);

  const totalHeight =
    LEGEND_Y + legendRows * 20 + (footer ? 12 : 0) + 8;

  return (
    <svg
      viewBox={`0 0 ${VW} ${totalHeight}`}
      style={{ width: "100%", display: "block" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Connecting line */}
      <line
        x1={xs[0]}
        y1={LINE_Y}
        x2={xs[xs.length - 1]}
        y2={LINE_Y}
        stroke="#E8E4DF"
        strokeWidth="2.5"
        strokeLinecap="round"
      />

      {/* Critical gap bracket annotations */}
      {sortedGaps.map((gap, gi) => {
        const fromX = xs[gap.fromIndex];
        const toX = xs[gap.toIndex];
        if (fromX === undefined || toX === undefined) return null;

        // Stack brackets upward — the first bracket is closest to the dots.
        const bracketY = BRACKET_BASE_Y - gi * BRACKET_STEP;
        const midX = (fromX + toX) / 2;
        const vertBottom = LINE_Y - DOT_R; // top of dot circle

        return (
          <g key={gi}>
            {/* Gap label above bracket */}
            <text
              x={midX}
              y={bracketY - 3}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="10"
              fontWeight="600"
              fill="#FF3B30"
            >
              {gap.label}
            </text>
            {/* Horizontal bracket bar */}
            <line
              x1={fromX}
              y1={bracketY}
              x2={toX}
              y2={bracketY}
              stroke="#FF3B30"
              strokeWidth="0.8"
            />
            {/* Left vertical dashed post */}
            <line
              x1={fromX}
              y1={bracketY}
              x2={fromX}
              y2={vertBottom}
              stroke="#FF3B30"
              strokeWidth="0.8"
              strokeDasharray="2 2"
            />
            {/* Right vertical dashed post */}
            <line
              x1={toX}
              y1={bracketY}
              x2={toX}
              y2={vertBottom}
              stroke="#FF3B30"
              strokeWidth="0.8"
              strokeDasharray="2 2"
            />
          </g>
        );
      })}

      {/* Gap-duration labels between consecutive dots (above line) */}
      {doses.map((dose, i) => {
        if (i === 0) return null; // no label before the first dot
        const gw = dose.gapWeeks;
        const lbl = dose.gapLabel ?? (gw !== undefined ? `${gw}w` : null);
        if (!lbl) return null;
        const midX = (xs[i - 1] + xs[i]) / 2;
        const color = gw !== undefined ? gapTextColor(gw) : "#8A8A8A";
        return (
          <text
            key={i}
            x={midX}
            y={GAP_LABEL_Y}
            textAnchor="middle"
            fontFamily="Inter,sans-serif"
            fontSize="8"
            fill={color}
          >
            {lbl}
          </text>
        );
      })}

      {/* Dose dots */}
      {doses.map((dose, i) => {
        const gw = dose.gapWeeks ?? 0;
        const fill = dose.isUpcoming
          ? "none"
          : i === 0
          ? "#34C759" // first dose is always on-time green
          : gapColor(gw);
        const stroke = dose.isUpcoming ? "#8A8A8A" : "white";
        const strokeWidth = 1.5;
        const strokeDasharray = dose.isUpcoming ? "3 2" : undefined;
        const textFill = dose.isUpcoming ? "#8A8A8A" : "white";
        const innerText = dose.isUpcoming ? "?" : String(dose.n);
        const fontSize = dose.n >= 10 ? "7" : "8";

        return (
          <g key={i}>
            <circle
              cx={xs[i]}
              cy={LINE_Y}
              r={DOT_R}
              fill={fill}
              stroke={stroke}
              strokeWidth={strokeWidth}
              strokeDasharray={strokeDasharray}
            />
            <text
              x={xs[i]}
              y={LINE_Y + 4}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize={fontSize}
              fontWeight="700"
              fill={textFill}
            >
              {innerText}
            </text>
            {/* X-axis date label — adaptive anchor prevents edge clipping */}
            <text
              x={xs[i] < VW / 4 ? PAD / 2 : xs[i] > (3 * VW) / 4 ? VW - PAD / 2 : xs[i]}
              y={DATE_Y}
              textAnchor={
                xs[i] < VW / 4 ? "start" : xs[i] > (3 * VW) / 4 ? "end" : "middle"
              }
              fontFamily="Inter,sans-serif"
              fontSize="8"
              fill={
                dose.isUpcoming
                  ? "#8A8A8A"
                  : gw > 12 && i > 0
                  ? "#FF3B30"
                  : "#8A8A8A"
              }
            >
              {dose.label}
            </text>
          </g>
        );
      })}

      {/* Legend */}
      {legendItems.map((item, li) => {
        const col = li % 2;
        const row = Math.floor(li / 2);
        const lx = col === 0 ? PAD : VW / 2 + PAD;
        const ly = LEGEND_Y + row * 20 + 6;
        return (
          <g key={li}>
            <circle
              cx={lx + 6}
              cy={ly}
              r={6}
              fill={item.fill}
              stroke={item.dashed ? "#8A8A8A" : item.fill === "none" ? "#8A8A8A" : "none"}
              strokeWidth={item.dashed ? 1.5 : 0}
              strokeDasharray={item.dashed ? "3 2" : undefined}
            />
            <text
              x={lx + 16}
              y={ly + 4}
              fontFamily="Inter,sans-serif"
              fontSize="10"
              fill="#4A4A4A"
            >
              {item.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
