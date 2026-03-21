'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, WeightEntry, WeightHistoryResponse } from '@/lib/api';
import {
  updatePreventiveDate, updateWeight, updatePreventiveFrequency,
  getWeightHistory, addWeightEntry, updateMedicineName, addToCart,
} from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CareCard from '@/components/ui/CareCard';
import ReminderBar from '@/components/ui/ReminderBar';
import Toggle from '@/components/ui/Toggle';
import VaxFreqModal from '@/components/ui/VaxFreqModal';
import DateEditSheet from '@/components/ui/DateEditSheet';
import Ring from '@/components/ui/Ring';
import {
  filterByKeywords, getStatusForRecord, formatApiDate,
  VACCINE_KW, DEWORMING_KW, FLEA_TICK_KW, CHECKUP_KW,
  freqToDays, daysToFreq, VAX_FREQ_LABELS,
} from '@/lib/dashboard-utils';

interface HealthTabProps {
  data: DashboardData;
  token: string;
  onUpdated: () => void;
  onCartClick: (itemId?: string) => void;
}

export default function HealthTab({ data, token, onUpdated, onCartClick }: HealthTabProps) {
  const [editingVax, setEditingVax] = useState<string | null>(null);
  const [editingCheckup, setEditingCheckup] = useState<string | null>(null);
  const [weightInput, setWeightInput] = useState('');
  const [weightSaving, setWeightSaving] = useState(false);
  const [weightMsg, setWeightMsg] = useState('');

  // Real weight history from API
  const [weightHistory, setWeightHistory] = useState<WeightEntry[]>([]);
  const [idealRange, setIdealRange] = useState<{ min: number; max: number } | null>(null);
  const [weightLoading, setWeightLoading] = useState(true);

  const records = data.preventive_records || [];
  const vaccines = filterByKeywords(records, VACCINE_KW);
  const deworming = filterByKeywords(records, DEWORMING_KW);
  const fleaTick = filterByKeywords(records, FLEA_TICK_KW);
  const checkups = filterByKeywords(records, CHECKUP_KW);

  const mandatoryVax = vaccines.filter(v => v.category === 'essential');
  const optionalVax = vaccines.filter(v => v.category !== 'essential');

  // Base items — always shown, PetCircle Recommended
  const BASE_CHECKUP_NAMES = ['Vet Visit', 'Blood Work'];
  const baseCheckupItems = BASE_CHECKUP_NAMES.map(name => ({
    key: name,
    name,
    source: 'petcircle' as const,
    record: checkups.find(c => c.item_name.toLowerCase().includes(name.toLowerCase())),
  }));

  // Condition monitoring items — Vet Prescribed, pulled from conditions
  const conditionMonItems = (data.conditions || []).flatMap(cond =>
    cond.monitoring.map(mon => ({
      key: `${cond.id}_${mon.id}`,
      name: mon.name,
      source: 'vet' as const,
      conditionName: cond.name,
      monitoringItem: mon,
    }))
  );

  const allCheckupItems = [...baseCheckupItems, ...conditionMonItems];
  const completedCheckups = allCheckupItems.filter(item =>
    'record' in item
      ? !!(item.record && (item.record.status === 'up_to_date' || item.record.status === 'done'))
      : !!item.monitoringItem.last_done_date
  ).length;

  const pet = data.pet;

  // Load real weight history
  const loadWeightHistory = useCallback(async () => {
    try {
      const resp: WeightHistoryResponse = await getWeightHistory(token);
      setWeightHistory(resp.entries);
      setIdealRange(resp.ideal_range);
    } catch {
      // Fallback: empty list
    } finally {
      setWeightLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadWeightHistory();
  }, [loadWeightHistory]);

  // If no weight history entries but pet has an onboarding weight, show it as synthetic entry
  const effectiveHistory = weightHistory.length === 0 && pet.weight
    ? [{ id: 'onboarding', weight: pet.weight, recorded_at: new Date().toISOString().split('T')[0], note: 'Onboarding weight' } as WeightEntry]
    : weightHistory;

  // Weight history sorted oldest-first for sparkline
  const sortedHistory = [...effectiveHistory].sort((a, b) =>
    (a.recorded_at || '').localeCompare(b.recorded_at || '')
  );
  const sparklineData = sortedHistory.slice(-6);
  const maxWeight = Math.max(...sparklineData.map(w => w.weight), 1);

  const handleDateSave = async (itemName: string, dateStr: string) => {
    await updatePreventiveDate(token, itemName, dateStr);
    onUpdated();
  };

  const handleFreqChange = async (itemName: string, freq: number, unit: string) => {
    const days = freqToDays(freq, unit);
    try {
      await updatePreventiveFrequency(token, itemName, days);
      onUpdated();
    } catch {
      // Silently fail — local state already updated in UI
    }
  };

  const handleMedicineSave = async (itemName: string, medicineName: string) => {
    await updateMedicineName(token, itemName, medicineName);
    onUpdated();
  };

  const handleOrderWithMedicine = async (medicineName: string | null | undefined, category: string, fallbackId: string) => {
    if (medicineName) {
      try {
        const productId = `med_${medicineName.toLowerCase().replace(/\s+/g, '_')}`;
        await addToCart(token, {
          product_id: productId,
          name: medicineName,
          price: 0,
          icon: category === 'deworming' ? '🪱' : '🐛',
          sub: category === 'deworming' ? 'Deworming medicine' : 'Flea & Tick treatment',
          tag: 'Reorder',
          tag_color: '#D44800',
        });
        onCartClick(productId);
      } catch {
        onCartClick(fallbackId);
      }
    } else {
      onCartClick(fallbackId);
    }
  };

  const handleWeightSave = async () => {
    const w = parseFloat(weightInput);
    if (!w || w < 0.01 || w > 999.99) {
      const rangeHint = idealRange
        ? `Expected range for ${pet.breed || pet.species}: ${idealRange.min}–${idealRange.max} kg`
        : `Enter valid weight for your ${pet.species || 'pet'} (0.01–999.99 kg)`;
      setWeightMsg(rangeHint);
      return;
    }
    setWeightSaving(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      await addWeightEntry(token, w, today);
      await updateWeight(token, w);
      setWeightMsg('Saved!');
      setWeightInput('');
      loadWeightHistory();
      onUpdated();
    } catch {
      setWeightMsg('Failed to save');
    } finally {
      setWeightSaving(false);
    }
  };

  const VaxRow = ({ vax, isOptional }: { vax: typeof records[0]; isOptional: boolean }) => {
    const status = getStatusForRecord(vax);
    const initialFreq = daysToFreq(vax.custom_recurrence_days ?? vax.recurrence_days);
    const [reminderOn, setReminderOn] = useState(true);
    const [freq, setFreq] = useState(initialFreq.freq);
    const [freqUnit, setFreqUnit] = useState(initialFreq.unit);
    const [showVaxFreq, setShowVaxFreq] = useState(false);

    // For optional vaccines, derive current months from days
    const currentDays = vax.custom_recurrence_days ?? vax.recurrence_days;
    const currentMonths = Math.round(currentDays / 30) || 12;
    const vaxFreqLabel = VAX_FREQ_LABELS[currentMonths] || `Every ${currentMonths} months`;

    return (
      <div className="py-3 border-b border-gray-50 last:border-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: status === 'overdue' ? '#FF3B30' : status === 'upcoming' ? '#FF9500' : '#34C759' }} />
            <div>
              <p className="text-sm font-medium text-gray-900">{vax.item_name}</p>
              <p className="text-[11px] text-gray-500">
                Given: {formatApiDate(vax.last_done_date)} · Next: {formatApiDate(vax.next_due_date)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            <button onClick={() => setEditingVax(vax.item_name)} className="text-xs text-brand font-semibold">Edit</button>
          </div>
        </div>
        {isOptional && (
          <div className="mt-1 pl-4 flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Reminder</span>
              <button
                onClick={() => setShowVaxFreq(true)}
                className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200"
              >
                {vaxFreqLabel}
              </button>
            </div>
            <Toggle checked={reminderOn} onChange={setReminderOn} />
            <VaxFreqModal
              open={showVaxFreq}
              onClose={() => setShowVaxFreq(false)}
              currentMonths={currentMonths}
              onSave={(months) => {
                handleFreqChange(vax.item_name, months, 'month');
              }}
            />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Vaccinations */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>💉</span> Vaccinations
        </h3>
        {mandatoryVax.length > 0 && (
          <div className="mb-3">
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Mandatory</p>
            {mandatoryVax.map(v => <VaxRow key={v.item_name} vax={v} isOptional={false} />)}
          </div>
        )}
        {optionalVax.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Optional</p>
            {optionalVax.map(v => <VaxRow key={v.item_name} vax={v} isOptional={true} />)}
          </div>
        )}
        {vaccines.length === 0 && (
          <p className="text-xs text-gray-400 py-4 text-center">No vaccine records found</p>
        )}
        {vaccines.some(v => getStatusForRecord(v) === 'overdue') && (
          <button
            onClick={() => onCartClick('c1')}
            className="w-full mt-3 py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Book Now
          </button>
        )}
      </div>

      {/* Deworming */}
      {deworming.length > 0 ? deworming.map(d => (
        <CareCard
          key={d.item_name}
          icon="🪱"
          title={d.item_name}
          product={d.medicine_name || undefined}
          lastDone={d.last_done_date}
          nextDue={d.next_due_date}
          status={getStatusForRecord(d)}
          recurrenceDays={d.recurrence_days}
          medicineDependant={d.medicine_dependent}
          medicineName={d.medicine_name}
          onDateSave={(dateStr) => handleDateSave(d.item_name, dateStr)}
          onOrderClick={() => handleOrderWithMedicine(d.medicine_name, 'deworming', 'c2')}
          onFreqChange={(f, u) => handleFreqChange(d.item_name, f, u)}
          onMedicineSave={(name) => handleMedicineSave(d.item_name, name)}
        />
      )) : (
        <CareCard
          icon="🪱" title="Deworming" product="No record found"
          lastDone={null} nextDue={null} status="missing" recurrenceDays={90}
          onDateSave={() => Promise.resolve()} onOrderClick={() => onCartClick('c2')}
        />
      )}

      {/* Flea & Tick */}
      {fleaTick.length > 0 ? fleaTick.map(f => (
        <CareCard
          key={f.item_name}
          icon="🐛"
          title={f.item_name}
          product={f.medicine_name || undefined}
          lastDone={f.last_done_date}
          nextDue={f.next_due_date}
          status={getStatusForRecord(f)}
          recurrenceDays={f.recurrence_days}
          medicineDependant={f.medicine_dependent}
          medicineName={f.medicine_name}
          onDateSave={(dateStr) => handleDateSave(f.item_name, dateStr)}
          onOrderClick={() => handleOrderWithMedicine(f.medicine_name, 'flea_tick', 'c5')}
          onFreqChange={(freq, unit) => handleFreqChange(f.item_name, freq, unit)}
          onMedicineSave={(name) => handleMedicineSave(f.item_name, name)}
        />
      )) : (
        <CareCard
          icon="🐛" title="Flea & Tick" product="No record found"
          lastDone={null} nextDue={null} status="missing" recurrenceDays={30}
          onDateSave={() => Promise.resolve()} onOrderClick={() => onCartClick('c5')}
        />
      )}

      {/* Preventive Checkup */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>🩺</span> Preventive Checkup
        </h3>
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">{completedCheckups}/{allCheckupItems.length} completed</span>
            <span className="text-xs font-semibold" style={{ color: completedCheckups >= allCheckupItems.length ? '#34C759' : '#FF9500' }}>
              {allCheckupItems.length > 0 ? Math.round((completedCheckups / allCheckupItems.length) * 100) : 0}%
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${allCheckupItems.length > 0 ? (completedCheckups / allCheckupItems.length) * 100 : 0}%`, background: 'var(--brand-gradient)' }} />
          </div>
        </div>
        {allCheckupItems.map((item) => {
          if (item.source === 'petcircle') {
            const status = item.record ? getStatusForRecord(item.record) : 'missing';
            const isDone = status === 'up_to_date' || status === 'done';
            return (
              <div key={item.key} className="py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className="w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center"
                      style={{ borderColor: isDone ? '#34C759' : '#E5E5EA' }}
                    >
                      {isDone && <span className="text-green-500 text-xs">✓</span>}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm text-gray-800">{item.name}</span>
                        <span style={{ background: '#FFF3EE', color: '#D44800', borderRadius: 20, padding: '1px 7px', fontSize: 9, fontWeight: 700, flexShrink: 0 }}>
                          🐾 PetCircle
                        </span>
                      </div>
                      {item.record?.last_done_date && (
                        <p className="text-[10px] text-gray-400 mt-0.5">Last: {formatApiDate(item.record.last_done_date)}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={status} />
                    <button
                      onClick={() => setEditingCheckup(item.record?.item_name || item.name)}
                      className="text-xs text-brand font-semibold"
                    >
                      Log
                    </button>
                  </div>
                </div>
              </div>
            );
          } else {
            // Vet-prescribed condition monitoring item
            const mon = item.monitoringItem;
            const monStatus = (() => {
              if (!mon.next_due_date) return 'upcoming';
              const today = new Date(); today.setHours(0, 0, 0, 0);
              const due = new Date(mon.next_due_date);
              if (isNaN(due.getTime())) return 'upcoming';
              const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
              return diff < 0 ? 'overdue' : diff <= 30 ? 'upcoming' : 'done';
            })();
            const isDone = !!mon.last_done_date;
            return (
              <div key={item.key} className="py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className="w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center"
                      style={{ borderColor: isDone ? '#34C759' : '#E5E5EA' }}
                    >
                      {isDone && <span className="text-green-500 text-xs">✓</span>}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm text-gray-800">{mon.name}</span>
                        <span style={{ background: '#F0F6FF', color: '#007AFF', borderRadius: 20, padding: '1px 7px', fontSize: 9, fontWeight: 700, flexShrink: 0 }}>
                          Vet Prescribed
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-400 mt-0.5">{item.conditionName}</p>
                      {mon.last_done_date && (
                        <p className="text-[10px] text-gray-400">Last: {formatApiDate(mon.last_done_date)}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    <StatusBadge status={monStatus} />
                  </div>
                </div>
              </div>
            );
          }
        })}
      </div>

      {/* Weight Log */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span className="w-8 h-8 rounded-full flex items-center justify-center text-base" style={{ backgroundColor: '#F0F6FF' }}>⚖️</span>
          <div>
            <span>Weight Log</span>
            {idealRange && (
              <p className="text-[10px] text-gray-400 font-normal">Ideal range for {pet.breed}: {idealRange.min}–{idealRange.max} kg</p>
            )}
          </div>
        </h3>

        {/* Current weight + trend */}
        <div className="flex items-center gap-3 mb-3">
          <Ring percentage={pet.weight ? Math.min((pet.weight / (idealRange?.max || 40)) * 100, 100) : 0} size={60} strokeWidth={6} color="#D44800">
            <span className="text-xs font-bold">{pet.weight || '—'}</span>
          </Ring>
          <div>
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-bold text-gray-900">{pet.weight ? `${pet.weight} kg` : 'Not set'}</p>
              {(() => {
                if (weightHistory.length < 2 || !pet.weight) return null;
                const prev = weightHistory[1]?.weight;
                if (!prev) return null;
                const diff = Math.round((pet.weight - prev) * 10) / 10;
                if (diff === 0) return <span className="text-xs text-blue-500 font-medium">→ stable</span>;
                const isUp = diff > 0;
                return (
                  <span className={`text-xs font-medium ${isUp ? 'text-amber-500' : 'text-green-500'}`}>
                    {isUp ? '↑' : '↓'} {Math.abs(diff)} kg since last
                  </span>
                );
              })()}
            </div>
            <p className="text-[11px] text-gray-500">Current weight</p>
          </div>
        </div>

        {/* In-range status banner */}
        {pet.weight && idealRange && (
          <div
            className="rounded-xl px-3 py-2 mb-3 text-xs font-medium"
            style={
              pet.weight >= idealRange.min && pet.weight <= idealRange.max
                ? { backgroundColor: '#F0FFF4', color: '#15803d' }
                : { backgroundColor: '#FFF6ED', color: '#92400e' }
            }
          >
            {pet.weight >= idealRange.min && pet.weight <= idealRange.max
              ? `✅ Weight is within healthy range for ${pet.breed}`
              : pet.weight > idealRange.max
                ? `⚠️ Weight slightly above ideal — monitor closely`
                : `⚠️ Weight slightly below ideal — monitor closely`}
          </div>
        )}

        {/* Sparkline with labels */}
        {sparklineData.length >= 1 && (
          <div className="mb-3">
            <svg viewBox={`0 0 ${Math.max(sparklineData.length, 2) * 50} 90`} className="w-full h-20">
              {sparklineData.map((w, i) => {
                const maxBarH = 40;
                const minBarH = 6;
                const h = Math.max((w.weight / maxWeight) * maxBarH, minBarH);
                const barBase = 70;
                const year = w.recorded_at ? new Date(w.recorded_at).getFullYear().toString().slice(-2) : '';
                return (
                  <g key={i}>
                    {/* Weight label above bar */}
                    <text
                      x={i * 50 + 25}
                      y={barBase - h - 4}
                      textAnchor="middle"
                      fontSize="8"
                      fill="#666"
                      fontWeight="500"
                    >
                      {w.weight}
                    </text>
                    <rect
                      x={i * 50 + 10}
                      y={barBase - h}
                      width={30}
                      height={h}
                      rx={4}
                      fill={i === sparklineData.length - 1 ? '#007AFF' : '#FFD5C2'}
                    />
                    {/* Year label below bar */}
                    {year && (
                      <text
                        x={i * 50 + 25}
                        y={83}
                        textAnchor="middle"
                        fontSize="8"
                        fill="#999"
                      >
                        {`'${year}`}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        )}

        {/* Log table with notes + Latest badge */}
        {weightLoading ? (
          <p className="text-xs text-gray-400 py-2 text-center">Loading history...</p>
        ) : (
          <div className="space-y-0 mb-3 border border-gray-100 rounded-xl overflow-hidden">
            {effectiveHistory.slice(0, 5).map((w, idx) => (
              <div
                key={w.id}
                className="flex items-center justify-between text-xs px-3 py-2 border-b border-gray-50 last:border-0"
                style={idx === 0 ? { backgroundColor: '#F0F6FF' } : {}}
              >
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">{w.recorded_at ? formatApiDate(w.recorded_at) : '—'}</span>
                  {idx === 0 && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-600">Latest</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {w.note && <span className="text-[10px] text-gray-400 truncate max-w-[120px]">{w.note}</span>}
                  <span className="font-medium text-gray-800 shrink-0">{w.weight} kg</span>
                </div>
              </div>
            ))}
            {effectiveHistory.length === 0 && (
              <p className="text-xs text-gray-400 py-3 text-center">No weight entries yet</p>
            )}
          </div>
        )}

        {/* Log weight */}
        <div className="flex gap-2">
          <input
            type="number"
            step="0.1"
            value={weightInput}
            onChange={(e) => setWeightInput(e.target.value)}
            placeholder="Enter weight (kg)"
            className="flex-1 px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
          />
          <button
            onClick={handleWeightSave}
            disabled={weightSaving}
            className="px-4 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {weightSaving ? '...' : 'Log'}
          </button>
        </div>
        {weightMsg && <p className="text-xs text-gray-500 mt-1">{weightMsg}</p>}
      </div>

      {/* Date Edit Sheets */}
      {editingVax && (
        <DateEditSheet
          open={!!editingVax}
          onClose={() => setEditingVax(null)}
          title={`Edit ${editingVax}`}
          subtitle="When was this vaccine given?"
          currentDate={vaccines.find(v => v.item_name === editingVax)?.last_done_date || null}
          recurrenceDays={vaccines.find(v => v.item_name === editingVax)?.recurrence_days}
          onSave={(d) => handleDateSave(editingVax, d)}
        />
      )}
      {editingCheckup && (
        <DateEditSheet
          open={!!editingCheckup}
          onClose={() => setEditingCheckup(null)}
          title={`Log ${editingCheckup}`}
          subtitle="When was this last done?"
          currentDate={checkups.find(c => c.item_name.toLowerCase().includes(editingCheckup.toLowerCase()))?.last_done_date || null}
          recurrenceDays={365}
          onSave={(d) => handleDateSave(editingCheckup, d)}
        />
      )}
    </div>
  );
}
