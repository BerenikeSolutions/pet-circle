import type {
  CarePlanItem,
  CarePlanSection,
  DashboardData,
  DietMacroSummary,
  HealthConditionSummary,
  LifeStageData,
  RecognitionBullet,
} from "@/lib/api";

export const BUCKET_META = {
  continue: { label: "✅ Continue", bg: "#F0FFF4", border: "#C3E6CB", color: "#1e8c3a" },
  attend: { label: "⚠️ Attend to", bg: "#FFF0F0", border: "#FFCDD2", color: "#c0392b" },
  add: { label: "✦ Quick Fixes to Add", bg: "#FFF3EE", border: "#FFD5C2", color: "#FF6B35" },
} as const;

export const STAGE_WIDTHS = [10, 12, 45, 33] as const;
export const STAGE_LABELS = ["Puppy", "Junior", "Adult", "Senior"] as const;

export function getStageIndex(stage?: LifeStageData["stage"] | null): number {
  if (stage === "puppy") return 0;
  if (stage === "junior") return 1;
  if (stage === "adult") return 2;
  if (stage === "senior") return 3;
  return 2;
}

export function formatAgeLabel(ageMonths?: number | null): string {
  if (!ageMonths || ageMonths < 0) return "Unknown age";
  if (ageMonths < 24) {
    return `${ageMonths} mo`;
  }
  const years = Math.floor(ageMonths / 12);
  const months = ageMonths % 12;
  if (months === 0) return `${years} yr${years > 1 ? "s" : ""}`;
  return `${years}y ${months}m`;
}

export function ageMonthsFromDob(dob?: string | null): number | null {
  if (!dob) return null;
  const birthDate = new Date(dob);
  if (Number.isNaN(birthDate.getTime())) return null;

  const now = new Date();
  let months = (now.getFullYear() - birthDate.getFullYear()) * 12;
  months += now.getMonth() - birthDate.getMonth();
  if (now.getDate() < birthDate.getDate()) {
    months -= 1;
  }
  return Math.max(months, 0);
}

export function getPetAvatar(species?: string | null): string {
  const s = (species || "").toLowerCase();
  if (s.includes("cat")) return "🐈";
  if (s.includes("dog")) return "🐕";
  return "🐾";
}

export function normalizeSex(gender?: string | null): string {
  if (!gender) return "Unknown";
  return gender[0].toUpperCase() + gender.slice(1).toLowerCase();
}

export function normalizeWeight(weight?: number | null): string {
  if (typeof weight !== "number") return "--";
  return `${weight} kg`;
}

export function normalizeRecognitionBullets(data: DashboardData): RecognitionBullet[] {
  // Prefer backend-computed bullets when available (they include specific diet item names)
  const backendBullets = data.recognition?.bullets || [];
  if (backendBullets.length === 3) {
    return backendBullets;
  }

  // Fallback: compute client-side (always 3 bullets)
  const bullets: RecognitionBullet[] = [];

  // 1. Conditions — always present
  const activeConditions = (data.conditions || []).filter((c) => c.is_active);
  if (activeConditions.length > 0) {
    bullets.push({
      icon: "🩺",
      label: `${activeConditions.length} active condition${activeConditions.length > 1 ? "s" : ""} being managed`,
    });
  } else {
    bullets.push({ icon: "🩺", label: "No health conditions found" });
  }

  // 2. Preventive care — count core items with last_done_date filled
  const coreTracked = (data.preventive_records || []).filter(
    (r) => r.is_core && r.last_done_date
  );
  if (coreTracked.length > 0) {
    bullets.push({
      icon: "💉",
      label: `${coreTracked.length} preventive care item${coreTracked.length > 1 ? "s" : ""} tracked`,
    });
  } else {
    bullets.push({ icon: "💉", label: "0 preventive care items tracked" });
  }

  // 3. Diet — use backend diet bullet if available, else derive from diet_summary
  const dietBullet = backendBullets.find((b) => {
    const v = b.label.toLowerCase();
    return v.includes("diet") || v.includes("food") || v.includes("nutrition") || v.includes("kibble") || v.includes("cup") || v.includes("supplement") || v.includes("🍽️");
  });
  if (dietBullet) {
    bullets.push({ icon: dietBullet.icon || "🍽️", label: dietBullet.label });
  } else if ((data.diet_summary?.macros?.length ?? 0) > 0) {
    bullets.push({ icon: "🍽️", label: "Diet items tracked" });
  } else {
    bullets.push({ icon: "🍽️", label: "No diet entries recorded" });
  }

  return bullets;
}

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  severe: 0,
  high: 0,
  red: 0,
  moderate: 1,
  medium: 1,
  amber: 1,
  yellow: 1,
  mild: 2,
  low: 2,
  green: 2,
};

const PREVENTIVE_ITEM_KW = ["vaccine", "vaccination", "rabies", "deworm", "flea", "tick", "preventive"];
const OVERDUE_ITEM_KW = ["overdue", "missed", "pending", "late"];

