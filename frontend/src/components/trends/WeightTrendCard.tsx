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
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.headline}</div>
        {data.bcs && (
          <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 8, background: "var(--ta)", color: "#9a5800" }}>
            BCS {data.bcs}
          </span>
        )}
      </div>
      <div style={{ marginTop: 14 }}>
        <LineChart
          points={points.map((point, index) => {
            const isLast = index === points.length - 1;
            return {
              label: isLast ? "Now" : formatAxisDate(point.date),
              val: point.value,
              display: isLast ? `${point.value}kg` : `${point.value}`,
              color: isLast ? (point.alert !== false ? "#FF3B30" : "#FF9F1C") : undefined,
            };
          })}
        />
      </div>
      <div style={{ marginTop: 10, padding: "9px 12px", background: "var(--ta)", borderRadius: 10, fontSize: 12, color: "#9a5800", lineHeight: 1.5 }}>
        💡 {data.recommendation}
      </div>
    </div>
  );
}