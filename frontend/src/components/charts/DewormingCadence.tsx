"use client";

import type { DewormingCadence as DewormingCadenceData } from "@/lib/api";
import TimelineSVG from "./TimelineSVG";
import { formatAxisDate } from "@/components/trends/trend-utils";

interface DewormingCadenceProps {
  data: DewormingCadenceData;
}

function mapState(state: string): "done" | "missed" | "now" | "upcoming" {
  const normalized = state.toLowerCase();
  if (normalized.includes("done")) return "done";
  if (normalized.includes("now")) return "now";
  if (normalized.includes("upcoming")) return "upcoming";
  return "missed";
}

export default function DewormingCadence({ data }: DewormingCadenceProps) {
  return (
    <TimelineSVG
      nodes={data.nodes.map((node) => ({
        label: node.state.toLowerCase().includes("now") ? "Now" : formatAxisDate(node.date),
        type: mapState(node.state),
      }))}
      legend={[
        { type: "done", label: "Done" },
        { type: "upcoming", label: "Upcoming" },
        { type: "missed", label: "Missed" },
        { type: "now", label: "Administer now" },
      ]}
    />
  );
}