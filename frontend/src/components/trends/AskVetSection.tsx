"use client";

import type { AskVetData } from "@/lib/api";
import AskVetConditionCard from "./AskVetConditionCard";

interface AskVetSectionProps {
  data: AskVetData | null;
  vetName: string;
  onOpenDashboardCondition?: (conditionId: string) => void;
}

export default function AskVetSection({
  data,
  vetName,
  onOpenDashboardCondition,
}: AskVetSectionProps) {
  const conditions = data?.conditions || [];

  return (
    <section>
      <div
        style={{
          fontSize: 13,
          color: "var(--t2)",
          marginBottom: 14,
          lineHeight: 1.55,
          padding: "10px 14px",
          background: "var(--tr)",
          borderRadius: 10,
          border: "1px solid #FFCDD2",
        }}
      >
        🩺 Share this section with <strong style={{ color: "var(--t1)" }}>Dr. {vetName}</strong> at your next visit.
      </div>

      {conditions.length === 0 ? (
        <div className="card" style={{ fontSize: 13, color: "var(--t2)", lineHeight: 1.5 }}>
          No vet discussion items are available right now.
        </div>
      ) : (
        conditions.map((condition) => (
          <AskVetConditionCard
            key={condition.id}
            condition={condition}
            onOpenDashboardCondition={onOpenDashboardCondition}
          />
        ))
      )}
    </section>
  );
}