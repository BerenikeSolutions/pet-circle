'use client';

import { useState } from 'react';
import type { DashboardData } from '@/lib/api';
import { updatePreventiveDate, updateWeight } from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CareCard from '@/components/ui/CareCard';
import ReminderBar from '@/components/ui/ReminderBar';
import DateEditSheet from '@/components/ui/DateEditSheet';
import Ring from '@/components/ui/Ring';
import {
  filterByKeywords, getStatusForRecord, formatApiDate,
  buildMockWeightHistory,
  VACCINE_KW, DEWORMING_KW, FLEA_TICK_KW, CHECKUP_KW,
  VAX_FREQ_OPTS, VAX_FREQ_LABELS,
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
  const weightHistory = buildMockWeightHistory(pet.weight, pet.dob);
  const maxWeight = Math.max(...weightHistory.map(w => w.weight), 1);

  const handleDateSave = async (itemName: string, dateStr: string) => {
    await updatePreventiveDate(token, itemName, dateStr);
    onUpdated();
  };

  const handleWeightSave = async () => {
    const w = parseFloat(weightInput);
    if (!w || w < 0.01 || w > 999.99) { setWeightMsg('Enter valid weight (0.01–999.99)'); return; }
    setWeightSaving(true);
    try {
      await updateWeight(token, w);
      setWeightMsg('Saved!');
      setWeightInput('');
      onUpdated();
    } catch {
      setWeightMsg('Failed to save');
    } finally {
      setWeightSaving(false);
    }
  };

  const VaxRow = ({ vax, isOptional }: { vax: typeof records[0]; isOptional: boolean }) => {
    const status = getStatusForRecord(vax);
    const [reminderOn, setReminderOn] = useState(true);
    const [freq, setFreq] = useState(12);
    const [freqUnit, setFreqUnit] = useState('month');

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
          <div className="mt-1 pl-4">
            <ReminderBar
              enabled={reminderOn}
              onToggle={setReminderOn}
              freq={freq}
              unit={freqUnit}
              onFreqChange={(f, u) => { setFreq(f); setFreqUnit(u); }}
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
        <button
          onClick={() => onCartClick('c14')}
          className="w-full mt-3 py-2.5 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Book Now
        </button>
      </div>

      {/* Weight Log */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>⚖️</span> Weight Log
        </h3>
        <div className="flex items-center gap-3 mb-3">
          <Ring percentage={pet.weight ? Math.min((pet.weight / 40) * 100, 100) : 0} size={60} strokeWidth={6} color="#D44800">
            <span className="text-xs font-bold">{pet.weight || '—'}</span>
          </Ring>
          <div>
            <p className="text-lg font-bold text-gray-900">{pet.weight ? `${pet.weight} kg` : 'Not set'}</p>
            <p className="text-[11px] text-gray-500">Current weight</p>
            {pet.weight_flagged && <p className="text-[10px] text-amber-600 font-medium">⚠ Weight seems unusual</p>}
          </div>
        </div>

        {/* Sparkline */}
        {weightHistory.length > 1 && (
          <div className="mb-3">
            <svg viewBox={`0 0 ${weightHistory.length * 50} 60`} className="w-full h-12">
              {weightHistory.map((w, i) => {
                const h = (w.weight / maxWeight) * 50;
                return (
                  <rect
                    key={i}
                    x={i * 50 + 10}
                    y={55 - h}
                    width={30}
                    height={h}
                    rx={4}
                    fill={i === weightHistory.length - 1 ? '#D44800' : '#FFD5C2'}
                  />
                );
              })}
            </svg>
          </div>
        )}

        {/* Log table */}
        <div className="space-y-1 mb-3">
          {weightHistory.slice().reverse().slice(0, 5).map((w, i) => (
            <div key={i} className="flex justify-between text-xs py-1">
              <span className="text-gray-500">{w.date}</span>
              <span className="font-medium text-gray-800">{w.weight} kg</span>
            </div>
          ))}
        </div>

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
