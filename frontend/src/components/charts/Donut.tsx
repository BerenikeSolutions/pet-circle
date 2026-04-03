"use client";

/** Color map for nutritional status — matches nutrColor in PetDashboard_3103_4.jsx. */
const NUTR_COLOR: Record<string, string> = {
  green: "#34C759",
  amber: "#FF9F1C",
  red: "#FF3B30",
};

/** Stroke width for the ring, fixed at 7px matching the JSX reference. */
const STROKE_WIDTH = 7;

interface DonutProps {
  /** Percentage to fill (0–100+). Values above 100 are shown as full ring. */
  pct: number;
  /** Status key: "green" | "amber" | "red". Falls back to grey for unknown values. */
  status: string;
  /** Overall size in px. Default 80, dashboard uses 64. */
  size?: number;
}

/**
 * Circular SVG ring chart showing a percentage of a nutritional requirement.
 * Renders "pct%" in the centre with an "of need" sub-label.
 * Matches the Donut component in PetDashboard_3103_4.jsx pixel-for-pixel.
 */
export default function Donut({ pct, status, size = 80 }: DonutProps) {
  const sw = STROKE_WIDTH;
  const r = (size - sw * 2) / 2;
  const circ = 2 * Math.PI * r;
  const fill = circ * (Math.min(pct, 100) / 100);
  const cx = size / 2;
  const color = NUTR_COLOR[status] ?? "#8A8A8A";

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Background track */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke="#E8E4DF"
        strokeWidth={sw}
      />
      {/* Filled arc — starts at 12 o'clock via rotate(-90) */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={sw}
        strokeDasharray={`${fill} ${circ - fill}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`}
      />
      {/* Percentage value */}
      <text
        x={cx}
        y={cx - 3}
        textAnchor="middle"
        fontFamily="DM Sans,sans-serif"
        fontSize="11"
        fontWeight="700"
        fill="#1A1A1A"
      >
        {pct}%
      </text>
      {/* "of need" sub-label */}
      <text
        x={cx}
        y={cx + 9}
        textAnchor="middle"
        fontFamily="DM Sans,sans-serif"
        fontSize="9"
        fill="#8A8A8A"
      >
        of need
      </text>
    </svg>
  );
}
