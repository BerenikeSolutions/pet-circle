"use client";

import type { SignalsData } from "@/lib/api";
import BloodPanelTable from "./BloodPanelTable";
import MetabolicCard from "./MetabolicCard";
import WeightTrendCard from "./WeightTrendCard";

interface SignalsSectionProps {
  data: SignalsData | null;
}

export default function SignalsSection({ data }: SignalsSectionProps) {
  if (!data) {
    return (
      <div className="card" style={{ fontSize: 13, color: "var(--t2)", lineHeight: 1.5 }}>
        No signal summaries are available yet.
      </div>
    );
  }

  return (
    <section>
      {data.blood_panel && <BloodPanelTable data={data.blood_panel} />}
      {data.weight && <WeightTrendCard data={data.weight} />}
      {data.metabolic && <MetabolicCard data={data.metabolic} />}
    </section>
  );
}