"use client";

import type { MetabolicData } from "@/lib/api";

interface MetabolicCardProps {
  data: MetabolicData;
}

export default function MetabolicCard({ data }: MetabolicCardProps) {
  return (
    <div className="card">
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "var(--green)" }}>
        ⚗️ Metabolic · Organ Health
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.headline}</div>
      <div style={{ fontSize: 12, color: "var(--t3)", lineHeight: 1.5, marginTop: 4 }}>{data.sub}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 14 }}>
        {data.stats.slice(0, 4).map((stat) => (
          <div
            key={stat.label}
            style={{
              background: "var(--tg)",
              border: "1px solid #C3E6CB",
              borderRadius: 10,
              padding: "12px 10px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--green)" }}>{stat.value}</div>
            {stat.unit && <div style={{ fontSize: 9, color: "#4a9a63", fontWeight: 400, marginTop: 1 }}>{stat.unit}</div>}
            <div style={{ fontSize: 10, color: "#2e7d4a", fontWeight: 500, marginTop: stat.unit ? 2 : 4 }}>{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}