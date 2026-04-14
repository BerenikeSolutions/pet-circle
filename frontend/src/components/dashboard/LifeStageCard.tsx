"use client";

import type { DashboardData, LifeStageInsight } from "@/lib/api";
import {
  ageMonthsFromDob,
  formatAgeLabel,
  getStageIndex,
  STAGE_LABELS,
  STAGE_WIDTHS,
} from "./dashboard-utils";

interface LifeStageCardProps {
  data: DashboardData;
  compact?: boolean;
}

const INSIGHT_BG: Record<LifeStageInsight["color"], { bg: string; color: string }> = {
  orange:  { bg: "var(--ta)",  color: "#b85c00" },
  green:   { bg: "var(--tg)",  color: "#1e8c3a" },
  neutral: { bg: "#F0EDE9",    color: "var(--t2)" },
};

function getStageStarts() {
  return STAGE_WIDTHS.reduce<number[]>((acc, width, index) => {
    acc.push(index === 0 ? 0 : acc[index - 1] + STAGE_WIDTHS[index - 1]);
    return acc;
  }, []);
}

function markerPositionPct(
  ageMonths: number,
  stageIndex: number,
  starts: number[],
  boundaries?: { junior_start: number; adult_start: number; senior_start: number },
): number {
  const b = boundaries ?? { junior_start: 12, adult_start: 24, senior_start: 84 };
  const stageBounds = [0, b.junior_start, b.adult_start, b.senior_start, b.senior_start + 48];
  const start = stageBounds[stageIndex];
  const end   = stageBounds[stageIndex + 1];
  const progress = Math.max(0, Math.min(1, (ageMonths - start) / Math.max(1, end - start)));
  const raw = starts[stageIndex] + progress * STAGE_WIDTHS[stageIndex];
  // Keep the 18px circle + 2px shadow fully inside the bar on all screen widths
  return Math.max(4, Math.min(raw, 94));
}

export default function LifeStageCard({ data, compact = false }: LifeStageCardProps) {
  const lifeStage = data.life_stage;
  const computedAge = ageMonthsFromDob(data.pet.dob);
  const ageMonths = lifeStage?.age_months ?? computedAge;
  const hasAge = ageMonths !== null && ageMonths !== undefined;
  const effectiveAge = ageMonths ?? 24;
  const ageLabel = formatAgeLabel(effectiveAge);

  const stageIndex = getStageIndex(lifeStage?.stage);
  const starts = getStageStarts();
  const markerPct = markerPositionPct(effectiveAge, stageIndex, starts, lifeStage?.stage_boundaries);

  const insights = (lifeStage?.insights ?? []).slice(0, 3);

  if (!hasAge) {
    return (
      <div className={compact ? undefined : "card"} style={{ paddingBottom: 12 }}>
        <div className="sec-lbl">What to expect as {data.pet.name} grows</div>
        <div style={{ fontSize: 13, color: "var(--t2)", lineHeight: 1.5, marginTop: 4 }}>
          Age has not been provided yet. Add {data.pet.name}&apos;s date of birth to see life stage insights and personalized care tips.
        </div>
      </div>
    );
  }

  return (
    <div className={compact ? undefined : "card"} style={{ paddingBottom: 12 }}>
      <div className="sec-lbl">What to expect as {data.pet.name} turns {ageLabel}</div>

      {/* Stage labels */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--t3)", marginBottom: 4 }}>
        {STAGE_LABELS.map((label, index) => (
          <span
            key={label}
            style={{
              width: `${STAGE_WIDTHS[index]}%`,
              textAlign: "center",
              color: index === stageIndex ? "var(--orange)" : "var(--t3)",
              fontWeight: index === stageIndex ? 700 : 400,
            }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* Progress bar */}
      <div className="stage-bar" style={{ marginBottom: 8 }}>
        {STAGE_LABELS.map((label, index) => (
          <div
            key={label}
            style={{
              position: "absolute",
              left: `${starts[index]}%`,
              width: `${STAGE_WIDTHS[index]}%`,
              top: 0,
              bottom: 0,
              background: index === stageIndex ? "linear-gradient(90deg,#FF8C5A,#FF6B35)" : "#E0DDD9",
              opacity: index === stageIndex ? 1 : 0.5,
              borderRadius: index === 0 ? "6px 0 0 6px" : index === STAGE_LABELS.length - 1 ? "0 6px 6px 0" : 0,
            }}
          />
        ))}
        <div className="stage-marker" style={{ left: `${markerPct}%` }} />
      </div>

      {/* Caption tracks the marker — anchors right when dot is in the right half */}
      <div style={{ position: "relative", height: 20, marginBottom: 12 }}>
        <span
          className="stage-caption"
          style={{
            position: "absolute",
            fontSize: 11,
            whiteSpace: "nowrap",
            ...(markerPct >= 60
              ? { right: `${100 - markerPct}%`, left: "auto" }
              : markerPct <= 40
              ? { left: `${markerPct}%`, right: "auto" }
              : { left: `${markerPct}%`, transform: "translateX(-50%)" }),
          }}
        >
          {data.pet.name} is here · {ageLabel}
        </span>
      </div>

      {/* Full-sentence insight cards */}
      {insights.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {insights.map((insight, i) => {
            const style = INSIGHT_BG[insight.color] ?? INSIGHT_BG.neutral;
            return (
              <div
                key={i}
                style={{
                  background: style.bg,
                  borderRadius: 10,
                  padding: "10px 14px",
                  fontSize: 13,
                  fontWeight: 500,
                  color: style.color,
                  lineHeight: 1.45,
                  overflowWrap: "break-word",
                  wordBreak: "break-word",
                  minWidth: 0,
                }}
              >
                {insight.text}
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--t3)", textAlign: "center", padding: "8px 0" }}>
          Personalised insights are being prepared for {data.pet.name}.
        </div>
      )}
    </div>
  );
}
