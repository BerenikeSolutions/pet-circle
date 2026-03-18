'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, HygienePreference } from '@/lib/api';
import {
  getHygienePreferences, addHygieneItem, updateHygienePreference,
  updateHygieneDate, deleteHygieneItem,
} from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import ReminderBar from '@/components/ui/ReminderBar';
import DateEditSheet from '@/components/ui/DateEditSheet';
import BottomSheet from '@/components/ui/BottomSheet';
import AddRow from '@/components/ui/AddRow';
import { freqLabel, addByUnit, formatDMY } from '@/lib/dashboard-utils';

interface HygieneTabProps {
  data: DashboardData;
  token: string;
  onUpdated: () => void;
  onCartClick: (itemId?: string) => void;
}

const HYGIENE_EMOJIS = ['🪮', '🦷', '👂', '👁️', '🛁', '🐾', '✂️', '🧴', '🧽', '🧹', '💅', '🪥', '🧼', '💧'];

function computeStatus(item: HygienePreference): string {
  if (!item.last_done) return 'upcoming';

  let lastDate: Date | null = null;
  if (item.last_done.includes('/')) {
    const [d, m, y] = item.last_done.split('/');
    lastDate = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
  } else {
    lastDate = new Date(item.last_done);
  }
  if (isNaN(lastDate.getTime())) return 'upcoming';

  const now = new Date();
  const diffMs = now.getTime() - lastDate.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);

  let intervalDays = item.freq;
  switch (item.unit) {
    case 'week': intervalDays = item.freq * 7; break;
    case 'month': intervalDays = item.freq * 30; break;
    case 'year': intervalDays = item.freq * 365; break;
  }

  if (diffDays <= 1 && item.unit === 'day') return 'done';
  if (diffDays > intervalDays) return 'overdue';
  if (diffDays > intervalDays * 0.8) return 'upcoming';
  return 'done';
}

