"use client";

import type { DashboardData } from "@/lib/api";
import Donut from "@/components/charts/Donut";
import { macroStatus, normalizeMacros } from "./dashboard-utils";

interface DietAnalysisCardProps {
  data: DashboardData;
  compact?: boolean;
}

const NOTE_COLOR: Record<"green" | "amber" | "red", string> = {
  green: "#34C759",
  amber: "#FF9F1C",
  red: "#FF3B30",
};

export default function DietAnalysisCard({ data, compact = false }: DietAnalysisCardProps) {
  const macros = normalizeMacros(data.diet_summary?.macros || []);
  const missingMicros = (data.diet_summary?.missing_micros || []).slice(0, 3);

  // Check if any macro has actual data (pct_of_need > 0)
  const hasData = macros.some((macro) => macro.pct_of_need > 0);

  // Hide the entire section if no food data exists
  if (!hasData) {
    return null;
  }

  return (
    <div className={compact ? undefined : "card"}>
      <div className="sec-lbl">Diet Analysis</div>

      <div className="donut-grid" style={{ marginBottom: 12 }}>
        {macros.map((macro) => {
          // Skip rendering macros with 0% data
          if (macro.pct_of_need === 0) {
            return null;
          }

          const status = macroStatus(macro.name, macro.pct_of_need);
          return (
            <div
              key={macro.name}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
              }}
            >
              <Donut pct={macro.pct_of_need} status={status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t1)", textAlign: "center" }}>{macro.name}</div>
              <div
                style={{
                  fontSize: 9,
                  color: NOTE_COLOR[status],
                  fontWeight: 600,
                  textAlign: "center",
                }}
              >
                {macro.note}
              </div>
            </div>
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
            {missingMicros.map((micro) => {
              const capName = micro.name
                ? micro.name.charAt(0).toUpperCase() + micro.name.slice(1)
                : micro.name;
              return (
                <span
                  key={micro.name}
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    padding: "3px 9px",
                    borderRadius: 20,
                    background: "var(--ta)",
                    color: "#b85c00",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                  title={micro.reason}
                >
                  {micro.icon} {capName}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
