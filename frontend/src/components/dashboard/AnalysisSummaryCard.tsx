"use client";

import type { DashboardData } from "@/lib/api";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import LifeStageCard from "./LifeStageCard";
import HealthConditionsCard from "./HealthConditionsCard";
import DietAnalysisCard from "./DietAnalysisCard";

interface AnalysisSummaryCardProps {
  data: DashboardData;
  onGoToTrends: () => void;
}

export default function AnalysisSummaryCard({ data, onGoToTrends }: AnalysisSummaryCardProps) {
  return (
    <CollapsibleCard title="Analysis" defaultOpen={false}>
      <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "14px 12px" }}>
          <LifeStageCard data={data} compact />
        </div>
        <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "14px 12px" }}>
          <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} compact />
        </div>
        <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "14px 12px" }}>
          <DietAnalysisCard nutrition={data.nutrition_analysis} compact />
        </div>
      </div>
    </CollapsibleCard>
  );
}
