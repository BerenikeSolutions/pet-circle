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
  const ageLabel = formatAgeLabel(ageMonths);
  const sex = normalizeSex(data.pet.gender);
  const weight = normalizeWeight(data.pet.weight);
  const avatar = getPetAvatar(data.pet.species);
  const vetName = data.vet_summary?.name || "Not added yet";
  const vetLastVisit = data.vet_summary?.last_visit || "--";

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
          <div className="dog-sub" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {data.pet.breed} · {sex} · {ageLabel} · ⚖️ {weight}
          </div>
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
