'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { DashboardData, BackendDietItem, NutritionAnalysis } from '@/lib/api';
import { getDietItems, addDietItem, updateDietItem, deleteDietItem, getNutritionAnalysis } from '@/lib/api';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';

interface NutritionTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
  onUpdated?: () => void;
}

type DietType = 'packaged' | 'homemade' | 'supplement';

function mapStatus(s: string): 'ok' | 'low' | 'high' {
  if (s === 'Adequate') return 'ok';
  if (s === 'Low' || s === 'Missing') return 'low';
  return 'ok';
}

function priorityColor(p: string): { color: string; bg: string } {
  switch (p) {
    case 'urgent': return { color: '#FF3B30', bg: '#FFF0F0' };
    case 'high': return { color: '#FF3B30', bg: '#FFF0F0' };
    case 'medium': return { color: '#FF9500', bg: '#FFF6ED' };
    default: return { color: '#34C759', bg: '#F0FFF4' };
  }
}

function statusBarColor(s: string): string {
  if (s === 'Adequate') return '#34C759';
  if (s === 'Low') return '#FF9500';
  return '#FF3B30';
}

/** Loading skeleton placeholder */
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded ${className || ''}`} />
  );
}

export default function NutritionTab({ data, token, onCartClick, onUpdated }: NutritionTabProps) {
  const [diet, setDiet] = useState<BackendDietItem[]>([]);
  const [nutrition, setNutrition] = useState<NutritionAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editSheet, setEditSheet] = useState(false);
  const [editItem, setEditItem] = useState<BackendDietItem | null>(null);
  const [form, setForm] = useState({
    label: '',
    detail: '',
    type: 'packaged' as DietType,
  });
  // Reorder reminder toggles (keyed by supplement name)
  const [reorderToggles, setReorderToggles] = useState<Record<string, boolean>>({});

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

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    if (!form.label.trim()) return;
    setSaving(true);
    try {
      if (editItem) {
        await updateDietItem(token, editItem.id, {
          label: form.label.trim(),
          detail: form.detail.trim() || undefined,
        });
      } else {
        await addDietItem(token, {
          type: form.type,
          label: form.label.trim(),
          detail: form.detail.trim() || undefined,
        });
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

  // Collect orderable supplements from nutrition analysis (vitamins, minerals, others with supplement suggestions)
  const reorderItems = useMemo(() => {
    if (!nd) return [];
    const items: Array<{ name: string; supplement: string; price: string; priority: string }> = [];
    for (const arr of [nd.vitamins, nd.minerals, nd.others]) {
      for (const n of arr) {
        if (n.supplement && n.price) {
          items.push({
            name: n.name,
            supplement: n.supplement,
            price: n.price,
            priority: ('priority' in n ? n.priority : 'medium') as string,
          });
        }
      }
    }
    return items;
  }, [nd]);

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
          <Skeleton className="h-16 w-full" />
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-full" />
          {[1, 2, 3, 4, 5].map(i => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-700">
          {error}
          <button onClick={() => { setError(null); loadData(); }} className="ml-2 underline">Retry</button>
        </div>
      )}

      {/* Current Diet */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>🍖</span> Current Diet
        </h3>
        {foods.length > 0 && (
          <div className="mb-3">
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Food</p>
            {foods.map(f => (
              <div key={f.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{f.icon} {f.label}</p>
                  {f.detail && <p className="text-[11px] text-gray-500">{f.detail}</p>}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setEditItem(f);
                      setForm({ label: f.label, detail: f.detail || '', type: f.type });
                      setEditSheet(true);
                    }}
                    className="text-xs text-brand font-semibold"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(f.id)}
                    disabled={saving}
                    className="text-xs text-red-500 font-semibold"
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {supplements.length > 0 && (
          <div className="mb-3">
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Supplements</p>
            {supplements.map(s => (
              <div key={s.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{s.icon} {s.label}</p>
                  {s.detail && <p className="text-[11px] text-gray-500">{s.detail}</p>}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setEditItem(s);
                      setForm({ label: s.label, detail: s.detail || '', type: s.type });
                      setEditSheet(true);
                    }}
                    className="text-xs text-brand font-semibold"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    disabled={saving}
                    className="text-xs text-red-500 font-semibold"
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {diet.length === 0 && (
          <p className="text-xs text-gray-400 py-3 text-center">
            No diet items added yet. Add items to see nutrition analysis.
          </p>
        )}
        <AddRow label="Add Food/Supplement" onClick={() => {
          setEditItem(null);
          setForm({ label: '', detail: '', type: 'packaged' });
          setEditSheet(true);
        }} />
      </div>

      {/* Order Reminders */}
      {reorderItems.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
            <span>🔔</span> Order Reminders
          </h3>
          <p className="text-[11px] text-gray-500 mb-3">
            Toggle on to get WhatsApp reminders when it&apos;s time to reorder.
          </p>
          <div className="space-y-0">
            {reorderItems.map((item) => {
              const pc = priorityColor(item.priority);
              const isOn = reorderToggles[item.name] ?? false;
              return (
                <div
                  key={item.name}
                  className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0"
                >
                  <div className="flex-1 min-w-0 mr-3">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 truncate">{item.supplement}</p>
                      <span
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                        style={{ color: pc.color, backgroundColor: pc.bg }}
                      >
                        {item.name}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500">{item.price} &middot; Monthly refill</p>
                  </div>
                  <button
                    onClick={() =>
                      setReorderToggles(prev => ({ ...prev, [item.name]: !prev[item.name] }))
                    }
                    className="w-11 h-6 rounded-full relative transition-colors shrink-0"
                    style={{ backgroundColor: isOn ? '#34C759' : '#E5E5EA' }}
                    aria-label={`Toggle reorder reminder for ${item.supplement}`}
                  >
                    <span
                      className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform"
                      style={{ left: isOn ? '22px' : '2px' }}
                    />
                  </button>
                </div>
              );
            })}
          </div>
          <button
            onClick={() => onCartClick()}
            className="w-full mt-3 py-2 rounded-xl text-sm font-semibold border-2 border-dashed"
            style={{ borderColor: '#D44800', color: '#D44800' }}
          >
            🛒 Order All Supplements
          </button>
        </div>
      )}

      {/* Nutrition Note */}
      {nd && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <span>🥗</span> Nutrition Note
          </h3>
          <div className="rounded-xl p-3" style={{ backgroundColor: '#FFF6ED', borderLeft: '3px solid #FF9500' }}>
            <p className="text-xs font-semibold text-amber-800 mb-1">Overall Diet</p>
            <p className="text-xs text-amber-700">
              {nd.calories.actual}/{nd.calories.target} kcal/day — {nd.calories.status === 'adequate' ? 'on target' : nd.calories.status === 'low' ? 'slightly below target' : 'below target'}.
            </p>
            {(nd as any).diet_summary && (
              <p className="text-xs text-amber-600 mt-1">{(nd as any).diet_summary}</p>
            )}
          </div>
          {nd.improvements.length > 0 && (
            <div className="rounded-xl p-3" style={{ backgroundColor: '#F0F6FF', borderLeft: '3px solid #007AFF' }}>
              <p className="text-xs font-semibold text-blue-800 mb-1">What to Improve</p>
              <ul className="space-y-1">
                {nd.improvements.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-blue-700">
                    <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: item.dot }} />
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="rounded-xl p-3" style={{ backgroundColor: '#F0FFF4', borderLeft: '3px solid #34C759' }}>
            <p className="text-xs font-semibold text-green-800 mb-1">Recommendation</p>
            <p className="text-xs text-green-700">{nd.recommendation}</p>
          </div>
          <p className="text-[10px] text-gray-400 text-center">{nd.analysis_context}</p>
        </div>
      )}

      {/* Empty state for nutrition when no diet items */}
      {!nd && diet.length === 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 text-center">
          <p className="text-gray-400 text-sm">Add diet items to see nutrition analysis</p>
        </div>
      )}

      {/* Nutrition Breakdown */}
      {nd && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-4">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <span>📊</span> Nutrition Breakdown
          </h3>

          {/* Calories */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-500">Daily Calories</span>
              <span className="font-semibold">{nd.calories.actual}/{nd.calories.target} kcal/day</span>
            </div>
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min((nd.calories.actual / nd.calories.target) * 100, 100)}%`,
                  background: nd.calories.actual >= nd.calories.target * 0.9 ? '#34C759' : 'var(--brand-gradient)',
                }}
              />
            </div>
          </div>

          {/* Macronutrients */}
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-2">Macronutrients</p>
            {nd.macros.map((m, i) => (
              <div key={i} className="mb-2">
                <div className="flex items-center justify-between text-xs mb-0.5">
                  <span className="flex items-center gap-1">
                    <span>{m.icon}</span>
                    <span className="text-gray-700">{m.name}</span>
                  </span>
                  <span className="font-medium">{m.actual}/{m.target}{m.unit}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min((m.actual / (m.target || 1)) * 100, 100)}%`,
                      backgroundColor: statusBarColor(m.status),
                    }}
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-0.5">{m.note}</p>
              </div>
            ))}
          </div>

          {/* Vitamins */}
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-2">Vitamins Gap Analysis</p>
            {nd.vitamins.map((v, i) => {
              const pc = priorityColor(v.priority);
              return (
                <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-sm text-gray-800">{v.name}</p>
                    {v.supplement && <p className="text-[10px] text-gray-500">&rarr; {v.supplement} &middot; {v.price}</p>}
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color: pc.color, backgroundColor: pc.bg }}
                  >
                    {v.status}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Minerals */}
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-2">Minerals</p>
            {nd.minerals.map((m, i) => {
              const pc = priorityColor(m.priority);
              return (
                <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span>{m.icon}</span>
                    <div>
                      <p className="text-sm text-gray-800">{m.name}</p>
                      <p className="text-[10px] text-gray-500">{m.reason}</p>
                      {m.supplement && <p className="text-[10px] text-brand font-medium">&rarr; {m.supplement} &middot; {m.price}</p>}
                    </div>
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color: pc.color, backgroundColor: pc.bg }}
                  >
                    {m.status}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Other Nutrients */}
          <div>
            <p className="text-xs font-semibold text-gray-500 mb-2">Other Nutrients</p>
            {nd.others.map((o, i) => {
              const pc = priorityColor(o.priority);
              return (
                <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span>{o.icon}</span>
                    <div>
                      <p className="text-sm text-gray-800">{o.name}</p>
                      {o.supplement && <p className="text-[10px] text-brand font-medium">&rarr; {o.supplement} &middot; {o.price}</p>}
                    </div>
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color: pc.color, backgroundColor: pc.bg }}
                  >
                    {o.status}
                  </span>
                </div>
              );
            })}
          </div>

          <button
            onClick={() => onCartClick('c4')}
            className="w-full py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            🛒 Order Supplements
          </button>
        </div>
      )}

      {/* Diet Edit Sheet */}
      <BottomSheet
        open={editSheet}
        onClose={() => { setEditSheet(false); setEditItem(null); }}
        title={editItem ? 'Edit Item' : 'Add Item'}
      >
        <div className="space-y-3">
          {!editItem && (
            <div className="flex gap-2">
              {(['packaged', 'homemade', 'supplement'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setForm({ ...form, type: t })}
                  className="px-4 py-2 rounded-full text-xs font-semibold border"
                  style={form.type === t
                    ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                    : { borderColor: '#E5E5EA', color: '#666' }
                  }
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          )}
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Name</label>
            <input
              type="text"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="e.g., Royal Canin Golden Retriever Adult"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Detail</label>
            <input
              type="text"
              value={form.detail}
              onChange={(e) => setForm({ ...form, detail: e.target.value })}
              placeholder="e.g., 280g/day, 2 scoops"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <button
            onClick={handleSave}
            disabled={saving || !form.label.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Saving...' : editItem ? 'Save Changes' : 'Add Item'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
