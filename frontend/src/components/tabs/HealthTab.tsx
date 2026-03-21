'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, WeightEntry, WeightHistoryResponse } from '@/lib/api';
import {
  updatePreventiveDate, updateWeight, updatePreventiveFrequency,
  getWeightHistory, addWeightEntry,
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

  const mandatoryVax = vaccines.filter(v => ['rabies', 'dhpp'].some(k => v.item_name.toLowerCase().includes(k)));
  const optionalVax = vaccines.filter(v => !['rabies', 'dhpp'].some(k => v.item_name.toLowerCase().includes(k)));

  const checkupItems = ['Vet Visit', 'Blood Work', 'X-Ray', 'Urinalysis', 'Fecal Test'];
  const completedCheckups = checkups.filter(c => c.status === 'up_to_date' || c.status === 'done').length;

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

  // Weight history sorted oldest-first for sparkline
  const sortedHistory = [...weightHistory].sort((a, b) =>
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

  const handleWeightSave = async () => {
    const w = parseFloat(weightInput);
    if (!w || w < 0.01 || w > 999.99) { setWeightMsg('Enter valid weight (0.01–999.99)'); return; }
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
          product="Bayer Drontal Plus"
          lastDone={d.last_done_date}
          nextDue={d.next_due_date}
          status={getStatusForRecord(d)}
          recurrenceDays={d.recurrence_days}
          onDateSave={(dateStr) => handleDateSave(d.item_name, dateStr)}
          onOrderClick={() => onCartClick('c2')}
          onFreqChange={(f, u) => handleFreqChange(d.item_name, f, u)}
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
          product="NexGard"
          lastDone={f.last_done_date}
          nextDue={f.next_due_date}
          status={getStatusForRecord(f)}
          recurrenceDays={f.recurrence_days}
          onDateSave={(dateStr) => handleDateSave(f.item_name, dateStr)}
          onOrderClick={() => onCartClick('c5')}
          onFreqChange={(freq, unit) => handleFreqChange(f.item_name, freq, unit)}
        />
      )) : (
        <CareCard
          icon="🐛" title="Flea & Tick" product="No record found"
          lastDone={null} nextDue={null} status="missing" recurrenceDays={30}
          onDateSave={() => Promise.resolve()} onOrderClick={() => onCartClick('c5')}
        />
      )}

      {/* Annual Checkups */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>🩺</span> Annual Health Checkups
        </h3>
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">{completedCheckups}/{checkupItems.length} completed</span>
            <span className="text-xs font-semibold" style={{ color: completedCheckups >= checkupItems.length ? '#34C759' : '#FF9500' }}>
              {Math.round((completedCheckups / checkupItems.length) * 100)}%
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${(completedCheckups / checkupItems.length) * 100}%`, background: 'var(--brand-gradient)' }} />
          </div>
        </div>
        {checkupItems.map((item, i) => {
          const match = checkups.find(c => c.item_name.toLowerCase().includes(item.toLowerCase()));
          const status = match ? getStatusForRecord(match) : 'missing';
          return (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full border-2 flex items-center justify-center"
                  style={{ borderColor: status === 'up_to_date' || status === 'done' ? '#34C759' : '#E5E5EA' }}
                >
                  {(status === 'up_to_date' || status === 'done') && <span className="text-green-500 text-xs">✓</span>}
                </div>
                <span className="text-sm text-gray-800">{item}</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={status} />
                <button onClick={() => setEditingCheckup(match?.item_name || item)} className="text-xs text-brand font-semibold">Edit</button>
              </div>
            </div>
          );
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
        {sparklineData.length > 1 && (
          <div className="mb-3">
            <svg viewBox={`0 0 ${sparklineData.length * 50} 80`} className="w-full h-16">
              {sparklineData.map((w, i) => {
                const h = (w.weight / maxWeight) * 50;
                const year = w.recorded_at ? new Date(w.recorded_at).getFullYear().toString().slice(-2) : '';
                return (
                  <g key={i}>
                    {/* Weight label above bar */}
                    <text
                      x={i * 50 + 25}
                      y={55 - h - 4}
                      textAnchor="middle"
                      fontSize="8"
                      fill="#666"
                      fontWeight="500"
                    >
                      {w.weight}
                    </text>
                    <rect
                      x={i * 50 + 10}
                      y={55 - h}
                      width={30}
                      height={h}
                      rx={4}
                      fill={i === sparklineData.length - 1 ? '#007AFF' : '#FFD5C2'}
                    />
                    {/* Year label below bar */}
                    {year && (
                      <text
                        x={i * 50 + 25}
                        y={70}
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
            {weightHistory.slice(0, 5).map((w, idx) => (
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
            {weightHistory.length === 0 && (
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
          title={`Edit ${editingCheckup}`}
          subtitle="When was this last done?"
          currentDate={checkups.find(c => c.item_name === editingCheckup)?.last_done_date || null}
          recurrenceDays={365}
          onSave={(d) => handleDateSave(editingCheckup, d)}
        />
      )}
    </div>
  );
}
