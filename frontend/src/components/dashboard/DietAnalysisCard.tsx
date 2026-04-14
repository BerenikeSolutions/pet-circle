"use client";

import { useEffect, useState } from "react";
import Donut from "@/components/charts/Donut";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MicronutrientGap {
  name: string;
  status: string;
  severity_score: number;
  prescribed?: boolean;
}

interface Improvement {
  title: string;
  detail: string;
  severity: "high" | "medium" | "prescribed";
}

interface NutritionAnalysis {
  calories_per_day?: number;
  calorie_target?: number;
  calorie_gap_pct?: number;
  food_label?: string;
  show_warning?: boolean;
  warning_message?: string;
  prescription_context?: string;
  protein_pct?: number;
  fat_pct?: number;
  carbs_pct?: number;
  fibre_pct?: number;
  micronutrient_gaps?: MicronutrientGap[];
  top_improvements?: Improvement[];
  has_diet_items?: boolean;
}

interface DietAnalysisCardProps {
  token: string;
  compact?: boolean;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const NUTR_COLOR = { green: "#34C759", amber: "#FF9F1C", red: "#FF3B30" };

const AMBER_PILL_BG  = "#FFF3E0";
const AMBER_PILL_TXT = "#b85c00";
const RED_PILL_BG    = "#FFD6D6";
const RED_PILL_TXT   = "#c0392b";

// Map severity_score (0–1) to pill colours
function pillStyle(score: number): { background: string; color: string } {
  return score >= 0.75
    ? { background: RED_PILL_BG, color: RED_PILL_TXT }
    : { background: AMBER_PILL_BG, color: AMBER_PILL_TXT };
}

// Map top_improvements severity to dot colour
function improvementColor(severity: string): string {
  if (severity === "high")       return NUTR_COLOR.red;
  if (severity === "medium")     return NUTR_COLOR.amber;
  if (severity === "prescribed") return "#8A8A8E";
  return NUTR_COLOR.amber;
}

// Nutrient name → display label + icon
const MICRO_META: Record<string, { icon: string; label: string }> = {
  omega_3:     { icon: "🐟", label: "Omega-3" },
  omega_6:     { icon: "🌿", label: "Omega-6" },
  vitamin_e:   { icon: "🫐", label: "Vitamin E" },
  vitamin_d3:  { icon: "☀️", label: "Vitamin D3" },
  glucosamine: { icon: "🦴", label: "Glucosamine" },
  calcium:     { icon: "🦷", label: "Calcium" },
  phosphorus:  { icon: "⚡", label: "Phosphorus" },
  iron:        { icon: "🩸", label: "Iron" },
  zinc:        { icon: "💊", label: "Zinc" },
  taurine:     { icon: "❤️", label: "Taurine" },
  fibre:       { icon: "🌾", label: "Fibre" },
};

// ── Macro helpers ─────────────────────────────────────────────────────────────

interface MacroEntry {
  label: string;
  pct: number;
  status: "green" | "amber" | "red";
  note: string;
}

function deriveMacros(n: NutritionAnalysis): MacroEntry[] {
  const entries = [
    { label: "Protein", pct: Math.round(n.protein_pct ?? 0) },
    { label: "Fat",     pct: Math.round(n.fat_pct     ?? 0) },
    { label: "Carbs",   pct: Math.round(n.carbs_pct   ?? 0) },
    { label: "Fibre",   pct: Math.round(n.fibre_pct   ?? 0) },
  ];

  return entries
    .filter((m) => m.pct != null && !isNaN(m.pct) && m.pct > 0)
    .map((m) => {
      let status: "green" | "amber" | "red" = "green";
      let note = "On track";
      if (m.pct < 70)        { status = "red";   note = "Too low"; }
      else if (m.pct < 85)   { status = "amber"; note = "Low"; }
      else if (m.pct > 130)  { status = "red";   note = "Too high"; }
      else if (m.pct > 115)  { status = "amber"; note = "Slightly over"; }
      return { ...m, status, note };
    });
}

// ── CalTag component ──────────────────────────────────────────────────────────

function CalTag({ calorie_gap_pct }: { calorie_gap_pct?: number | null }) {
  if (calorie_gap_pct == null) return null;
  const pct  = Math.abs(calorie_gap_pct);
  const over = calorie_gap_pct > 0;
  if (pct < 2) {
    return (
      <span style={{
        fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 20,
        background: "#F0FFF4", color: "#1e8c3a", flexShrink: 0,
      }}>
        On target
      </span>
    );
  }
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 20,
      background: over ? "#FFE0B2" : "#FFF0F0",
      color: over ? "#b85c00" : "#c0392b",
      flexShrink: 0,
    }}>
      {pct}% {over ? "over" : "under"}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

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
    return () => { cancelled = true; };
  }, [token]);

  if (loading) return null;

  const n = nutrition;

  // Empty state
  if (!n || (!n.calories_per_day && !n.protein_pct && !n.fat_pct)) {
    const hasDietItems = n?.has_diet_items ?? false;
    return (
      <div className={compact ? undefined : "card"}>
        <div className="sec-lbl">Diet Analysis</div>
        <div style={{ color: "var(--t3)", fontSize: 13, padding: "14px 4px", lineHeight: 1.5 }}>
          {hasDietItems
            ? "Add portion sizes to your food items to see the calorie and macro breakdown."
            : "Not enough diet information yet. Log meals and portion sizes to see the breakdown across calories, protein, fat and fibre."}
        </div>
      </div>
    );
  }

  const macros       = deriveMacros(n);
  const gaps         = (n.micronutrient_gaps ?? []).filter((g) => g.status !== "sufficient");
  const improvements = (n.top_improvements  ?? []).slice(0, 3);

  if (!macros.length && !gaps.length) {
    return (
      <div className={compact ? undefined : "card"}>
        <div className="sec-lbl">Diet Analysis</div>
        <div style={{ color: "var(--t3)", fontSize: 13, padding: "14px 4px", lineHeight: 1.5 }}>
          Add portion sizes to your food items to see the calorie and macro breakdown.
        </div>
      </div>
    );
  }

  return (
    <div className={compact ? undefined : "card"}>
      <div className="sec-lbl">Diet Analysis</div>

      {/* ── Calorie line ── */}
      {!!n.calories_per_day && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "#FFF6ED", borderRadius: 10, padding: "10px 12px", marginBottom: 6,
        }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: "var(--t1)", minWidth: 0,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginRight: 8,
          }}>
            ~{n.calories_per_day.toLocaleString()} kcal / day
            {n.food_label && (
              <span style={{ color: "var(--t3)", fontWeight: 400, fontSize: 12, marginLeft: 4 }}>
                · {n.food_label}
              </span>
            )}
          </div>
          <CalTag calorie_gap_pct={n.calorie_gap_pct} />
        </div>
      )}

      {/* ── Prescription context ── */}
      {n.prescription_context && (
        <div style={{
          fontSize: 11, color: "#0055cc", background: "#EBF3FF",
          borderRadius: 8, padding: "5px 10px", marginBottom: 8,
        }}>
          Vet prescribed: {n.prescription_context}
        </div>
      )}

      {/* ── Warning / disclaimer ── */}
      {n.show_warning && n.warning_message && (
        <div style={{ fontSize: 11, color: "var(--t3)", marginBottom: 14, padding: "0 2px" }}>
          ⚠ <strong style={{ color: "var(--t2)" }}>Estimated</strong> — {n.warning_message}
        </div>
      )}

      {/* ── Macro donuts ── */}
      {macros.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: `repeat(${macros.length}, 1fr)`,
          gap: 6,
          textAlign: "center",
          marginBottom: 14,
          marginTop: n.show_warning || n.calories_per_day ? 8 : 0,
        }}>
          {macros.map((m) => (
            <div key={m.label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
              <Donut pct={m.pct} status={m.status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t1)" }}>{m.label}</div>
              <div style={{ fontSize: 9, fontWeight: 600, color: NUTR_COLOR[m.status] ?? "#8A8A8A" }}>
                {m.note}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Missing micronutrients ── */}
      {gaps.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginBottom: 12 }}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: "var(--t3)",
            textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 8,
          }}>
            Missing micronutrients
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {gaps.map((g) => {
              const meta = MICRO_META[g.name] ?? { icon: "💊", label: g.name };
              const ps   = pillStyle(g.severity_score);
              return (
                <span key={g.name} style={{
                  fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 20,
                  background: ps.background, color: ps.color,
                }}>
                  {meta.icon} {meta.label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Top improvements ── */}
      {improvements.map((imp, i) => (
        <div key={i} style={{
          display: "flex", gap: 10, padding: "9px 0",
          borderTop: "1px solid var(--border)", alignItems: "flex-start",
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%", flexShrink: 0, marginTop: 5,
            background: improvementColor(imp.severity),
          }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--t1)", marginBottom: 2 }}>
              {imp.title}
              {imp.severity === "prescribed" && (
                <span style={{ fontSize: 10, fontWeight: 500, color: "#8A8A8E", marginLeft: 6 }}>
                  · Vet prescribed
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: "var(--t2)", lineHeight: 1.45 }}>
              {imp.detail}
            </div>
          </div>
        </div>
      ))}

    </div>
  );
}
