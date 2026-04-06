"use client";

import type { DashboardData } from "@/lib/api";
import {
  ageMonthsFromDob,
  formatAgeLabel,
  getPetAvatar,
  normalizeSex,
  normalizeWeight,
} from "./dashboard-utils";

interface ProfileBannerProps {
  data: DashboardData;
  onGoToReminders: () => void;
}

export default function ProfileBanner({ data, onGoToReminders }: ProfileBannerProps) {
  const ageMonths = data.life_stage?.age_months ?? ageMonthsFromDob(data.pet.dob);
  const avatar = getPetAvatar(data.pet.species);
  const vetName = data.vet_summary?.name || "Not added yet";
  const vetLastVisit = data.vet_summary?.last_visit || "--";

  const subParts: string[] = [];
  if (data.pet.breed) subParts.push(data.pet.breed);
  if (data.pet.gender) subParts.push(normalizeSex(data.pet.gender));
  if (ageMonths != null && ageMonths > 0 && data.pet.dob) subParts.push(formatAgeLabel(ageMonths));
  if (typeof data.pet.weight === "number" && data.pet.weight > 0) subParts.push(`⚖️ ${normalizeWeight(data.pet.weight)}`);
  const subLine = subParts.join(" · ");

  return (
    <div className="banner">
      <div className="bn-top">
        <span className="brand">PetCircle</span>
        <button
          className="bell"
          onClick={onGoToReminders}
          type="button"
          title="Care Reminders"
          aria-label="Open care reminders"
        >
          🔔
        </button>
      </div>

      <div className="profile">
        <div className="avatar">{avatar}</div>
        <div style={{ minWidth: 0 }}>
          <div className="dog-name">{data.pet.name}</div>
          {subLine && (
            <div className="dog-sub" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {subLine}
            </div>
          )}
        </div>
      </div>

      <div className="vet-row">
        <span>🩺</span>
        <span className="vet-l">Vet</span>
        <span className="vet-v">{vetName}</span>
        <span className="vet-sep">·</span>
        <span className="vet-l">Last visit</span>
        <span className="vet-v">{vetLastVisit}</span>
      </div>
    </div>
  );
}
