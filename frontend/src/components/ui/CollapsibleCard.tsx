'use client';

import { useState } from 'react';

interface CollapsibleCardProps {
  icon?: string;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  headerBg?: string;
  headerColor?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleCard({
  icon, title, subtitle, badge, headerBg, headerColor, defaultOpen = false, children,
}: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" style={{ marginBottom: 12 }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
        style={{ backgroundColor: headerBg, color: headerColor }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && <span className="text-lg shrink-0">{icon}</span>}
          <div className="min-w-0">
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--t3)" }} className="truncate">{title}</div>
            {subtitle && <div className="text-xs opacity-70 truncate">{subtitle}</div>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {badge}
          <svg
            className="w-4 h-4 transition-transform duration-200"
            style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {open && (
        <div className="border-t border-gray-100 animate-slideDown">
          {children}
        </div>
      )}
    </div>
  );
}
