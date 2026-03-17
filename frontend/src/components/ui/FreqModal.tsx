'use client';

import { useState, useEffect } from 'react';
import BottomSheet from './BottomSheet';
import { FREQ_MODAL_UNITS, FREQ_MODAL_OPTIONS, freqLabel } from '@/lib/dashboard-utils';

interface FreqModalProps {
  open: boolean;
  onClose: () => void;
  currentFreq: number;
  currentUnit: string;
  onSave: (freq: number, unit: string) => void;
}

export default function FreqModal({ open, onClose, currentFreq, currentUnit, onSave }: FreqModalProps) {
  const [freq, setFreq] = useState(currentFreq);
  const [unit, setUnit] = useState(currentUnit);

  useEffect(() => {
    if (open) { setFreq(currentFreq); setUnit(currentUnit); }
  }, [open, currentFreq, currentUnit]);

  const options = FREQ_MODAL_OPTIONS[unit] || [1];

  return (
    <BottomSheet open={open} onClose={onClose} title="Set Frequency">
      <div className="space-y-4">
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-2 block">Unit</label>
          <div className="flex gap-2">
            {FREQ_MODAL_UNITS.map(u => (
              <button
                key={u}
                onClick={() => { setUnit(u); setFreq(FREQ_MODAL_OPTIONS[u]?.[0] || 1); }}
                className="px-4 py-2 rounded-full text-sm font-semibold border transition-colors"
                style={u === unit
                  ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                  : { borderColor: '#E5E5EA', color: '#666' }
                }
              >
                {u.charAt(0).toUpperCase() + u.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold text-gray-500 mb-2 block">Every</label>
          <div className="flex gap-2">
            {options.map(n => (
              <button
                key={n}
                onClick={() => setFreq(n)}
                className="w-12 h-12 rounded-full text-sm font-bold border transition-colors"
                style={n === freq
                  ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                  : { borderColor: '#E5E5EA', color: '#666' }
                }
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="bg-gray-50 rounded-xl px-4 py-3">
          <span className="text-sm text-gray-700">{freqLabel(freq, unit)}</span>
        </div>
        <button
          onClick={() => { onSave(freq, unit); onClose(); }}
          className="w-full py-3 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Save
        </button>
      </div>
    </BottomSheet>
  );
}
