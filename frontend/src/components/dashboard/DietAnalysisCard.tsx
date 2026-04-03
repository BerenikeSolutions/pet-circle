"use client";

import { useState } from "react";
import type { DashboardData } from "@/lib/api";
import Donut from "@/components/charts/Donut";
import { macroStatus, normalizeMacros } from "./dashboard-utils";

interface DietAnalysisCardProps {
  data: DashboardData;
}

const NOTE_COLOR: Record<"green" | "amber" | "red", string> = {
  green: "#34C759",
  amber: "#FF9F1C",
  red: "#FF3B30",
};

export default function DietAnalysisCard({ data }: DietAnalysisCardProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const macros = normalizeMacros(data.diet_summary?.macros || []);
  const missingMicros = (data.diet_summary?.missing_micros || []).slice(0, 3);

  return (
    <div className="card">
      <div className="sec-lbl">Diet Analysis</div>

      <div className="donut-grid" style={{ marginBottom: 12 }}>
        {macros.map((macro, index) => {
          const status = macroStatus(macro.name, macro.pct_of_need);
          return (
            <button
              key={macro.name}
              type="button"
              onClick={() => setActiveIndex((prev) => (prev === index ? null : index))}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex((prev) => (prev === index ? null : prev))}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                border: "none",
                background: "transparent",
                cursor: "pointer",
              }}
            >
              <Donut pct={macro.pct_of_need} status={status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t1)", textAlign: "center" }}>{macro.name}</div>
              <div
                style={{
                  minHeight: 20,
                  fontSize: 9,
                  color: NOTE_COLOR[status],
                  fontWeight: 600,
                  textAlign: "center",
                  opacity: activeIndex === index ? 1 : 0,
                  transition: "opacity 0.15s",
                }}
              >
                {macro.note}
              </div>
            </button>
          );
        })}
      </div>

      {missingMicros.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--t3)",
              textTransform: "uppercase",
              letterSpacing: "0.8px",
              marginBottom: 6,
            }}
          >
            Missing micronutrients
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {missingMicros.map((micro) => (
              <span
                key={micro.name}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: "3px 9px",
                  borderRadius: 20,
                  background: "var(--ta)",
                  color: "#b85c00",
                }}
                title={micro.reason}
              >
                {micro.icon} {micro.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
