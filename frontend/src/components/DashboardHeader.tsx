'use client';

import { useState } from 'react';
import type { PetProfile, OwnerInfo } from '@/lib/api';
import { ageFromDob, pincodeToCity } from '@/lib/dashboard-utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DashboardHeaderProps {
  pet: PetProfile;
  owner: OwnerInfo;
  overdueCount: number;
  healthScore: { score: number; label: string };
  onCartClick: (itemId?: string) => void;
  onActionsClick?: () => void;
}

export default function DashboardHeader({ pet, owner, overdueCount, healthScore, onCartClick, onActionsClick }: DashboardHeaderProps) {
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  const photoUrl = photoPreview || (pet.photo_url ? `${API_BASE}${pet.photo_url}` : null);
  const initials = pet.name?.slice(0, 2).toUpperCase() || '??';
  const age = ageFromDob(pet.dob);
  const city = pincodeToCity(owner.pincode);
  const locationOrSpecies = city || (pet.species ? pet.species.charAt(0).toUpperCase() + pet.species.slice(1) : '');

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
          <div className="text-white min-w-0 flex-1 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="font-display text-2xl font-bold truncate">{pet.name}</h1>
              <p className="text-white/80 text-sm">
                {pet.breed} · {age} · {locationOrSpecies}
              </p>
              <p className="text-white/60 text-xs mt-0.5">
                Parent: {owner.full_name}
              </p>
            </div>
            {/* Health Score Ring */}
            {(() => {
              const r = 22;
              const circ = 2 * Math.PI * r;
              const dash = (healthScore.score / 100) * circ;
              return (
                <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                  <div style={{ position: 'relative', width: 54, height: 54 }}>
                    <svg width={54} height={54} style={{ transform: 'rotate(-90deg)' }}>
                      <circle cx={27} cy={27} r={r} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={5} />
                      <circle
                        cx={27} cy={27} r={r} fill="none" stroke="#fff" strokeWidth={5}
                        strokeLinecap="round"
                        strokeDasharray={`${dash} ${circ - dash}`}
                      />
                    </svg>
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <span style={{ fontFamily: 'Fraunces, serif', fontSize: 14, fontWeight: 700, color: '#fff', lineHeight: 1 }}>
                        {healthScore.score}
                      </span>
                    </div>
                  </div>
                  <span style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.75)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {healthScore.label}
                  </span>
                </div>
              );
            })()}
          </div>
        </div>

        {/* Actions Banner */}
        {overdueCount > 0 && (
          <button
            onClick={() => onActionsClick ? onActionsClick() : onCartClick()}
            className="w-full flex items-center justify-between rounded-xl px-4 py-3 text-white"
            style={{ border: '2.5px solid rgba(255,255,255,0.5)', background: 'transparent' }}
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
                <span className="text-[10px] text-white/60">Medicines · Supplements</span>
              </div>
            </div>
            <span className="text-sm font-semibold shrink-0">Order →</span>
          </button>
        )}
      </div>
    </div>
  );
}
