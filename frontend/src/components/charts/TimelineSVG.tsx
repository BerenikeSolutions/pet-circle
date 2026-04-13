"use client";

// ─── Chart geometry constants ─────────────────────────────────────────────────
/** SVG canvas width, matches vaccine cadence chart in JSX reference. */
const VW = 358;
/** Canvas pad left/right so edge circles don't clip. */
const PAD = 20;
/** Y-position of the connecting line and circle centres. */
const LINE_Y = 54;
/** Node circle radius. */
const NODE_R = 13;
/** Y start of primary label below node (date / round number). */
const LABEL_Y = LINE_Y + NODE_R + 14;
/** Y start of secondary sub-label below node (vaccine names). */
const SUB_Y = LABEL_Y + 13;
/** Y start of the legend area. */
const LEGEND_Y = SUB_Y + 22;
/** Height of each legend row. */
const LEGEND_ROW_H = 20;

// ─── Node-type visual rules ───────────────────────────────────────────────────
// Matches the vaccination and deworming timelines in PetDashboard_3103_4.jsx.

interface NodeStyle {
  fill: string;
  stroke: string;
  strokeWidth: number;
  strokeDasharray?: string;
  textFill: string;
}

const NODE_STYLE: Record<string, NodeStyle> = {
  done: {
    fill: "#34C759",
    stroke: "white",
    strokeWidth: 2,
    textFill: "white",
  },
  upcoming: {
    fill: "none",
    stroke: "#8A8A8A",
    strokeWidth: 1.5,
    strokeDasharray: "3 2",
    textFill: "#8A8A8A",
  },
  missed: {
    fill: "none",
    stroke: "#FF3B30",
    strokeWidth: 1.5,
    strokeDasharray: "3 2",
    textFill: "#FF3B30",
  },
  now: {
    fill: "none",
    stroke: "#FF9500",
    strokeWidth: 1.5,
    strokeDasharray: "3 2",
    textFill: "#FF9500",
  },
};

/** Symbol rendered inside the node when no explicit label is given. */
const NODE_SYMBOL: Record<string, string> = {
  done: "✓",
  upcoming: "?",
  missed: "×",
  now: "!",
};

// ─── Types ────────────────────────────────────────────────────────────────────

export type TimelineNodeType = "done" | "upcoming" | "missed" | "now";

export interface TimelineNode {
  /** Short text inside the circle (e.g., "R1", "R2"). Falls back to status symbol. */
  nodeLabel?: string;
  /** Primary date / name label below the circle (e.g., "Mar '23"). */
  label: string;
  /** Optional second line below label (e.g., "DHPPi · RL · R"). */
  sub?: string;
  /** Visual type determining colour and border style. */
  type: TimelineNodeType;
}

export interface TimelineGap {
  /** Gap is between `nodes[afterIndex]` and `nodes[afterIndex + 1]`. */
  afterIndex: number;
  /** Human-readable gap label, e.g., "~13 months". */
  label: string;
}

export interface TimelineLegendItem {
  type: TimelineNodeType;
  label: string;
}

