'use client';

import { useEffect } from 'react';

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export default function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center animate-fadeIn">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        className="relative w-full max-w-[430px] bg-white rounded-t-[20px] p-5 pb-8 animate-slideUp"
        style={{ maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />

        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            width: 32,
            height: 32,
            borderRadius: '50%',
            border: '1.5px solid #e0e0e0',
            background: '#f5f5f5',
            fontSize: 18,
            lineHeight: 1,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#555',
            fontWeight: 400,
          }}
        >
          &times;
        </button>

        {title && <h3 className="text-lg font-bold text-gray-900 mb-4">{title}</h3>}
        {children}
      </div>
    </div>
  );
}
