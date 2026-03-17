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
        {title && <h3 className="text-lg font-bold text-gray-900 mb-4">{title}</h3>}
        {children}
      </div>
    </div>
  );
}
