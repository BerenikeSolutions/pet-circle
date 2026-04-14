"use client";

import type { FleaTickCadence } from "@/lib/api";
import DotPlotSVG from "./DotPlotSVG";
import {
  buildCriticalGapAnnotations,
  formatAxisDate,
  parseGapWeeks,
} from "@/components/trends/trend-utils";

interface TickFleaCadenceProps {
  data: FleaTickCadence;
}

export default function TickFleaCadence({ data }: TickFleaCadenceProps) {
  return (
    <DotPlotSVG
      doses={data.doses.map((dose) => ({
        n: dose.num,
        label: formatAxisDate(dose.date),
        gapWeeks: parseGapWeeks(dose.gap),
        gapLabel: dose.gap ?? undefined,
        isUpcoming: dose.status === "upcoming" || dose.status === "overdue",
      }))}
      criticalGaps={buildCriticalGapAnnotations(data.doses)}
      footer={data.footer.text}
    />
  );
}