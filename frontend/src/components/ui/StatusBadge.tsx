'use client';

import { STATUS_CONFIG } from '@/lib/dashboard-utils';

interface StatusBadgeProps {
  status: string;
  label?: string;
}

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.missing;
  return (
    <span
      className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase whitespace-nowrap"
      style={{ color: config.color, backgroundColor: config.bg }}
    >
      {label || config.label}
    </span>
  );
}
