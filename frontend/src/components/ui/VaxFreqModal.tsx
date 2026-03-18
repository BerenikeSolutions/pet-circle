'use client';

import { useState, useEffect } from 'react';
import BottomSheet from './BottomSheet';
import { VAX_FREQ_OPTS, VAX_FREQ_LABELS } from '@/lib/dashboard-utils';

interface VaxFreqModalProps {
  open: boolean;
  onClose: () => void;
  currentMonths: number;
  onSave: (months: number) => void;
}

export default function VaxFreqModal({ open, onClose, currentMonths, onSave }: VaxFreqModalProps) {
  const [selected, setSelected] = useState(currentMonths);

  useEffect(() => {
    if (open) setSelected(currentMonths);
  }, [open, currentMonths]);

  return (
    <BottomSheet open={open} onClose={onClose} title="Vaccine Frequency">
      <div className="space-y-4">
        <p className="text-xs text-gray-500">Choose how often this vaccine should be repeated:</p>
        <div className="flex flex-wrap gap-2">
          {VAX_FREQ_OPTS.map(months => (
            <button
              key={months}
              onClick={() => setSelected(months)}
              className="px-[18px] py-[10px] rounded-full text-sm font-semibold border transition-colors"
              style={months === selected
                ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                : { borderColor: '#E5E5EA', color: '#666' }
              }
            >
              {VAX_FREQ_LABELS[months] || `Every ${months} months`}
            </button>
          ))}
        </div>
        <button
          onClick={() => { onSave(selected); onClose(); }}
          className="w-full py-3 rounded-xl text-white text-sm font-semibold"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Save
        </button>
      </div>
    </BottomSheet>
  );
}
