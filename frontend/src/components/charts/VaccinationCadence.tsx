"use client";

import type { VaccineCadence } from "@/lib/api";
import TimelineSVG from "./TimelineSVG";
import { buildVaccineGapLabels, formatAxisDate } from "@/components/trends/trend-utils";

interface VaccinationCadenceProps {
  data: VaccineCadence;
}

export default function VaccinationCadence({ data }: VaccinationCadenceProps) {
  return (
    <TimelineSVG
      nodes={data.rounds.map((round) => ({
        nodeLabel: round.label,
        label: formatAxisDate(round.date),
        sub: round.done ? round.vaccines : "Due",
        type: round.done ? "done" : "upcoming",
      }))}
      gaps={buildVaccineGapLabels(data.rounds, data.gaps)}
      legend={[
        { type: "done", label: "Completed" },
        { type: "upcoming", label: "Upcoming" },
      ]}
    />
  );
}