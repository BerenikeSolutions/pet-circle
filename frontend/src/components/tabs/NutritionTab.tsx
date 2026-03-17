'use client';

import { useState, useEffect } from 'react';
import type { DashboardData } from '@/lib/api';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import { MOCK_NUTRITION_DATA, STATUS_CONFIG } from '@/lib/dashboard-utils';

interface NutritionTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
}

interface DietItem {
  id: string;
  name: string;
  brand: string;
  quantity: string;
  type: 'food' | 'supplement';
}

export default function NutritionTab({ data, token, onCartClick }: NutritionTabProps) {
  const [diet, setDiet] = useState<DietItem[]>([]);
  const [editSheet, setEditSheet] = useState(false);
  const [editItem, setEditItem] = useState<DietItem | null>(null);
  const [form, setForm] = useState({ name: '', brand: '', quantity: '', type: 'food' as 'food' | 'supplement' });

  const storageKey = `petcircle_diet_${token}`;

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) setDiet(JSON.parse(saved));
  }, [storageKey]);

  const saveDiet = (list: DietItem[]) => {
    setDiet(list);
    localStorage.setItem(storageKey, JSON.stringify(list));
  };

  const handleSave = () => {
    const item: DietItem = {
      id: editItem?.id || Date.now().toString(),
      name: form.name, brand: form.brand, quantity: form.quantity, type: form.type,
    };
    if (editItem) {
      saveDiet(diet.map(d => d.id === editItem.id ? item : d));
    } else {
      saveDiet([...diet, item]);
    }
    setEditSheet(false);
    setEditItem(null);
  };

  const foods = diet.filter(d => d.type === 'food');
  const supplements = diet.filter(d => d.type === 'supplement');
  const nd = MOCK_NUTRITION_DATA;

  return (
    <div className="space-y-4">
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
                  <p className="text-sm font-medium text-gray-900">{f.name}</p>
                  <p className="text-[11px] text-gray-500">{f.brand} · {f.quantity}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setEditItem(f); setForm(f); setEditSheet(true); }} className="text-xs text-brand font-semibold">Edit</button>
                  <button onClick={() => saveDiet(diet.filter(d => d.id !== f.id))} className="text-xs text-red-500 font-semibold">×</button>
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
                  <p className="text-sm font-medium text-gray-900">{s.name}</p>
                  <p className="text-[11px] text-gray-500">{s.brand} · {s.quantity}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setEditItem(s); setForm(s); setEditSheet(true); }} className="text-xs text-brand font-semibold">Edit</button>
                  <button onClick={() => saveDiet(diet.filter(d => d.id !== s.id))} className="text-xs text-red-500 font-semibold">×</button>
                </div>
              </div>
            ))}
          </div>
        )}
        {diet.length === 0 && <p className="text-xs text-gray-400 py-3 text-center">No diet items added yet</p>}
        <AddRow label="Add Food/Supplement" onClick={() => {
          setEditItem(null);
          setForm({ name: '', brand: '', quantity: '', type: 'food' });
          setEditSheet(true);
        }} />
      </div>

      {/* Nutrition Note (shared with Overview) */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <span>🥗</span> Nutrition Note
        </h3>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#FFF6ED', borderLeft: '3px solid #FF9500' }}>
          <p className="text-xs font-semibold text-amber-800 mb-1">Overall Diet</p>
          <p className="text-xs text-amber-700">
            {nd.calories.current}/{nd.calories.target} kcal/day — slightly below target.
          </p>
        </div>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#F0F6FF', borderLeft: '3px solid #007AFF' }}>
          <p className="text-xs font-semibold text-blue-800 mb-1">What to Improve</p>
          <ul className="space-y-1">
            {nd.improve.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-blue-700">
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: item.dot }} />
                {item.text}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#F0FFF4', borderLeft: '3px solid #34C759' }}>
          <p className="text-xs font-semibold text-green-800 mb-1">Recommendation</p>
          <p className="text-xs text-green-700">Consider adding joint supplements and increasing protein intake.</p>
        </div>
      </div>

      {/* Nutrition Breakdown */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-4">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <span>📊</span> Nutrition Breakdown
        </h3>

        {/* Calories */}
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-500">Daily Calories</span>
            <span className="font-semibold">{nd.calories.current}/{nd.calories.target} {nd.calories.unit}</span>
          </div>
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min((nd.calories.current / nd.calories.target) * 100, 100)}%`,
                background: nd.calories.current >= nd.calories.target ? '#34C759' : 'var(--brand-gradient)',
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
                    width: `${Math.min((m.actual / m.target) * 100, 100)}%`,
                    backgroundColor: m.status === 'ok' ? '#34C759' : m.status === 'low' ? '#FF9500' : '#FF3B30',
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
          {nd.vitamins.map((v, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div>
                <p className="text-sm text-gray-800">{v.name}</p>
                {v.supplement && <p className="text-[10px] text-gray-500">→ {v.supplement} · {v.price}</p>}
              </div>
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{
                  color: v.priority === 'ok' ? '#34C759' : v.priority === 'high' ? '#FF3B30' : '#FF9500',
                  backgroundColor: v.priority === 'ok' ? '#F0FFF4' : v.priority === 'high' ? '#FFF0F0' : '#FFF6ED',
                }}
              >
                {v.status}
              </span>
            </div>
          ))}
        </div>

        {/* Minerals */}
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-2">Minerals</p>
          {nd.minerals.map((m, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div className="flex items-center gap-2">
                <span>{m.icon}</span>
                <div>
                  <p className="text-sm text-gray-800">{m.name}</p>
                  <p className="text-[10px] text-gray-500">{m.reason}</p>
                  {m.supplement && <p className="text-[10px] text-brand font-medium">→ {m.supplement} · {m.price}</p>}
                </div>
              </div>
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{
                  color: m.priority === 'ok' ? '#34C759' : m.priority === 'urgent' ? '#FF3B30' : '#FF9500',
                  backgroundColor: m.priority === 'ok' ? '#F0FFF4' : m.priority === 'urgent' ? '#FFF0F0' : '#FFF6ED',
                }}
              >
                {m.status}
              </span>
            </div>
          ))}
        </div>

        {/* Other Nutrients */}
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-2">Other Nutrients</p>
          {nd.others.map((o, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div className="flex items-center gap-2">
                <span>{o.icon}</span>
                <div>
                  <p className="text-sm text-gray-800">{o.name}</p>
                  <p className="text-[10px] text-gray-500">{o.reason}</p>
                  {o.supplement && <p className="text-[10px] text-brand font-medium">→ {o.supplement} · {o.price}</p>}
                </div>
              </div>
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{
                  color: o.priority === 'ok' ? '#34C759' : '#FF9500',
                  backgroundColor: o.priority === 'ok' ? '#F0FFF4' : '#FFF6ED',
                }}
              >
                {o.status}
              </span>
            </div>
          ))}
        </div>

        <button
          onClick={() => onCartClick('c4')}
          className="w-full py-2.5 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          🛒 Order Supplements
        </button>
      </div>

      {/* Diet Edit Sheet */}
      <BottomSheet
        open={editSheet}
        onClose={() => { setEditSheet(false); setEditItem(null); }}
        title={editItem ? 'Edit Item' : 'Add Item'}
      >
        <div className="space-y-3">
          <div className="flex gap-2">
            {(['food', 'supplement'] as const).map(t => (
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
          {['name', 'brand', 'quantity'].map(field => (
            <div key={field}>
              <label className="text-xs font-semibold text-gray-500 mb-1 block capitalize">{field}</label>
              <input
                type="text"
                value={(form as any)[field]}
                onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                placeholder={field === 'quantity' ? 'e.g., 200g/day' : ''}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
            </div>
          ))}
          <button
            onClick={handleSave}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {editItem ? 'Save Changes' : 'Add Item'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
