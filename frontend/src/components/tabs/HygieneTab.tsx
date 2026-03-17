'use client';

import { useState, useEffect } from 'react';
import type { DashboardData } from '@/lib/api';
import { updatePreventiveDate } from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import Toggle from '@/components/ui/Toggle';
import DateEditSheet from '@/components/ui/DateEditSheet';
import FreqModal from '@/components/ui/FreqModal';
import {
  filterByCircle, getStatusForRecord, formatApiDate, freqLabel,
  MOCK_DAILY_HYGIENE, MOCK_PERIODIC_HYGIENE, STATUS_CONFIG,
} from '@/lib/dashboard-utils';

interface HygieneTabProps {
  data: DashboardData;
  token: string;
  onUpdated: () => void;
  onCartClick: (itemId?: string) => void;
}

interface HygieneSettings {
  reminders: Record<string, boolean>;
  frequencies: Record<string, { freq: number; unit: string }>;
}

export default function HygieneTab({ data, token, onUpdated, onCartClick }: HygieneTabProps) {
  const [settings, setSettings] = useState<HygieneSettings>({ reminders: {}, frequencies: {} });
  const [freqEditing, setFreqEditing] = useState<string | null>(null);
  const [dateEditing, setDateEditing] = useState<string | null>(null);

  const storageKey = `petcircle_hygiene_${token}`;

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) setSettings(JSON.parse(saved));
  }, [storageKey]);

  const saveSettings = (s: HygieneSettings) => {
    setSettings(s);
    localStorage.setItem(storageKey, JSON.stringify(s));
  };

  const hygieneRecords = filterByCircle(data.preventive_records || [], 'hygiene');
  const breed = data.pet.breed || 'your breed';

  const dailyItems = hygieneRecords.length > 0
    ? hygieneRecords.filter(r => ['brush', 'teeth', 'ear', 'eye', 'wipe', 'clean'].some(k => r.item_name.toLowerCase().includes(k)))
    : MOCK_DAILY_HYGIENE;

  const periodicItems = hygieneRecords.length > 0
    ? hygieneRecords.filter(r => ['bath', 'nail', 'groom', 'anal', 'trim'].some(k => r.item_name.toLowerCase().includes(k)))
    : MOCK_PERIODIC_HYGIENE;

  const handleDateSave = async (itemName: string, dateStr: string) => {
    await updatePreventiveDate(token, itemName, dateStr);
    onUpdated();
  };

  const getFreq = (id: string) => settings.frequencies[id] || { freq: 1, unit: 'day' };
  const getReminderOn = (id: string) => settings.reminders[id] !== false;

  return (
    <div className="space-y-4">
      {/* Breed Note */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
        <p className="text-xs text-amber-800">
          <span className="font-semibold">🐕 Note:</span> Frequencies are breed-adjusted for {breed}.
        </p>
      </div>

      {/* Frequent Activities */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm mb-3">🪮 Frequent Activities</h3>
        <div className="space-y-0">
          {(dailyItems as any[]).map((item: any) => {
            const id = item.id || item.item_name;
            const name = item.name || item.item_name;
            const status = item.status || getStatusForRecord(item);
            const lastDone = item.lastDone || formatApiDate(item.last_done_date);
            const f = getFreq(id);

            return (
              <div key={id} className="py-3 border-b border-gray-50 last:border-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg">{item.icon || '🧹'}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{name}</p>
                      <p className="text-[11px] text-gray-500">Last: {lastDone}</p>
                    </div>
                  </div>
                  <StatusBadge status={status} />
                </div>
                <div className="flex items-center justify-between mt-1 pl-8">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setFreqEditing(id)}
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
                    >
                      {freqLabel(f.freq, f.unit)}
                    </button>
                  </div>
                  <Toggle
                    checked={getReminderOn(id)}
                    onChange={(v) => saveSettings({ ...settings, reminders: { ...settings.reminders, [id]: v } })}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Periodic Grooming */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm mb-3">✂️ Periodic Grooming</h3>
        <div className="space-y-0">
          {(periodicItems as any[]).map((item: any) => {
            const id = item.id || item.item_name;
            const name = item.name || item.item_name;
            const status = item.status || getStatusForRecord(item);
            const lastDone = item.lastDone || formatApiDate(item.last_done_date);
            const f = getFreq(id);

            return (
              <div key={id} className="py-3 border-b border-gray-50 last:border-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg">{item.icon || '🛁'}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{name}</p>
                      <p className="text-[11px] text-gray-500">
                        Last: {lastDone}
                        {item.note && <span className="text-gray-400"> · {item.note}</span>}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={status} />
                    <button
                      onClick={() => setDateEditing(item.item_name || id)}
                      className="text-xs text-brand font-semibold"
                    >
                      Edit
                    </button>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-1 pl-8">
                  <button
                    onClick={() => setFreqEditing(id)}
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
                  >
                    {freqLabel(f.freq, f.unit)}
                  </button>
                  <Toggle
                    checked={getReminderOn(id)}
                    onChange={(v) => saveSettings({ ...settings, reminders: { ...settings.reminders, [id]: v } })}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <button
          onClick={() => onCartClick('c7')}
          className="w-full mt-3 py-2.5 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Book Now
        </button>
      </div>

      {/* FreqModal */}
      {freqEditing && (
        <FreqModal
          open={!!freqEditing}
          onClose={() => setFreqEditing(null)}
          currentFreq={getFreq(freqEditing).freq}
          currentUnit={getFreq(freqEditing).unit}
          onSave={(f, u) => {
            saveSettings({ ...settings, frequencies: { ...settings.frequencies, [freqEditing]: { freq: f, unit: u } } });
          }}
        />
      )}

      {/* DateEditSheet */}
      {dateEditing && (
        <DateEditSheet
          open={!!dateEditing}
          onClose={() => setDateEditing(null)}
          title={`Edit ${dateEditing}`}
          subtitle="When was this last done?"
          currentDate={hygieneRecords.find(r => r.item_name === dateEditing)?.last_done_date || null}
          recurrenceDays={hygieneRecords.find(r => r.item_name === dateEditing)?.recurrence_days || 30}
          onSave={(d) => handleDateSave(dateEditing, d)}
        />
      )}
    </div>
  );
}
