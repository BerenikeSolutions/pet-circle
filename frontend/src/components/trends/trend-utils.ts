import type {
  AskVetChartPoint,
  AskVetTimelineNode,
  BloodPanelRow,
  FleaTickDose,
  VaccineRound,
} from "@/lib/api";

const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
});

const MONTH_YEAR_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  month: "short",
  year: "2-digit",
});

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDisplayDate(value?: string | null): string {
  const date = parseDate(value);
  return date ? DATE_FORMATTER.format(date) : "Date unavailable";
}

export function formatAxisDate(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "--";
  const now = new Date();
  if (date.getFullYear() === now.getFullYear()) {
    return SHORT_DATE_FORMATTER.format(date);
  }
  return MONTH_YEAR_FORMATTER.format(date).replace(" ", " '");
}

export function getSpeciesEmoji(species?: string | null): string {
  const normalized = (species || "").toLowerCase();
  if (normalized.includes("cat")) return "🐈";
  if (normalized.includes("dog")) return "🐕";
  return "🐾";
}

export function buildBarStatus(point: AskVetChartPoint): "red" | "amber" | "green" {
  const marker = point.marker.toLowerCase();
  const status = point.status.toLowerCase();
  if (marker.includes("pus")) {
    if (point.value <= 0 || status.includes("nil") || status.includes("normal")) return "green";
    if (point.value > 5 || status.includes("high")) return "red";
    return "amber";
  }

  if (status.includes("normal")) return "green";
  if (status.includes("high") || status.includes("low") || status.includes("positive")) return "red";
  return "amber";
}

export function isPlateletSeries(points: AskVetChartPoint[]): boolean {
  return points.some((point) => point.marker.toLowerCase().includes("platelet"));
}

export function bloodPanelRowOrder(rows: BloodPanelRow[]): BloodPanelRow[] {
  const groupOrder: Array<[RegExp, number]> = [
    [/(platelet|haemoglobin|hemoglobin|wbc|rbc|neutrophil|lymphocyte|monocyte|eosinophil|hematocrit|pcv|mcv|mch|mchc)/i, 0],
    [/(alt|ast|alp|bilirubin|albumin|total protein|globulin)/i, 1],
    [/(creatinine|bun|urea|phosphorus|sdma)/i, 2],
    [/(glucose|cholesterol|sodium|potassium|chloride|calcium)/i, 3],
  ];

  const explicitOrder: Record<string, number> = {
    platelets: 0,
    haemoglobin: 1,
    hemoglobin: 1,
    wbc: 2,
    neutrophils: 3,
    lymphocytes: 4,
    alt: 10,
    creatinine: 20,
    glucose: 30,
    bilirubin: 31,
  };

  return [...rows].sort((left, right) => {
    // When panel has >8 rows, sort abnormal results first for scanning efficiency
    if (rows.length > 8) {
      const leftAbnormal = left.status.toLowerCase() !== "normal" ? 0 : 1;
      const rightAbnormal = right.status.toLowerCase() !== "normal" ? 0 : 1;
      if (leftAbnormal !== rightAbnormal) return leftAbnormal - rightAbnormal;
    }

    const leftGroup = groupOrder.find(([pattern]) => pattern.test(left.marker))?.[1] ?? 99;
    const rightGroup = groupOrder.find(([pattern]) => pattern.test(right.marker))?.[1] ?? 99;
    if (leftGroup !== rightGroup) return leftGroup - rightGroup;

    const leftKey = left.marker.toLowerCase();
    const rightKey = right.marker.toLowerCase();
    const leftRank = explicitOrder[leftKey] ?? 999;
    const rightRank = explicitOrder[rightKey] ?? 999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.marker.localeCompare(right.marker);
  });
}

export function parseGapWeeks(gap?: string | null): number | undefined {
  if (!gap) return undefined;
  const match = gap.match(/(\d+)/);
  return match ? Number(match[1]) : undefined;
}

export function buildVaccineGapLabels(rounds: VaccineRound[], gaps: string[]): Array<{ afterIndex: number; label: string }> {
  const usable = Math.max(0, Math.min(gaps.length, rounds.length - 1));
  return gaps.slice(0, usable).map((label, index) => ({ afterIndex: index, label }));
}

export function buildCriticalGapAnnotations(doses: FleaTickDose[]): Array<{ fromIndex: number; toIndex: number; label: string }> {
  const annotations: Array<{ fromIndex: number; toIndex: number; label: string }> = [];
  doses.forEach((dose, index) => {
    const weeks = parseGapWeeks(dose.gap);
    if (!dose.gap_alert || weeks === undefined || index === 0) return;
    annotations.push({ fromIndex: index - 1, toIndex: index, label: `${weeks}w gap` });
  });
  return annotations;
}

export function compressTimelineNodes(nodes: AskVetTimelineNode[]): {
  nodes: AskVetTimelineNode[];
  showBreak: boolean;
} {
  if (nodes.length <= 5) {
    return { nodes, showBreak: false };
  }

  return {
    nodes: [nodes[0], ...nodes.slice(-4)],
    showBreak: true,
  };
}

export function timelineNodeColor(node: AskVetTimelineNode, index: number, total: number): string {
  const source = `${node.label} ${node.icon}`.toLowerCase();
  if (source.includes("clear") || source.includes("negative") || source.includes("nil") || source.includes("✅")) {
    return "#34C759";
  }
  if (source.includes("partial") || source.includes("persist") || source.includes("retest") || source.includes("🔄") || source.includes("⚠")) {
    return "#FF9F1C";
  }
  if (source.includes("detected") || source.includes("positive") || source.includes("episode") || source.includes("🦠") || source.includes("🔬") || source.includes("🔴")) {
    return "#FF3B30";
  }
  return index === total - 1 ? "#FF9F1C" : "#8A8A8A";
}