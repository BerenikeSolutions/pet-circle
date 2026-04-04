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
    <CollapsibleCard icon="📊" title="Analysis" defaultOpen={false}>
      <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        <LifeStageCard data={data} compact />
        <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} compact />
        <DietAnalysisCard data={data} compact />
      </div>
    </CollapsibleCard>
  );
}