function severityRank(condition: HealthConditionSummary): number {
  const severityText = [condition.severity, condition.trend_label].join(" ").toLowerCase();
  const severityKey = Object.keys(SEVERITY_ORDER).find((key) => severityText.includes(key));
  return severityKey ? SEVERITY_ORDER[severityKey] : 3;
}

function toTimestamp(raw: unknown): number {
  if (typeof raw !== "string" || !raw.trim()) return 0;
  const ts = new Date(raw).getTime();
  return Number.isNaN(ts) ? 0 : ts;
}

function sanitizeTrendLabel(label: string): string {
  return label.replace(/urgent/gi, "High Priority");
}

function sanitizeInsight(insight: string): string {
  const safe = insight.replace(/urgent/gi, "High Priority");
  const medicationPattern = /\b(tablet|capsule|syrup|dose|doses|amoxicillin|prednisone|doxycycline|metronidazole|gabapentin|carprofen|clavamox)\b|(\d+(\.\d+)?\s?(mg|ml))\b/i;
  if (medicationPattern.test(safe)) {
    return "Monitor this closely and ask your vet for the right diagnosis and treatment plan.";
  }
  return safe;
}

function isPreventiveGap(item: CarePlanItem): boolean {
  const text = `${item.name} ${item.test_type} ${item.status_tag}`.toLowerCase();
  const status = (item.status_tag || "").toLowerCase();
  const explicitlyNotOverdue = status.includes("soon") || status.includes("upcoming");
  return !explicitlyNotOverdue
    && PREVENTIVE_ITEM_KW.some((kw) => text.includes(kw))
    && OVERDUE_ITEM_KW.some((kw) => text.includes(kw));
}

function buildPuppyPreventiveGaps(data: DashboardData): HealthConditionSummary[] {
  if (data.life_stage?.stage !== "puppy") return [];

  const attendSections = data.care_plan_v2?.attend || [];
  const gapItems = attendSections.flatMap((section) => section.items).filter(isPreventiveGap);

  return gapItems.map((item, index) => ({
    id: `prev_${item.test_type || "preventive"}_${index}`,
    icon: "🛡️",
    title: `${item.name} overdue`,
    severity: "high",
    trend_label: "preventive gap",
    insight: "Preventive care is overdue. Ask your vet for the safest catch-up plan.",
  }));
}

function sortConditionsBySeverityAndRecency(
  conditions: HealthConditionSummary[],
  datesById: Map<string, number>
): HealthConditionSummary[] {
  return [...conditions].sort((a, b) => {
    const severityDiff = severityRank(a) - severityRank(b);
    if (severityDiff !== 0) return severityDiff;

    const aRecency = Math.max(
      toTimestamp((a as HealthConditionSummary & { last_detected?: string }).last_detected),
      toTimestamp((a as HealthConditionSummary & { first_detected?: string }).first_detected),
      datesById.get(a.id) || 0
    );
    const bRecency = Math.max(
      toTimestamp((b as HealthConditionSummary & { last_detected?: string }).last_detected),
      toTimestamp((b as HealthConditionSummary & { first_detected?: string }).first_detected),
      datesById.get(b.id) || 0
    );
    return bRecency - aRecency;
  });
}

export function normalizeConditions(data: DashboardData): HealthConditionSummary[] {
  const conditionDates = new Map(
    (data.conditions || []).map((condition) => [
      condition.id,
      toTimestamp(condition.diagnosed_at) || toTimestamp(condition.created_at),
    ])
  );

  const base = data.health_conditions_summary && data.health_conditions_summary.length > 0
    ? data.health_conditions_summary
    : (data.conditions || [])
      .filter((condition) => condition.is_active)
      .map((condition) => ({
        id: condition.id,
        icon: condition.icon || "🩺",
        title: condition.name,
        severity: "high",
        trend_label: "Active",
        insight: condition.notes || "Keep discussing progress with your vet.",
      }));

  const sanitized = base.map((condition) => ({
    ...condition,
    trend_label: sanitizeTrendLabel(condition.trend_label || ""),
    insight: sanitizeInsight(condition.insight || "Keep discussing progress with your vet."),
  }));

  const withPuppyGaps = [...sanitized, ...buildPuppyPreventiveGaps(data)];
  return sortConditionsBySeverityAndRecency(withPuppyGaps, conditionDates);
}

export function normalizeMacros(macros: DietMacroSummary[] = []): DietMacroSummary[] {
  const byName = new Map(macros.map((m) => [m.name.toLowerCase(), m]));

  const pick = (name: string): DietMacroSummary => {
    const fallback: DietMacroSummary = { name, pct_of_need: 0, color: "red", note: "No data" };
    return byName.get(name.toLowerCase()) || fallback;
  };

  return [pick("Calories"), pick("Protein"), pick("Fat"), pick("Fibre")];
}

