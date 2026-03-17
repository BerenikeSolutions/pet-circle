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
  onDateSave: (dateStr: string) => Promise<void>;
  onOrderClick?: (itemId?: string) => void;
}

export default function CareCard({ icon, title, product, lastDone, nextDue, status, recurrenceDays, onDateSave, onOrderClick }: CareCardProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [freq, setFreq] = useState(3);
  const [unit, setUnit] = useState('month');

  return (
    <>
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">{icon}</span>
            <div>
              <h4 className="font-semibold text-sm text-gray-900">{title}</h4>
              {product && <p className="text-xs text-gray-500">{product}</p>}
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

        <div className="border-t border-gray-100 pt-2">
          <ReminderBar
            enabled={reminderEnabled}
            onToggle={setReminderEnabled}
            freq={freq}
            unit={unit}
            onFreqChange={(f, u) => { setFreq(f); setUnit(u); }}
          />
        </div>

        {(status === 'overdue' || status === 'missing') && onOrderClick && (
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
