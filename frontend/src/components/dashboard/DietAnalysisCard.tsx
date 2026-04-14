"use client";

import { useEffect, useState } from "react";
import Donut from "@/components/charts/Donut";
import { macroStatus } from "./dashboard-utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DietAnalysisCardProps {
  token: string;
  compact?: boolean;
}

interface NutritionMacro {
  name: string;
  actual: number;
  target: number;
}

interface NutritionNutrient {
  name: string;
  icon: string;
  status: string;
  priority: string;
  reason?: string | null;
}

interface NutritionAnalysis {
  calories: { actual: number; target: number; status: string };
  macros: NutritionMacro[];
  vitamins: NutritionNutrient[];
  minerals: NutritionNutrient[];
  others: NutritionNutrient[];
  has_diet_items?: boolean;
}

const NOTE_COLOR: Record<"green" | "amber" | "red", string> = {
  green: "#34C759",
  amber: "#FF9F1C",
  red: "#FF3B30",
};

const STATUS_NOTE: Record<string, string> = {
  green: "On track",
  amber: "Slightly over",
  red: "Deficient",
};

const PRIORITY_RANK: Record<string, number> = { urgent: 0, high: 1, medium: 2 };

function safePct(actual: number, target: number): number {
  if (!target) return 100;
  return Math.round(Math.max(0, (actual / target) * 100));
}

export default function DietAnalysisCard({ token, compact = false }: DietAnalysisCardProps) {
  const [nutrition, setNutrition] = useState<NutritionAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/dashboard/${token}/nutrition-analysis`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: NutritionAnalysis | null) => {
        if (!cancelled) {
          setNutrition(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const cal = nutrition?.calories;
  const macrosList = nutrition?.macros ?? [];
  const findMacro = (name: string) => macrosList.find((m) => m.name === name);

  const macros = [
    { name: "Calories", pct: cal ? safePct(cal.actual, cal.target) : 0 },
    {
      name: "Protein",
      pct: (() => {
        const m = findMacro("Protein");
        return m ? safePct(m.actual, m.target) : 0;
      })(),
    },
    {
      name: "Fat",
      pct: (() => {
        const m = findMacro("Fat");
        return m ? safePct(m.actual, m.target) : 0;
      })(),
    },
    {
      name: "Fibre",
      pct: (() => {
        const m = findMacro("Fibre");
        return m ? safePct(m.actual, m.target) : 0;
      })(),
    },
  ];

  // Order must match backend get_diet_summary: minerals → others → vitamins
  // so the top-3 slice selects the same nutrients as the supplement cards.
  const allNutrients: NutritionNutrient[] = [
    ...(nutrition?.minerals ?? []),
    ...(nutrition?.others ?? []),
    ...(nutrition?.vitamins ?? []),
  ];

  const missingMicros = allNutrients
    .filter((n) => n.priority in PRIORITY_RANK)
    .sort((a, b) => (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3))
    .slice(0, 3);

  const hasAnyMacroValue = macros.some((m) => m.pct > 0);

  if (loading) return null;

  if (!nutrition || !hasAnyMacroValue) {
    const hasDietItems = nutrition?.has_diet_items ?? false;
    return (
      <div className={compact ? undefined : "card"}>
        <div className="sec-lbl">Diet Analysis</div>
        <div
          style={{
            color: "var(--t3)",
            fontSize: 13,
            padding: "14px 4px",
            lineHeight: 1.5,
          }}
        >
          {hasDietItems
            ? "Add portion sizes to your food items to see the calorie and macro breakdown."
            : "Not enough diet information yet. Log meals and portion sizes to see the breakdown across calories, protein, fat and fibre."}
        </div>
      </div>
    );
  }

  return (
    <div className={compact ? undefined : "card"}>
      <div className="sec-lbl">Diet Analysis</div>

      <div className="donut-grid" style={{ marginBottom: 12 }}>
        {macros.map((macro) => {
          const hasValue = macro.pct > 0;
          const status = hasValue ? macroStatus(macro.name, macro.pct) : ("none" as const);
          const note = STATUS_NOTE[status] ?? "No data";
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
              <Donut pct={macro.pct} status={status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t1)", textAlign: "center" }}>
                {macro.name}
              </div>
              {hasValue && status !== "none" && (
                <div
                  style={{
                    fontSize: 9,
                    color: NOTE_COLOR[status],
                    fontWeight: 600,
                    textAlign: "center",
                  }}
                >
                  {note}
                </div>
              )}
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
                  title={micro.reason ?? undefined}
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
