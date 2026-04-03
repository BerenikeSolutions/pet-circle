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
  const rawBullets = data.recognition?.bullets || [];
  const capped = rawBullets.slice(0, 3);

  // Keep conditions first, preventive second, diet last when mixed.
  const orderScore = (label: string): number => {
    const v = label.toLowerCase();
    if (v.includes("condition")) return 0;
    if (v.includes("prevent") || v.includes("vaccin") || v.includes("deworm") || v.includes("tick")) return 1;
    if (v.includes("diet") || v.includes("food") || v.includes("nutrition")) return 2;
    return 3;
  };

  return [...capped].sort((a, b) => orderScore(a.label) - orderScore(b.label));
}

export function normalizeConditions(data: DashboardData): HealthConditionSummary[] {
  if (data.health_conditions_summary && data.health_conditions_summary.length > 0) {
    return data.health_conditions_summary;
  }

  return (data.conditions || [])
    .filter((condition) => condition.is_active)
    .map((condition) => ({
      id: condition.id,
      icon: condition.icon || "🩺",
      title: condition.name,
      severity: "red",
      trend_label: "Active",
      insight: condition.notes || "Keep discussing progress with your vet.",
    }));
}

export function normalizeMacros(macros: DietMacroSummary[] = []): DietMacroSummary[] {
  const byName = new Map(macros.map((m) => [m.name.toLowerCase(), m]));

  const pick = (name: string): DietMacroSummary => {
    const fallback: DietMacroSummary = { name, pct_of_need: 0, color: "red", note: "No data" };
    return byName.get(name.toLowerCase()) || fallback;
  };

  return [pick("Calories"), pick("Protein"), pick("Omega-3"), pick("Fat")];
}

export function macroStatus(name: string, pct: number): "green" | "amber" | "red" {
  const metric = name.toLowerCase();
  if (metric.includes("omega") && pct <= 15) return "red";
  if (metric.includes("calorie")) {
    if (pct > 100) return "amber";
    if (pct < 80) return "red";
    return "green";
  }

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

    return { ...section, items: filteredItems };
  };

  return {
    continue: source.continue.map((section) => sanitizeSection("continue", section)),
    attend: source.attend.map((section) => sanitizeSection("attend", section)),
    add: source.add.map((section) => sanitizeSection("add", section)),
  };
}

export function itemStatusClass(item: CarePlanItem): "s-tag-g" | "s-tag-y" | "s-tag-r" {
  const status = (item.status_tag || "").toLowerCase();
  if (status.includes("urgent") || status.includes("overdue") || status.includes("red")) return "s-tag-r";
  if (status.includes("soon") || status.includes("watch") || status.includes("amber") || status.includes("yellow")) return "s-tag-y";
  return "s-tag-g";
}
