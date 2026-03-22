'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { DashboardData, BackendDietItem, NutritionAnalysis } from '@/lib/api';
import { getDietItems, addDietItem, updateDietItem, deleteDietItem, getNutritionAnalysis, addToCart } from '@/lib/api';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import Toggle from '@/components/ui/Toggle';

interface NutritionTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
  onUpdated?: () => void;
}

type DietType = 'packaged' | 'homemade' | 'supplement';

// ── Inline NutrientRow card (matches petcircle reference) ─────────────────────
function NutrientRow({
  icon, name, status, priority, reason, supplement, price,
}: {
  icon?: string; name: string; status: string; priority?: string;
  reason?: string; supplement?: string | null; price?: string | null;
}) {
  const c  = status === 'Missing' ? '#FF3B30' : (status === 'Low' || status === 'high') ? '#FF9500' : '#34C759';
  const bg = status === 'Missing' ? '#FFF0F0' : (status === 'Low' || status === 'high') ? '#FFF6ED' : '#F0FFF4';
  const lbl = status === 'Missing' ? 'Missing' : status === 'Low' ? 'Low' : status === 'High' ? 'High' : 'Adequate';
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 10px', background: '#FAFAF9', borderRadius: 10, border: `1px solid ${c}22` }}>
      <div style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{icon || '•'}</div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
          <div style={{ background: bg, color: c, borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>{lbl}</div>
          {priority === 'urgent' && (
            <div style={{ background: '#FF3B30', color: 'white', borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>Urgent</div>
          )}
        </div>
        {reason && <div style={{ fontSize: 11, color: '#8E8E93', lineHeight: 1.4 }}>{reason}</div>}
        {supplement && price && (
          <div style={{ fontSize: 11, color: '#007AFF', marginTop: 3 }}>→ {supplement} · {price}</div>
        )}
      </div>
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className || ''}`} />;
}

/** Capitalize first letter of each word */
function titleCase(str: string): string {
  return str.replace(/\b\w/g, c => c.toUpperCase());
}

/** Format detail consistently */
function formatDetail(detail: string | null): string | null {
  if (!detail) return null;
  let d = detail.charAt(0).toUpperCase() + detail.slice(1);
  d = d.replace(/\b(daily|weekly|monthly|twice|once|per day|per week)\b/gi, match => titleCase(match));
  return d;
}

export default function NutritionTab({ data, token, onCartClick, onUpdated }: NutritionTabProps) {
  const [diet, setDiet] = useState<BackendDietItem[]>([]);
  const [nutrition, setNutrition] = useState<NutritionAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editSheet, setEditSheet] = useState(false);
  const [editItem, setEditItem] = useState<BackendDietItem | null>(null);
  const [form, setForm] = useState({ label: '', detail: '', type: 'packaged' as DietType });

  // Reorder reminder toggles (keyed by diet item id)
  const [reorderToggles, setReorderToggles] = useState<Record<string, boolean>>({});
  // Frequency modal state for order reminders
  const [freqModal, setFreqModal] = useState<{ id: string; freq: number; unit: string } | null>(null);
  const [freqSettings, setFreqSettings] = useState<Record<string, { freq: number; unit: string }>>({});

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [dietData, nutritionData] = await Promise.all([
        getDietItems(token),
        getNutritionAnalysis(token),
      ]);
      setDiet(dietData);
      setNutrition(nutritionData);
    } catch (e: any) {
      setError(e.message || 'Failed to load nutrition data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    if (!form.label.trim()) return;
    setSaving(true);
    try {
      if (editItem) {
        await updateDietItem(token, editItem.id, { label: form.label.trim(), detail: form.detail.trim() });
      } else {
        await addDietItem(token, { type: form.type, label: form.label.trim(), detail: form.detail.trim() || undefined });
      }
      setEditSheet(false);
      setEditItem(null);
      await loadData();
      onUpdated?.();
    } catch (e: any) {
      setError(e.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (itemId: string) => {
    setSaving(true);
    try {
      await deleteDietItem(token, itemId);
      await loadData();
      onUpdated?.();
    } catch (e: any) {
      setError(e.message || 'Failed to delete');
    } finally {
      setSaving(false);
    }
  };

  const foods = diet.filter(d => d.type === 'packaged' || d.type === 'homemade');
  const supplements = diet.filter(d => d.type === 'supplement');
  const nd = nutrition;

  // Items with supplement recommendations from nutrition analysis
  const suppsFromAnalysis = useMemo(() => {
    if (!nd) return [];
    const items: Array<{ key: string; name: string; supplement: string; price: string; priority: string }> = [];
    for (const arr of [nd.minerals, nd.others]) {
      for (const n of arr) {
        if (n.supplement && n.price && n.status !== 'Adequate') {
          items.push({ key: n.name, name: n.name, supplement: n.supplement, price: n.price, priority: ('priority' in n ? n.priority : 'medium') as string });
        }
      }
    }
    for (const v of nd.vitamins) {
      if (v.supplement && v.price && v.status !== 'Adequate') {
        items.push({ key: v.name, name: v.name, supplement: v.supplement, price: v.price, priority: v.priority });
      }
    }
    return items;
  }, [nd]);

  // Priority rank for sorting
  const PRIORITY_RANK: Record<string, number> = { urgent: 0, high: 1, medium: 2, ok: 3 };

  const freqLabelStr = (freq: number, unit: string) => {
    if (unit === 'day')   return freq === 1 ? 'Daily'   : `Every ${freq} days`;
    if (unit === 'week')  return freq === 1 ? 'Weekly'  : `Every ${freq} weeks`;
    if (unit === 'month') return freq === 1 ? 'Monthly' : `Every ${freq} months`;
    if (unit === 'year')  return freq === 1 ? 'Yearly'  : `Every ${freq} years`;
    return `Every ${freq} ${unit}s`;
  };

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-48" />
          {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      </div>
    );
  }

  // Calorie status helpers
  const calActual = nd?.calories.actual ?? 0;
  const calTarget = nd?.calories.target ?? 1;
  const calDiff = calActual - calTarget;
  const calStatus = calDiff < -100 ? 'low' : calDiff > 150 ? 'high' : 'ok';
  const calC   = calStatus === 'ok' ? '#34C759' : calStatus === 'low' ? '#FF9500' : '#FF3B30';
  const calBg  = calStatus === 'ok' ? '#F0FFF4' : calStatus === 'low' ? '#FFF6ED' : '#FFF0F0';
  const calLbl = calStatus === 'ok' ? 'On target' : calStatus === 'low' ? 'Below target' : 'Above target';
  const calPct = Math.round((calActual / calTarget) * 100);

  const vitaminGaps = nd?.vitamins.filter(v => v.status !== 'Adequate') ?? [];
  const vitaminOverall = vitaminGaps.some(v => v.priority === 'high') ? '#FF3B30' : vitaminGaps.length ? '#FF9500' : '#34C759';
  const vitaminBg = vitaminOverall === '#34C759' ? '#F0FFF4' : vitaminOverall === '#FF9500' ? '#FFF6ED' : '#FFF0F0';
  const vitaminLbl = vitaminOverall === '#34C759' ? 'Adequate' : vitaminGaps.some(v => v.status === 'Missing') ? 'Missing' : 'Low';

  const gapCount = nd?.gap_count ?? suppsFromAnalysis.filter(s => s.priority === 'urgent' || s.priority === 'high').length;
  const hasDiet = diet.length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {error && (
        <div style={{ background: '#FFF0F0', border: '1px solid #FF3B3044', borderRadius: 12, padding: '10px 14px', fontSize: 12, color: '#FF3B30' }}>
          {error}
          <button onClick={() => { setError(null); loadData(); }} style={{ marginLeft: 8, textDecoration: 'underline', background: 'none', border: 'none', color: '#FF3B30', cursor: 'pointer', fontSize: 12 }}>Retry</button>
        </div>
      )}

      {/* ── 1. CURRENT DIET ─────────────────────────────────────────────────── */}
      <div style={{ background: 'white', borderRadius: 16, padding: 16, border: '1px solid #F0EDE8', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>🥣 Current diet</div>

        {foods.map((row, i) => (
          <div key={row.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0', borderTop: i === 0 ? 'none' : '1px solid #F0EDE8' }}>
            <div style={{ fontSize: 18, flexShrink: 0 }}>{row.icon}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: '#1A1A1A' }}>{titleCase(row.label)}</div>
              {row.detail && <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 1 }}>{formatDetail(row.detail)}</div>}
            </div>
            <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
              <button
                onClick={() => { setEditItem(row); setForm({ label: row.label, detail: row.detail || '', type: row.type }); setEditSheet(true); }}
                style={{ background: '#F2EDE8', border: 'none', borderRadius: 8, padding: '4px 8px', fontSize: 11, color: '#555', cursor: 'pointer', fontWeight: 600 }}
              >✎</button>
              <button
                onClick={() => handleDelete(row.id)}
                disabled={saving}
                style={{ background: '#FFF0F0', border: 'none', borderRadius: 8, padding: '4px 8px', fontSize: 11, color: '#FF3B30', cursor: 'pointer', fontWeight: 700 }}
              >✕</button>
            </div>
          </div>
        ))}

        {foods.length === 0 && (
          <div style={{ fontSize: 12, color: '#AEAEB2', padding: '8px 0', textAlign: 'center' }}>No food recorded yet</div>
        )}

        <AddRow label="Add food" onClick={() => { setEditItem(null); setForm({ label: '', detail: '', type: 'packaged' }); setEditSheet(true); }} />

        {/* Supplements section */}
        <div style={{ marginTop: 12, fontSize: 11, color: '#8E8E93', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>Current supplements</div>
        {supplements.length > 0 ? (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
            {supplements.map(s => (
              <div
                key={s.id}
                onClick={() => { setEditItem(s); setForm({ label: s.label, detail: s.detail || '', type: s.type }); setEditSheet(true); }}
                style={{ background: '#F0F6FF', color: '#007AFF', borderRadius: 8, padding: '3px 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                ✓ {titleCase(s.label)}
                <button
                  onClick={e => { e.stopPropagation(); handleDelete(s.id); }}
                  style={{ background: 'none', border: 'none', color: '#007AFF', fontSize: 11, cursor: 'pointer', opacity: 0.7, padding: 0, marginLeft: 2 }}
                >✕</button>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: '#AEAEB2', marginBottom: 6 }}>No supplements added</div>
        )}
        <AddRow label="Add supplement" onClick={() => { setEditItem(null); setForm({ label: '', detail: '', type: 'supplement' }); setEditSheet(true); }} />
      </div>

      {/* ── 2. ORDER REMINDERS ───────────────────────────────────────────────── */}
      <div style={{ background: 'white', borderRadius: 16, padding: 16, border: '1px solid #F0EDE8', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: hasDiet ? 12 : 8 }}>🔔 Order reminders</div>
        {hasDiet ? (
          <>
            {[...foods, ...supplements].map((item, i) => {
              const s = freqSettings[item.id] || { freq: 1, unit: 'month' };
              const on = reorderToggles[item.id] ?? false;
              return (
                <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderTop: i === 0 ? 'none' : '1px solid #F0EDE8' }}>
                  <div style={{ width: 36, height: 36, borderRadius: 10, background: '#F7F4F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>{item.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: '#1A1A1A' }}>{titleCase(item.label)}</div>
                    <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>Monthly {item.type === 'supplement' ? 'supplement' : 'reorder'}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <div
                      onClick={() => setFreqModal({ id: item.id, freq: s.freq, unit: s.unit })}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 3, background: on ? '#EFF6FF' : '#F2F2F7', color: on ? '#007AFF' : '#AEAEB2', borderRadius: 20, padding: '3px 9px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
                    >
                      🔁 {freqLabelStr(s.freq, s.unit)} <span style={{ fontSize: 10, opacity: 0.7 }}>✎</span>
                    </div>
                    <Toggle
                      checked={on}
                      onChange={() => setReorderToggles(prev => ({ ...prev, [item.id]: !prev[item.id] }))}
                    />
                  </div>
                </div>
              );
            })}
            <button
              onClick={async () => {
                for (const item of [...foods, ...supplements]) {
                  const productId = `diet_${item.id}`;
                  try {
                    await addToCart(token, { product_id: productId, name: item.label, price: 0, icon: item.icon, sub: 'Monthly reorder', tag: 'Reorder', tag_color: '#34C759' });
                  } catch { /* already in cart */ }
                }
                onCartClick();
              }}
              style={{ width: '100%', marginTop: 12, background: '#D44800', color: 'white', border: 'none', borderRadius: 10, padding: '11px', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              🛒 Order Now
            </button>
          </>
        ) : (
          <>
            <div style={{ background: '#F7F4F0', borderRadius: 10, padding: '12px 14px', fontSize: 12, color: '#8E8E93', lineHeight: 1.5 }}>
              No food or supplement information recorded. Add diet details above to set up order reminders.
            </div>
            <AddRow label="Add food or supplement" onClick={() => { setEditItem(null); setForm({ label: '', detail: '', type: 'packaged' }); setEditSheet(true); }} />
          </>
        )}
      </div>

      {/* ── 3. NUTRITION NOTE ────────────────────────────────────────────────── */}
      <div style={{ background: 'white', borderRadius: 16, padding: 16, border: '1.5px solid #D4480033', boxShadow: '0 1px 6px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: '#FFF3EE', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>🐾</div>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#1A1A1A' }}>Nutrition note</div>
        </div>

        {/* Overall diet box */}
        <div style={{ background: '#FFF6ED', border: '1px solid #FF950044', borderRadius: 10, padding: '8px 11px', marginBottom: 7 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#8B5E00', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 2 }}>Overall diet</div>
          <div style={{ fontSize: 12, color: '#3A3A3A', lineHeight: 1.5 }}>
            {nd
              ? (nd as any).diet_summary || (hasDiet
                  ? `${calActual}/${calTarget} kcal/day — ${calStatus === 'ok' ? 'on target' : calStatus === 'low' ? 'slightly below target' : 'above target'}.`
                  : 'Diet not recorded — macros and calorie analysis unavailable. Add diet info for a full breakdown.')
              : 'Add diet items to see analysis.'}
          </div>
        </div>

        {/* What to improve box */}
        {nd && nd.improvements.length > 0 && (
          <div style={{ background: '#F0F6FF', border: '1px solid #007AFF33', borderRadius: 10, padding: '8px 11px', marginBottom: 7 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#005BBB', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 5 }}>
              {hasDiet ? 'What to improve' : 'What to address (based on health records)'}
            </div>
            {nd.improvements.map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginBottom: i === nd.improvements.length - 1 ? 0 : 5 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: item.dot, flexShrink: 0, marginTop: 4 }} />
                <span style={{ fontSize: 12, color: '#333', lineHeight: 1.4 }}>{item.text}</span>
              </div>
            ))}
          </div>
        )}

        {/* Recommendation box */}
        {nd && (
          <div style={{ background: '#F0FFF4', border: '1px solid #34C75933', borderRadius: 10, padding: '8px 11px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#1A6B2A', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 2 }}>
              {hasDiet ? 'Our recommendation' : 'PetCircle recommendation'}
            </div>
            <div style={{ fontSize: 12, color: '#3A3A3A', lineHeight: 1.5 }}>{nd.recommendation}</div>
          </div>
        )}
      </div>

      {/* ── 4. NUTRITION BREAKDOWN / SUPPLEMENT RECOMMENDATIONS ─────────────── */}
      {nd && (
        <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', border: hasDiet ? '1.5px solid #FF3B3044' : '1.5px solid #FF9500', boxShadow: '0 1px 6px rgba(0,0,0,0.06)' }}>
          {/* Colored header */}
          <div style={{ background: hasDiet ? '#FFF0F0' : '#FFF3EE', padding: '14px 16px', borderBottom: '1px solid #F0EDE8' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {!hasDiet && <div style={{ width: 3, height: 36, background: '#D44800', borderRadius: 2, flexShrink: 0 }} />}
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                  <div style={{ fontWeight: 800, fontSize: 15, color: '#1A1A1A', letterSpacing: -0.2 }}>
                    {hasDiet ? 'Nutrition breakdown' : 'Supplement Recommendations'}
                  </div>
                  {!hasDiet && (
                    <div style={{ background: '#FFF3EE', border: '1.5px solid #D4480044', color: '#D44800', borderRadius: 20, padding: '2px 8px', fontSize: 9, fontWeight: 700 }}>🐾 PetCircle Recommended</div>
                  )}
                </div>
                <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 0 }}>
                  {hasDiet ? 'Calories · macros · vitamins · minerals' : `Based on ${data.pet.name}'s health records · not diet (not recorded)`}
                </div>
              </div>
              <div style={{ background: 'white', color: hasDiet ? '#FF3B30' : '#D44800', borderRadius: 20, padding: '4px 12px', fontSize: 11, fontWeight: 700, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', flexShrink: 0 }}>
                {hasDiet ? (gapCount > 0 ? 'Gaps found' : 'Balanced') : `${gapCount} Missing`}
              </div>
            </div>
          </div>

          <div style={{ padding: 16 }}>
            {/* Calories (only when diet is recorded) */}
            {hasDiet && (
              <div style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 15 }}>🔥</span>
                    <span style={{ fontWeight: 700, fontSize: 12, color: '#555', textTransform: 'uppercase', letterSpacing: 0.4 }}>Calories</span>
                  </div>
                  <div style={{ background: calBg, color: calC, borderRadius: 20, padding: '2px 9px', fontSize: 10, fontWeight: 700 }}>{calLbl}</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#8E8E93', marginBottom: 4 }}>
                  <span>Current: <strong style={{ color: '#1A1A1A' }}>{calActual} kcal/day</strong></span>
                  <span>Target: <strong style={{ color: '#1A1A1A' }}>{calTarget} kcal/day</strong></span>
                </div>
                <div style={{ height: 8, background: '#F2F2F7', borderRadius: 4, overflow: 'hidden', marginBottom: 4 }}>
                  <div style={{ height: '100%', width: `${Math.min(calPct, 100)}%`, background: calC, borderRadius: 4, transition: 'width 0.8s ease' }} />
                </div>
                <div style={{ fontSize: 11, color: calC, fontWeight: 600 }}>
                  {calDiff < 0
                    ? `${Math.abs(calDiff)} kcal below target — consider increasing portions`
                    : calDiff > 0
                    ? `${calDiff} kcal above target — monitor weight`
                    : 'Calorie intake well-balanced'}
                </div>
              </div>
            )}

            {/* Detailed analysis separator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <div style={{ flex: 1, height: 1, background: '#F0EDE8' }} />
              <div style={{ fontSize: 10, fontWeight: 700, color: '#AEAEB2', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {hasDiet ? 'Detailed analysis' : 'Based on health records'}
              </div>
              <div style={{ flex: 1, height: 1, background: '#F0EDE8' }} />
            </div>

            {/* Breed context hint */}
            <div style={{ fontSize: 11, color: '#8B5E00', background: '#FFF6ED', border: '1px solid #FF950044', borderRadius: 10, padding: '7px 10px', marginBottom: 12 }}>
              💡 {hasDiet
                ? `Analysis based on ${data.pet.breed || data.pet.species} breed profile${data.conditions && data.conditions.length > 0 ? ` + ${data.pet.name}'s health conditions` : ''}`
                : `Calorie and macro analysis requires diet information. Add ${data.pet.name}'s food above to unlock full breakdown.`}
            </div>

            {/* Macronutrients (only when diet is recorded) */}
            {hasDiet && nd.macros.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Macronutrients</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {nd.macros.map((m, i) => {
                    const mc = m.status === 'ok' || m.status === 'Adequate' ? '#34C759' : m.status === 'low' || m.status === 'Low' ? '#FF9500' : '#FF3B30';
                    const mbg = m.status === 'ok' || m.status === 'Adequate' ? '#F0FFF4' : m.status === 'low' || m.status === 'Low' ? '#FFF6ED' : '#FFF0F0';
                    const mlbl = m.status === 'ok' || m.status === 'Adequate' ? 'Adequate' : m.status === 'low' || m.status === 'Low' ? 'Low' : 'High';
                    const barPct = Math.min((m.actual / Math.max(m.target, m.actual || 1)) * 100, 100);
                    const tgtPct = Math.min((m.target / Math.max(m.target, m.actual || 1)) * 100, 100);
                    return (
                      <div key={i} style={{ padding: '9px 10px', background: '#FAFAF9', borderRadius: 10, border: `1px solid ${mc}22` }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                          <span style={{ fontSize: 15 }}>{m.icon}</span>
                          <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{m.name}</span>
                          <span style={{ fontSize: 11, color: '#8E8E93' }}>{m.actual}{m.unit} / {m.target}{m.unit}</span>
                          <div style={{ background: mbg, color: mc, borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>{mlbl}</div>
                        </div>
                        <div style={{ height: 5, background: '#EBEBEB', borderRadius: 3, position: 'relative' }}>
                          <div style={{ height: '100%', width: `${barPct}%`, background: mc, borderRadius: 3 }} />
                          <div style={{ position: 'absolute', top: -2, left: `${tgtPct}%`, width: 2, height: 9, background: '#555', borderRadius: 1, opacity: 0.25 }} />
                        </div>
                        <div style={{ fontSize: 10, color: '#AEAEB2', marginTop: 3 }}>{m.note}</div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* Vitamins */}
            {nd.vitamins.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Vitamins</div>
                <div style={{ padding: '10px 12px', background: '#FAFAF9', borderRadius: 10, border: `1px solid ${vitaminOverall}22`, marginBottom: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: vitaminGaps.length ? 8 : 0 }}>
                    <span style={{ fontSize: 16 }}>🧪</span>
                    <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>Vitamins</span>
                    <div style={{ background: vitaminBg, color: vitaminOverall, borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>{vitaminLbl}</div>
                  </div>
                  {vitaminGaps.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {vitaminGaps.map((v, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', background: v.status === 'Missing' ? '#FFF0F0' : '#FFF6ED', borderRadius: 8 }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: v.status === 'Missing' ? '#FF3B30' : '#FF9500', flexShrink: 0 }} />
                          <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{v.name}</span>
                          {v.supplement && v.price && (
                            <span style={{ fontSize: 10, color: '#007AFF' }}>→ {v.supplement} · {v.price}</span>
                          )}
                        </div>
                      ))}
                      {nd.vitamins.filter(v => v.status === 'Adequate').map((v, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px' }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#34C759', flexShrink: 0 }} />
                          <span style={{ fontSize: 11, color: '#8E8E93', flex: 1 }}>{v.name}</span>
                          <span style={{ fontSize: 10, color: '#34C759', fontWeight: 600 }}>Adequate</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Minerals (NutrientRow card format) */}
            {nd.minerals.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
                  {hasDiet ? 'Minerals' : 'Based on health records'}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {[...nd.minerals]
                    .sort((a, b) => (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3))
                    .map((m, i) => (
                      <NutrientRow key={i} icon={m.icon} name={m.name} status={m.status} priority={m.priority} reason={m.reason} supplement={m.supplement} price={m.price} />
                    ))}
                </div>
              </>
            )}

            {/* Other nutrients (NutrientRow card format) */}
            {nd.others.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Other key supplements</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {[...nd.others]
                    .sort((a, b) => (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3))
                    .map((o, i) => (
                      <NutrientRow key={i} icon={o.icon} name={o.name} status={o.status} priority={o.priority} supplement={o.supplement} price={o.price} />
                    ))}
                </div>
              </>
            )}

            {/* Order supplements CTA */}
            {suppsFromAnalysis.length > 0 && (
              <button
                onClick={async () => {
                  for (const item of suppsFromAnalysis) {
                    const productId = `supp_${item.name.toLowerCase().replace(/\s+/g, '_')}`;
                    try {
                      await addToCart(token, { product_id: productId, name: item.supplement, price: parseFloat(item.price.replace(/[^\d.]/g, '')) || 0, icon: '💊', sub: item.name, tag: 'Supplement', tag_color: '#34C759' });
                    } catch { /* already in cart */ }
                  }
                  onCartClick();
                }}
                style={{ width: '100%', background: '#D44800', color: 'white', border: 'none', borderRadius: 10, padding: '11px', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                🛒 Order Supplements
              </button>
            )}
          </div>
        </div>
      )}

      {/* Empty state when no diet and no nutrition analysis */}
      {!nd && diet.length === 0 && (
        <div style={{ background: 'white', borderRadius: 16, padding: 24, border: '1px solid #F0EDE8', textAlign: 'center' }}>
          <p style={{ fontSize: 13, color: '#AEAEB2' }}>Add diet items to see nutrition analysis</p>
        </div>
      )}

      {/* ── FREQ MODAL (Order reminders frequency) ──────────────────────────── */}
      {freqModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 300, display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}
          onClick={() => setFreqModal(null)}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'white', borderRadius: '20px 20px 0 0', padding: 24, width: '100%', maxWidth: 430 }}>
            <div style={{ width: 40, height: 4, background: '#E0E0E0', borderRadius: 2, margin: '0 auto 20px' }} />
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>Reminder frequency</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {[1, 2, 3, 6].map(n => (
                ['month'].map(u => (
                  <button key={`${n}-${u}`}
                    onClick={() => setFreqSettings(prev => ({ ...prev, [freqModal.id]: { freq: n, unit: u } }))}
                    style={{ padding: '10px', borderRadius: 10, border: `1.5px solid ${freqSettings[freqModal.id]?.freq === n ? '#D44800' : '#E8E4DF'}`, background: freqSettings[freqModal.id]?.freq === n ? '#FFF3EE' : 'white', color: freqSettings[freqModal.id]?.freq === n ? '#D44800' : '#555', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                    {freqLabelStr(n, u)}
                  </button>
                ))
              ))}
            </div>
            <button onClick={() => setFreqModal(null)}
              style={{ width: '100%', background: '#D44800', color: 'white', border: 'none', borderRadius: 12, padding: '13px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
              Done
            </button>
          </div>
        </div>
      )}

      {/* ── DIET EDIT SHEET ──────────────────────────────────────────────────── */}
      <BottomSheet
        open={editSheet}
        onClose={() => { setEditSheet(false); setEditItem(null); }}
        title={editItem ? 'Edit item' : 'Add item'}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {!editItem && (
            <div style={{ display: 'flex', gap: 8 }}>
              {(['packaged', 'homemade', 'supplement'] as const).map(t => (
                <button key={t} onClick={() => setForm({ ...form, type: t })}
                  style={{ flex: 1, padding: '8px 4px', borderRadius: 20, border: `1.5px solid ${form.type === t ? '#D44800' : '#E8E4DF'}`, background: form.type === t ? '#D44800' : 'white', color: form.type === t ? 'white' : '#666', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          )}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>Name / brand</div>
            <input value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} placeholder="e.g. Royal Canin Adult"
              style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1.5px solid #E8E4DF', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: "'DM Sans', sans-serif" }} />
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
              {form.type === 'supplement' ? 'Dose' : 'Quantity / frequency'}
            </div>
            <input value={form.detail} onChange={e => setForm({ ...form, detail: e.target.value })}
              placeholder={form.type === 'supplement' ? 'e.g. 2 scoops, twice daily' : 'e.g. 280g · 2x/day'}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1.5px solid #E8E4DF', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: "'DM Sans', sans-serif" }} />
          </div>
          <button onClick={handleSave} disabled={saving || !form.label.trim()}
            style={{ width: '100%', marginTop: 8, background: form.label.trim() ? '#D44800' : '#D1D1D6', color: 'white', border: 'none', borderRadius: 12, padding: '13px', fontSize: 14, fontWeight: 700, cursor: form.label.trim() ? 'pointer' : 'default' }}>
            {saving ? 'Saving...' : editItem ? 'Save' : 'Add item'}
          </button>
          {editItem && (
            <>
              <button onClick={() => { handleDelete(editItem.id); setEditSheet(false); setEditItem(null); }}
                style={{ width: '100%', background: 'none', border: '1.5px solid #FF3B3044', borderRadius: 12, padding: '11px', fontSize: 13, fontWeight: 600, color: '#FF3B30', cursor: 'pointer' }}>
                Delete this item
              </button>
              <button onClick={() => { setEditSheet(false); setEditItem(null); }}
                style={{ width: '100%', background: 'none', border: 'none', color: '#8E8E93', padding: '10px', fontSize: 13, cursor: 'pointer' }}>
                Cancel
              </button>
            </>
          )}
        </div>
      </BottomSheet>
    </div>
  );
}
