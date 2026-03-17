'use client';

import { useState } from 'react';
import Toggle from './Toggle';
import FreqModal from './FreqModal';
import { freqLabel } from '@/lib/dashboard-utils';

interface ReminderBarProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  freq: number;
  unit: string;
  onFreqChange: (freq: number, unit: string) => void;
}

export default function ReminderBar({ enabled, onToggle, freq, unit, onFreqChange }: ReminderBarProps) {
  const [showFreq, setShowFreq] = useState(false);

  return (
    <>
      <div className="flex items-center justify-between py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Reminder</span>
          <button
            onClick={() => setShowFreq(true)}
            className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200"
          >
            {freqLabel(freq, unit)}
          </button>
        </div>
        <Toggle checked={enabled} onChange={onToggle} />
      </div>
      <FreqModal
        open={showFreq}
        onClose={() => setShowFreq(false)}
        currentFreq={freq}
        currentUnit={unit}
        onSave={onFreqChange}
      />
    </>
  );
}
