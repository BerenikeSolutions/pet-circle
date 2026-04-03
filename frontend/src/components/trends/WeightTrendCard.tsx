"use client";

import type { WeightSignalData } from "@/lib/api";
import LineChart from "@/components/charts/LineChart";
import { formatAxisDate } from "./trend-utils";

interface WeightTrendCardProps {
  data: WeightSignalData;
}

export default function WeightTrendCard({ data }: WeightTrendCardProps) {
  const points = data.points.slice(-5);

  return (
    <div className="card">
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "var(--amber)" }}>
        ⚖️ Weight Trend
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.headline}</div>
      <div style={{ marginTop: 14 }}>
        <LineChart
          points={points.map((point, index) => ({
            label: index === points.length - 1 ? "Now" : formatAxisDate(point.date),
            val: point.value,
            display: index === points.length - 1 ? `${point.value}kg` : `${point.value}`,
          }))}
        />
      </div>
      <div style={{ marginTop: 10, padding: "9px 12px", background: "var(--ta)", borderRadius: 10, fontSize: 12, color: "#9a5800", lineHeight: 1.5 }}>
        💡 {data.recommendation}
      </div>
    </div>
  );
}