export function macroStatus(name: string, pct: number): "green" | "amber" | "red" {
  const metric = name.toLowerCase();
  if (metric.includes("calorie")) {
    if (pct > 110) return "amber";
    if (pct < 80) return "red";
    return "green";
  }
  // Protein, Fat, Fibre share the same thresholds
  if (pct > 110) return "amber";
  if (pct < 80) return "red";
  return "green";
}

export function buildCarePlanBuckets(data: DashboardData): Record<"continue" | "attend" | "add", CarePlanSection[]> {
  const source = data.care_plan_v2;
  if (!source) {
    return { continue: [], attend: [], add: [] };
  }

  const seen = new Set<string>();

  const SECTION_TITLE_MAP: Record<string, string> = {
    "tick flea": "Flea & Tick Protection",
    "tick & flea": "Flea & Tick Protection",
    "tick and flea": "Flea & Tick Protection",
    "tick/flea": "Flea & Tick Protection",
    "flea tick": "Flea & Tick Protection",
    "tick flea prevention": "Flea & Tick Protection",
    "tick & flea prevention": "Flea & Tick Protection",
    "tick/flea prevention": "Flea & Tick Protection",
    "flea & tick protection": "Flea & Tick Protection",
  };

  const PREVENTIVE_SECTIONS = ["vaccines", "vaccine", "preventive", "deworming", "flea", "tick"];
  const FOOD_SECTIONS = ["diet", "food"];

  const normalizeSectionTitle = (title: string): string => {
    const mapped = SECTION_TITLE_MAP[title.toLowerCase().trim()];
    return mapped || title;
  };

  const isPreventiveSection = (title: string): boolean => {
    const lower = title.toLowerCase();
    return PREVENTIVE_SECTIONS.some((kw) => lower.includes(kw));
  };

  const isFoodSection = (title: string): boolean => {
    const lower = title.toLowerCase();
    return FOOD_SECTIONS.some((kw) => lower.includes(kw));
  };

  const sanitizeSection = (bucket: "continue" | "attend" | "add", section: CarePlanSection): CarePlanSection => {
    const filteredItems = section.items.filter((item) => {
      const key = `${item.test_type}:${item.name}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).map((item) => {
      if (bucket === "attend") {
        return { ...item, orderable: false };
      }
      return item;
    });

    const normalizedTitle = normalizeSectionTitle(section.title);
    // Remove icons from vaccine/preventive care sections
    const sectionIcon = isPreventiveSection(normalizedTitle) ? "" : section.icon;

    return { ...section, title: normalizedTitle, icon: sectionIcon, items: filteredItems };
  };

  return {
    continue: source.continue.map((section) => sanitizeSection("continue", section)),
    attend: source.attend
      .map((section) => sanitizeSection("attend", section))
      .filter((section) => !isFoodSection(section.title)),
    add: source.add
      .map((section) => sanitizeSection("add", section))
      .filter((section) => !isFoodSection(section.title)),
  };
}

export function normalizeStatusTag(tag: string): string {
  const lower = (tag || "").toLowerCase().trim();
  if (lower === "recommended") return "Recommended";
  if (lower.includes("overdue") || lower.includes("urgent") || lower.includes("red") || lower.includes("missed") || lower.includes("late") || lower.includes("not started") || lower.includes("prescription") || lower.includes("review")) return "Urgent";
  if (lower.includes("soon") || lower.includes("upcoming") || lower.includes("watch") || lower.includes("amber") || lower.includes("yellow")) return "Due soon";
  return "On track";
}

export function itemStatusClass(item: CarePlanItem): "s-tag-g" | "s-tag-y" | "s-tag-r" | "s-tag-rec" {
  const normalized = normalizeStatusTag(item.status_tag || "");
  if (normalized === "Recommended") return "s-tag-rec";
  if (normalized === "Urgent") return "s-tag-r";
  if (normalized === "Due soon") return "s-tag-y";
  return "s-tag-g";
}

export function computeCarePlanCounts(
  data: DashboardData
): { onTrack: number; dueSoon: number; overdue: number } {
  const buckets = buildCarePlanBuckets(data);
  let onTrack = 0;
  let dueSoon = 0;
  let overdue = 0;

  // Only count items from the "continue" bucket — items in "add" (Quick Fixes)
  // and "attend" should not inflate the overdue/on-track/due-soon totals.
  const EXCLUDED_TYPES = new Set(["food", "supplement"]);
  for (const section of buckets.continue) {
    for (const item of section.items) {
      if (EXCLUDED_TYPES.has(item.test_type || "")) continue;
      const cls = itemStatusClass(item);
      if (cls === "s-tag-r") overdue += 1;
      else if (cls === "s-tag-y") dueSoon += 1;
      else if (cls === "s-tag-g") onTrack += 1;
    }
  }

  return { onTrack, dueSoon, overdue };
}
