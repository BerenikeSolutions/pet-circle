'use client';

import { useState, useEffect } from 'react';
import BottomSheet from './BottomSheet';
import { isDateInputValid, parseDMY, formatDMY, formatApiDate } from '@/lib/dashboard-utils';

interface DateEditSheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  currentDate: string | null;
  recurrenceDays?: number | null;
  onSave: (dateStr: string) => Promise<void>;
}

export default function DateEditSheet({ open, onClose, title, subtitle, currentDate, recurrenceDays, onSave }: DateEditSheetProps) {
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setValue(currentDate ? formatApiDate(currentDate) : '');
      setError('');
    }
  }, [open, currentDate]);

  const nextDuePreview = (() => {
    if (!value || !isDateInputValid(value) || !recurrenceDays) return null;
    const d = parseDMY(value);
    if (!d) return null;
    d.setDate(d.getDate() + recurrenceDays);
    return formatDMY(d);
  })();

  const handleSave = async () => {
    if (!isDateInputValid(value)) {
      setError('Enter a valid date (DD/MM/YYYY, DD-MM-YYYY, 12 March 2024, or YYYY-MM-DD)');
      return;
    }
    setSaving(true);
    try {
      const d = parseDMY(value)!;
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      await onSave(iso);
      onClose();
    } catch {
      setError('Failed to save. Try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <BottomSheet open={open} onClose={onClose} title={title}>
      {subtitle && <p className="text-sm text-gray-500 mb-4">{subtitle}</p>}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-1 block">Last Done</label>
          <input
            type="text"
            value={value}
            onChange={(e) => { setValue(e.target.value); setError(''); }}
            placeholder="DD/MM/YYYY, DD-MM-YYYY, or 12 March 2024"
            className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
          />
          <p className="text-[10px] text-gray-400 mt-0.5">Accepts: DD/MM/YYYY, DD-MM-YYYY, 12 March 2024, YYYY-MM-DD</p>
          {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </div>
        {nextDuePreview && (
          <div className="bg-green-50 rounded-xl px-4 py-3">
            <span className="text-xs text-gray-500">Next Due: </span>
            <span className="text-sm font-semibold text-green-700">{nextDuePreview}</span>
          </div>
        )}
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </BottomSheet>
  );
}
