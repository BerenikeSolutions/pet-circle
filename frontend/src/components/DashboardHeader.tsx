'use client';

import { useState } from 'react';
import type { PetProfile, OwnerInfo } from '@/lib/api';
import { ageFromDob } from '@/lib/dashboard-utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DashboardHeaderProps {
  pet: PetProfile;
  owner: OwnerInfo;
  overdueCount: number;
  onCartClick: (itemId?: string) => void;
}

export default function DashboardHeader({ pet, owner, overdueCount, onCartClick }: DashboardHeaderProps) {
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  const photoUrl = photoPreview || (pet.photo_url ? `${API_BASE}${pet.photo_url}` : null);
  const initials = pet.name?.slice(0, 2).toUpperCase() || '??';
  const age = ageFromDob(pet.dob);
  const species = pet.species ? pet.species.charAt(0).toUpperCase() + pet.species.slice(1) : '';

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setPhotoPreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="relative overflow-hidden" style={{ background: 'var(--brand-gradient)' }}>
      {/* Decorative circle */}
      <div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 200, height: 200,
          top: -40, right: -40,
          backgroundColor: 'rgba(255,255,255,0.04)',
        }}
      />
      <div className="max-w-[430px] mx-auto px-5 pt-8 pb-5">
        {/* Avatar + Info */}
        <div className="flex items-center gap-4 mb-4">
          <label className="relative cursor-pointer shrink-0">
            {photoUrl ? (
              <img
                src={photoUrl}
                alt={pet.name}
                className="w-[72px] h-[72px] rounded-full object-cover border-[3px] border-white/30"
              />
            ) : (
              <div
                className="w-[72px] h-[72px] rounded-full flex items-center justify-center border-[3px] border-white/30 text-white font-bold text-xl"
                style={{ background: 'rgba(255,255,255,0.2)' }}
              >
                {initials}
              </div>
            )}
            <input type="file" accept="image/*" className="hidden" onChange={handlePhotoChange} />
            <div className="absolute -bottom-0.5 -right-0.5 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow">
              <span className="text-xs">📷</span>
            </div>
          </label>
          <div className="text-white min-w-0">
            <h1 className="font-display text-2xl font-bold truncate">{pet.name}</h1>
            <p className="text-white/80 text-sm">
              {pet.breed} · {age} · {species}
            </p>
            <p className="text-white/60 text-xs mt-0.5">
              Parent: {owner.full_name}
            </p>
          </div>
        </div>

        {/* Actions Banner */}
        {overdueCount > 0 && (
          <button
            onClick={() => onCartClick()}
            className="w-full flex items-center justify-between rounded-xl px-4 py-3 text-white"
            style={{ border: '1px solid rgba(255,255,255,0.25)', background: 'transparent' }}
          >
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <span className="w-8 h-8 bg-white rounded-full flex items-center justify-center text-base">⚡</span>
                <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1">
                  {overdueCount}
                </span>
              </div>
              <div>
                <span className="text-sm font-medium block">Actions Due</span>
                <span className="text-[10px] text-white/60">Medicines · Vet visits · Supplements · Grooming</span>
              </div>
            </div>
            <span className="text-sm font-semibold shrink-0">Order →</span>
          </button>
        )}
      </div>
    </div>
  );
}