export interface TimelineSVGProps {
  nodes: TimelineNode[];
  /** Optional gap duration labels shown above the connecting line. */
  gaps?: TimelineGap[];
  /** Optional legend rows rendered below the chart. */
  legend?: TimelineLegendItem[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Compute evenly-distributed x-centres for n nodes. */
function nodeXPositions(n: number): number[] {
  if (n === 0) return [];
  if (n === 1) return [PAD];
  return Array.from({ length: n }, (_, i) =>
    PAD + (i / (n - 1)) * (VW - PAD * 2)
  );
}

/** Legend circle for a given node type. */
function LegendDot({
  type,
  cx,
  cy,
}: {
  type: TimelineNodeType;
  cx: number;
  cy: number;
}) {
  const s = NODE_STYLE[type] ?? NODE_STYLE.upcoming;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={6}
      fill={s.fill}
      stroke={s.stroke}
      strokeWidth={s.strokeWidth}
      strokeDasharray={s.strokeDasharray}
    />
  );
}

/**
 * Horizontal node-based timeline for vaccination and deworming cadence.
 *
 * Each node is a circle whose visual style (solid green / dashed grey / dashed
 * red / dashed amber) conveys its status. Optional gap labels float above the
 * connecting line between specified pairs of nodes.
 *
 * Matches the vaccination and deworming cadence charts in
 * PetDashboard_3103_4.jsx.
 */
export default function TimelineSVG({
  nodes,
  gaps = [],
  legend = [],
}: TimelineSVGProps) {
  if (nodes.length === 0) return null;

  const xs = nodeXPositions(nodes.length);
  const legendRows = Math.ceil(legend.length / 2);
  const totalHeight =
    LEGEND_Y + (legend.length > 0 ? legendRows * LEGEND_ROW_H : 0);

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

      {/* Gap labels above the connecting line */}
      {gaps.map((gap, gi) => {
        const fromX = xs[gap.afterIndex];
        const toX = xs[gap.afterIndex + 1];
        if (fromX === undefined || toX === undefined) return null;
        const midX = (fromX + toX) / 2;
        const bracketY = LINE_Y - 26 - gi * 16; // stack multiple brackets upward
        const vertY = bracketY + 5;

        return (
          <g key={gi}>
            {/* Horizontal bracket line */}
            <line
              x1={fromX + NODE_R}
              y1={bracketY}
              x2={toX - NODE_R}
              y2={bracketY}
              stroke="#D0CBC4"
              strokeWidth="0.8"
              strokeDasharray="3 3"
            />
            {/* Left fence post */}
            <line
              x1={fromX + NODE_R}
              y1={bracketY}
              x2={fromX + NODE_R}
              y2={vertY + 8}
              stroke="#D0CBC4"
              strokeWidth="0.8"
              strokeDasharray="3 3"
            />
            {/* Right fence post */}
            <line
              x1={toX - NODE_R}
              y1={bracketY}
              x2={toX - NODE_R}
              y2={vertY + 8}
              stroke="#D0CBC4"
              strokeWidth="0.8"
              strokeDasharray="3 3"
            />
            {/* Gap duration text */}
            <text
              x={midX}
              y={bracketY - 3}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="10"
              fill="#8A8A8A"
            >
              {gap.label}
            </text>
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map((node, i) => {
        const s = NODE_STYLE[node.type] ?? NODE_STYLE.upcoming;
        const innerLabel = node.nodeLabel ?? NODE_SYMBOL[node.type] ?? "";

        return (
          <g key={i}>
            <circle
              cx={xs[i]}
              cy={LINE_Y}
              r={NODE_R}
              fill={s.fill}
              stroke={s.stroke}
              strokeWidth={s.strokeWidth}
              strokeDasharray={s.strokeDasharray}
            />
            <text
              x={xs[i]}
              y={LINE_Y + 4}
              textAnchor="middle"
              fontFamily="Inter,sans-serif"
              fontSize="10"
              fontWeight={node.type === "done" ? "700" : "400"}
              fill={s.textFill}
            >
              {innerLabel}
            </text>
            {/* Primary label below node — adaptive anchor prevents edge clipping */}
            <text
              x={xs[i] < VW / 4 ? PAD / 2 : xs[i] > (3 * VW) / 4 ? VW - PAD / 2 : xs[i]}
              y={LABEL_Y}
              textAnchor={
                xs[i] < VW / 4 ? "start" : xs[i] > (3 * VW) / 4 ? "end" : "middle"
              }
              fontFamily="Inter,sans-serif"
              fontSize="10"
              fontWeight="600"
              fill={node.type === "upcoming" ? "#8A8A8A" : "#1A1A1A"}
            >
              {node.label}
            </text>
            {/* Optional sub-label — adaptive anchor prevents edge clipping */}
            {node.sub && (
              <text
                x={xs[i] < VW / 4 ? PAD / 2 : xs[i] > (3 * VW) / 4 ? VW - PAD / 2 : xs[i]}
                y={SUB_Y}
                textAnchor={
                  xs[i] < VW / 4 ? "start" : xs[i] > (3 * VW) / 4 ? "end" : "middle"
                }
                fontFamily="Inter,sans-serif"
                fontSize="9"
                fill={node.type === "done" ? "#166534" : "#8A8A8A"}
              >
                {node.sub}
              </text>
            )}
          </g>
        );
      })}

      {/* Legend */}
      {legend.map((item, li) => {
        const col = li % 2;
        const row = Math.floor(li / 2);
        const lx = col === 0 ? PAD : VW / 2 + PAD;
        const ly = LEGEND_Y + row * LEGEND_ROW_H + 4;
        return (
          <g key={li}>
            <LegendDot type={item.type} cx={lx + 6} cy={ly} />
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
