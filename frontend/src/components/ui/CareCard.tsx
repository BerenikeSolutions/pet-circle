'use client';

import { useState } from 'react';
import StatusBadge from './StatusBadge';
import ReminderBar from './ReminderBar';
import DateEditSheet from './DateEditSheet';
import { formatApiDate } from '@/lib/dashboard-utils';

interface CareCardProps {
  icon: string;
  title: string;
  product?: string;
  lastDone: string | null;
  nextDue: string | null;
  status: string;
  recurrenceDays?: number | null;
  medicineDependant?: boolean;
  medicineName?: string | null;
  onDateSave: (dateStr: string) => Promise<void>;
  onOrderClick?: (itemId?: string) => void;
  onFreqChange?: (freq: number, unit: string) => void;
  onMedicineSave?: (name: string) => Promise<void>;
}

export default function CareCard({
  icon, title, product, lastDone, nextDue, status, recurrenceDays,
  medicineDependant, medicineName,
  onDateSave, onOrderClick, onFreqChange, onMedicineSave,
}: CareCardProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [medInput, setMedInput] = useState(medicineName || '');
  const [medSaving, setMedSaving] = useState(false);
  const [medMsg, setMedMsg] = useState('');

  // Derive initial freq/unit from recurrenceDays
  const initFreq = recurrenceDays ? (
    recurrenceDays >= 365 && recurrenceDays % 365 === 0 ? { f: recurrenceDays / 365, u: 'year' } :
    recurrenceDays >= 30 && recurrenceDays % 30 === 0 ? { f: recurrenceDays / 30, u: 'month' } :
    recurrenceDays >= 7 && recurrenceDays % 7 === 0 ? { f: recurrenceDays / 7, u: 'week' } :
    { f: recurrenceDays, u: 'day' }
  ) : { f: 3, u: 'month' };
  const [freq, setFreq] = useState(initFreq.f);
  const [unit, setUnit] = useState(initFreq.u);

  const handleMedicineSave = async () => {
    const name = medInput.trim();
    if (!name) { setMedMsg('Enter a medicine name'); return; }
    if (!onMedicineSave) return;
    setMedSaving(true);
    setMedMsg('');
    try {
      await onMedicineSave(name);
      setMedMsg('Saved! Next due date updated.');
    } catch {
      setMedMsg('Failed to save');
    } finally {
      setMedSaving(false);
    }
  };

  const displayProduct = medicineName || product;

  return (
    <>
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">{icon}</span>
            <div>
              <h4 className="font-semibold text-sm text-gray-900">{title}</h4>
              {displayProduct && <p className="text-xs text-gray-500">{displayProduct}</p>}
            </div>
          </div>
          <StatusBadge status={status} />
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="space-y-1">
            <div className="text-gray-500">Last done: <span className="text-gray-900 font-medium">{formatApiDate(lastDone)}</span></div>
            <div className="text-gray-500">Next due: <span className="text-gray-900 font-medium">{formatApiDate(nextDue)}</span></div>
          </div>
          <button
            onClick={() => setEditOpen(true)}
            className="text-brand text-xs font-semibold hover:underline"
          >
            Edit
          </button>
        </div>

        {/* Medicine name input for medicine-dependent items */}
        {medicineDependant && (
          <div className="border-t border-gray-100 pt-2 space-y-2">
            <label className="text-[11px] text-gray-500 font-medium">Medicine / Product Name</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={medInput}
                onChange={(e) => setMedInput(e.target.value)}
                placeholder="e.g. NexGard, Drontal Plus"
                className="flex-1 px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
              <button
                onClick={handleMedicineSave}
                disabled={medSaving}
                className="px-3 py-2 rounded-xl text-white text-xs font-semibold disabled:opacity-50"
                style={{ background: 'var(--brand-gradient)' }}
              >
                {medSaving ? '...' : 'Save'}
              </button>
            </div>
            {medMsg && (
              <p className={`text-[11px] ${medMsg.includes('Saved') ? 'text-green-600' : 'text-red-500'}`}>
                {medMsg}
              </p>
            )}
          </div>
        )}

        <div className="border-t border-gray-100 pt-2">
          <ReminderBar
            enabled={reminderEnabled}
            onToggle={setReminderEnabled}
            freq={freq}
            unit={unit}
            onFreqChange={(f, u) => { setFreq(f); setUnit(u); onFreqChange?.(f, u); }}
          />
        </div>

        {onOrderClick && (
          <button
            onClick={() => onOrderClick?.()}
            className="w-full py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Order Now
          </button>
        )}
      </div>

      <DateEditSheet
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title={`Edit ${title}`}
        subtitle="Enter the last done date"
        currentDate={lastDone}
        recurrenceDays={recurrenceDays}
        onSave={onDateSave}
      />
    </>
  );
}
