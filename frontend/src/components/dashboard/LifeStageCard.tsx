"use client";

import type { DashboardData, LifeStageTrait } from "@/lib/api";
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

const TRAIT_CLASS: Record<LifeStageTrait["color"], string> = {
  green: "trait-g",
  yellow: "trait-y",
  red: "trait-r",
  neutral: "trait-p",
};

function getStageStarts() {
  return STAGE_WIDTHS.reduce<number[]>((acc, width, index) => {
    acc.push(index === 0 ? 0 : acc[index - 1] + STAGE_WIDTHS[index - 1]);
    return acc;
  }, []);
}

function traitOrder(label: string): number {
  const value = label.toLowerCase();
  const behaviorKeywords = ["energy", "play", "playful", "anxiety", "anxious", "active", "restless", "behavior", "temperament", "social"];
  const physiologyKeywords = ["appetite", "weight", "metabolism", "digestion", "sleep", "hydration", "coat", "hunger", "thirst"];
  const clinicalKeywords = ["joint", "dental", "pain", "stiff", "limp", "vomit", "diarr", "itch", "rash", "infection", "cardiac"];

  if (behaviorKeywords.some((keyword) => value.includes(keyword))) return 0;
  if (physiologyKeywords.some((keyword) => value.includes(keyword))) return 1;
  if (clinicalKeywords.some((keyword) => value.includes(keyword))) return 2;
  return 1;
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

  const adultStart = starts[2];
  const adultWidth = STAGE_WIDTHS[2];
  const posInAdult = (effectiveAge - 24) / (84 - 24);
  const markerPctRaw = adultStart + posInAdult * adultWidth;
  const markerPct = Math.max(0, Math.min(100, markerPctRaw));

  const traits = (lifeStage?.traits || [])
    .map((trait, index) => ({ trait, index }))
    .sort((a, b) => {
      const orderDiff = traitOrder(a.trait.label) - traitOrder(b.trait.label);
      return orderDiff !== 0 ? orderDiff : a.index - b.index;
    })
    .map((entry) => entry.trait)
    .slice(0, 8);
  const essentialCare = (lifeStage?.essential_care || []).slice(0, 2);

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

      <div className="stage-bar" style={{ marginBottom: 3 }}>
        {STAGE_LABELS.map((label, index) => (
          <div
            key={label}
            style={{
              position: "absolute",
              left: `${starts[index]}%`,
              width: `${STAGE_WIDTHS[index]}%`,
              top: 0,
              bottom: 0,
              background:
                index === stageIndex ? "linear-gradient(90deg,#FF8C5A,#FF6B35)" : "#E0DDD9",
              opacity: index === stageIndex ? 1 : 0.5,
              borderRadius:
                index === 0 ? "6px 0 0 6px" : index === STAGE_LABELS.length - 1 ? "0 6px 6px 0" : 0,
            }}
          />
        ))}
        <div className="stage-marker" style={{ left: `${markerPct}%` }} />
      </div>

      <div className="stage-caption" style={{ fontSize: 11, marginTop: 4, marginBottom: 8 }}>
        {data.pet.name} is here · {ageLabel}
      </div>

      {traits.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10, maxHeight: "52px", overflow: "hidden" }}>
          {traits.map((trait) => (
            <span
              key={trait.label}
              className={`trait-pill ${TRAIT_CLASS[trait.color]}`}
              style={{ fontSize: 10, padding: "3px 8px", whiteSpace: "nowrap" }}
            >
              {trait.label}
            </span>
          ))}
        </div>
      )}

      {essentialCare.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          {essentialCare.map((care) => (
            <div key={care.title} style={{ background: "var(--ta)", borderRadius: 8, padding: "8px 12px" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#b85c00", marginBottom: 2 }}>
                {care.title}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--t2)",
                  lineHeight: 1.4,
                }}
                title={care.detail}
              >
                {care.detail}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