function formatLastDone(lastDone: string | null): string {
  if (!lastDone) return 'Not recorded';

  let d: Date | null = null;
  if (lastDone.includes('/')) {
    const [day, month, year] = lastDone.split('/');
    d = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
  } else {
    d = new Date(lastDone);
  }
  if (!d || isNaN(d.getTime())) return lastDone;

  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function computeNextDue(item: HygienePreference): string | null {
  if (!item.last_done) return null;
  const next = addByUnit(item.last_done, item.freq, item.unit);
  return next === '—' ? null : next;
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className || ''}`} />;
}

export default function HygieneTab({ data, token, onUpdated, onCartClick }: HygieneTabProps) {
  const [items, setItems] = useState<HygienePreference[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dateEditing, setDateEditing] = useState<HygienePreference | null>(null);

  // Add item sheet
  const [addSheet, setAddSheet] = useState(false);
  const [addCategory, setAddCategory] = useState<'daily' | 'periodic'>('daily');
  const [addForm, setAddForm] = useState({ name: '', icon: '🧹', freq: 1, unit: 'month' });

  const breed = data.pet.breed || 'your breed';

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const prefs = await getHygienePreferences(token);
      setItems(prefs);
    } catch (e: any) {
      setError(e.message || 'Failed to load hygiene data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const dailyItems = items.filter(i => i.category === 'daily');
  const periodicItems = items.filter(i => i.category === 'periodic');

  const handleFreqSave = async (itemId: string, freq: number, unit: string) => {
    const item = items.find(i => i.item_id === itemId);
    if (!item) return;
    setSaving(true);
    try {
      await updateHygienePreference(token, itemId, { freq, unit, reminder: item.reminder });
      await loadData();
    } catch (e: any) {
      setError(e.message || 'Failed to update frequency');
    } finally {
      setSaving(false);
    }
  };

  const handleReminderToggle = async (itemId: string, value: boolean) => {
    const item = items.find(i => i.item_id === itemId);
    if (!item) return;
    setItems(prev => prev.map(i => i.item_id === itemId ? { ...i, reminder: value } : i));
    try {
      await updateHygienePreference(token, itemId, { freq: item.freq, unit: item.unit, reminder: value });
    } catch (e: any) {
      setItems(prev => prev.map(i => i.item_id === itemId ? { ...i, reminder: !value } : i));
      setError(e.message || 'Failed to update reminder');
    }
  };

  const handleDateSave = async (itemId: string, dateStr: string) => {
    setSaving(true);
    try {
      await updateHygieneDate(token, itemId, dateStr);
      await loadData();
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Failed to update date');
    } finally {
      setSaving(false);
    }
  };

  const handleAddItem = async () => {
    if (!addForm.name.trim()) return;
    setSaving(true);
    try {
      await addHygieneItem(token, {
        name: addForm.name.trim(),
        icon: addForm.icon,
        category: addCategory,
        freq: addForm.freq,
        unit: addForm.unit,
      });
      setAddSheet(false);
      setAddForm({ name: '', icon: '🧹', freq: 1, unit: 'month' });
      await loadData();
    } catch (e: any) {
      setError(e.message || 'Failed to add item');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (itemId: string) => {
    setSaving(true);
    try {
      await deleteHygieneItem(token, itemId);
      await loadData();
    } catch (e: any) {
      setError(e.message || 'Failed to delete item');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-40" />
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
          <Skeleton className="h-5 w-36" />
          {[1, 2].map(i => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      </div>
    );
  }

  const renderDailyItem = (item: HygienePreference) => {
    const status = computeStatus(item);
    const lastDone = formatLastDone(item.last_done);

    return (
      <div key={item.item_id} className="py-3 border-b border-gray-50 last:border-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-lg">{item.icon}</span>
            <div>
              <p className="text-sm font-medium text-gray-900">{item.name}</p>
              <p className="text-[11px] text-gray-500">Last: {lastDone}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            {!item.is_default && (
              <button
                onClick={() => handleDelete(item.item_id)}
                disabled={saving}
                className="text-xs text-red-500 font-semibold"
              >
                &times;
              </button>
            )}
          </div>
        </div>
        <div className="pl-8 mt-1">
          <ReminderBar
            enabled={item.reminder}
            onToggle={(v) => handleReminderToggle(item.item_id, v)}
            freq={item.freq}
            unit={item.unit}
            onFreqChange={(f, u) => handleFreqSave(item.item_id, f, u)}
          />
        </div>
      </div>
    );
  };

  const renderPeriodicItem = (item: HygienePreference) => {
    const status = computeStatus(item);
    const lastDone = formatLastDone(item.last_done);
    const nextDue = computeNextDue(item);

    return (
      <div key={item.item_id} className="py-3 border-b border-gray-50 last:border-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-lg">{item.icon}</span>
            <div>
              <p className="text-sm font-medium text-gray-900">{item.name}</p>
              <p className="text-[11px] text-gray-500">Last: {lastDone}</p>
              {nextDue && (
                <p className="text-[11px] text-gray-500">
                  Next due: <span className="font-medium text-gray-700">{nextDue}</span>
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            <button
              onClick={() => setDateEditing(item)}
              className="text-xs text-brand font-semibold"
            >
              Edit
            </button>
            {!item.is_default && (
              <button
                onClick={() => handleDelete(item.item_id)}
                disabled={saving}
                className="text-xs text-red-500 font-semibold"
              >
                &times;
              </button>
            )}
          </div>
        </div>
        <div className="pl-8 mt-1">
          <ReminderBar
            enabled={item.reminder}
            onToggle={(v) => handleReminderToggle(item.item_id, v)}
            freq={item.freq}
            unit={item.unit}
            onFreqChange={(f, u) => handleFreqSave(item.item_id, f, u)}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-700">
          {error}
          <button onClick={() => { setError(null); loadData(); }} className="ml-2 underline">Retry</button>
        </div>
      )}

      {/* Breed Note */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
        <p className="text-xs text-amber-800">
          <span className="font-semibold">Note:</span> Frequencies are breed-adjusted for {breed}.
        </p>
      </div>

      {/* Frequent Activities */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm mb-3">Frequent Activities</h3>
        <div className="space-y-0">
          {dailyItems.map(item => renderDailyItem(item))}
        </div>
        <div className="mt-3">
          <AddRow label="Add Activity" onClick={() => {
            setAddCategory('daily');
            setAddForm({ name: '', icon: '🧹', freq: 1, unit: 'day' });
            setAddSheet(true);
          }} />
        </div>
      </div>

      {/* Periodic Grooming */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm mb-3">Periodic Grooming</h3>
        <div className="space-y-0">
          {periodicItems.map(item => renderPeriodicItem(item))}
        </div>
        <div className="mt-3">
          <AddRow label="Add Grooming Item" onClick={() => {
            setAddCategory('periodic');
            setAddForm({ name: '', icon: '🛁', freq: 1, unit: 'month' });
            setAddSheet(true);
          }} />
        </div>
        <button
          onClick={() => onCartClick('c7')}
          className="w-full mt-3 py-2.5 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Book Now
        </button>
      </div>

      {/* DateEditSheet */}
      {dateEditing && (
        <DateEditSheet
          open={!!dateEditing}
          onClose={() => setDateEditing(null)}
          title={`Edit ${dateEditing.name}`}
          subtitle="When was this last done?"
          currentDate={dateEditing.last_done || null}
          recurrenceDays={
            dateEditing.unit === 'day' ? dateEditing.freq :
            dateEditing.unit === 'week' ? dateEditing.freq * 7 :
            dateEditing.unit === 'month' ? dateEditing.freq * 30 :
            dateEditing.freq * 365
          }
          onSave={async (d) => {
            await handleDateSave(dateEditing.item_id, d);
            setDateEditing(null);
          }}
        />
      )}

      {/* Add Item BottomSheet */}
      <BottomSheet
        open={addSheet}
        onClose={() => { setAddSheet(false); }}
        title={addCategory === 'daily' ? 'Add Activity' : 'Add Grooming Item'}
      >
        <div className="space-y-4">
          {/* Name */}
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Name</label>
            <input
              type="text"
              value={addForm.name}
              onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
              placeholder={addCategory === 'daily' ? 'e.g., Paw wiping' : 'e.g., Haircut'}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>

          {/* Icon Picker */}
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Icon</label>
            <div className="flex flex-wrap gap-2">
              {HYGIENE_EMOJIS.map(emoji => (
                <button
                  key={emoji}
                  onClick={() => setAddForm({ ...addForm, icon: emoji })}
                  className="w-9 h-9 rounded-lg text-lg flex items-center justify-center border-2 transition-colors"
                  style={{
                    borderColor: addForm.icon === emoji ? '#D44800' : '#E5E5EA',
                    backgroundColor: addForm.icon === emoji ? '#FFF3ED' : 'white',
                  }}
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>

          {/* Frequency */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Every</label>
              <input
                type="number"
                min={1}
                max={365}
                value={addForm.freq}
                onChange={(e) => setAddForm({ ...addForm, freq: Math.max(1, parseInt(e.target.value) || 1) })}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Period</label>
              <select
                value={addForm.unit}
                onChange={(e) => setAddForm({ ...addForm, unit: e.target.value })}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand bg-white"
              >
                <option value="day">Day(s)</option>
                <option value="week">Week(s)</option>
                <option value="month">Month(s)</option>
                <option value="year">Year(s)</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleAddItem}
            disabled={saving || !addForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Adding...' : 'Add Item'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
