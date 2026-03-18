'use client';

import { useState } from 'react';
import type { DashboardData } from '@/lib/api';
import {
  MOCK_WA_REMINDERS,
  WA_REMINDER_COLORS, WA_REMINDER_BG, WA_REMINDER_LABELS,
  REMINDER_EXPLAINER,
} from '@/lib/dashboard-utils';

interface RemindersViewProps {
  data: DashboardData;
  onBack: () => void;
}

const TIMELINE_STEPS = [
  { label: '1 week before', status: 'upcoming', icon: '📬' },
  { label: 'Due date', status: 'due', icon: '📅' },
  { label: 'Overdue', status: 'overdue', icon: '🚨' },
  { label: 'Done', status: 'done', icon: '✅' },
];

export default function RemindersView({ data, onBack }: RemindersViewProps) {
  const petName = data.pet.name || 'Your Pet';
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const apiReminders = data.reminders || [];
  const reminders = apiReminders.length > 0
    ? apiReminders.map((r: any, i: number) => ({
        id: r.id || `api-${i}`,
        type: r.type || 'general',
        daysOut: r.daysOut ?? 0,
        status: r.status || 'upcoming',
        icon: r.icon || '🔔',
        title: r.title || r.item_name || 'Reminder',
        body: r.body || '',
        actions: r.actions || [],
      }))
    : MOCK_WA_REMINDERS;

  const filtered = filter === 'all'
    ? reminders
    : reminders.filter((r: any) => r.status === filter);

  const counts = {
    all: reminders.length,
    upcoming: reminders.filter((r: any) => r.status === 'upcoming').length,
    due: reminders.filter((r: any) => r.status === 'due').length,
    overdue: reminders.filter((r: any) => r.status === 'overdue').length,
  };

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      {/* Header */}
      <div className="sticky top-0 z-30" style={{ backgroundColor: '#075E54' }}>
        <div className="max-w-[430px] mx-auto flex items-center gap-3 px-4 py-3">
          <button
            onClick={onBack}
            className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-white/10 transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12.5 15L7.5 10L12.5 5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <div>
            <h1 className="text-white font-semibold text-base">WhatsApp Reminders</h1>
            <p className="text-white/70 text-xs">{petName}&apos;s scheduled health reminders</p>
          </div>
        </div>
      </div>

      <div className="max-w-[430px] mx-auto p-4 space-y-4">
        {/* Timeline Legend */}
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-gray-700 mb-3">Reminder Lifecycle</p>
          <div className="relative flex justify-between items-start">
            {/* Connecting line */}
            <div className="absolute top-4 left-[10%] right-[10%] h-0.5 bg-gray-200" />
            {TIMELINE_STEPS.map((step, i) => {
              const color = step.status === 'done' ? '#34C759' : (WA_REMINDER_COLORS[step.status] || '#8E8E93');
              return (
                <div key={i} className="flex flex-col items-center gap-1.5 relative z-10" style={{ width: '25%' }}>
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                    style={{ backgroundColor: color + '18', border: `2px solid ${color}` }}
                  >
                    {step.icon}
                  </div>
                  <span className="text-[10px] font-semibold text-center leading-tight" style={{ color }}>
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Filter Chips */}
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {(['all', 'upcoming', 'due', 'overdue'] as const).map((f) => {
            const active = filter === f;
            const chipColor = f === 'all' ? '#075E54' : WA_REMINDER_COLORS[f] || '#8E8E93';
            const count = counts[f];
            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors"
                style={{
                  backgroundColor: active ? chipColor : 'white',
                  color: active ? 'white' : chipColor,
                  border: `1.5px solid ${chipColor}`,
                }}
              >
                {f === 'all' ? 'All' : WA_REMINDER_LABELS[f]}
                <span
                  className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold"
                  style={{
                    backgroundColor: active ? 'rgba(255,255,255,0.25)' : chipColor + '15',
                    color: active ? 'white' : chipColor,
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Reminder Cards */}
        {filtered.length === 0 ? (
          <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
            <p className="text-3xl mb-2">🎉</p>
            <p className="text-sm font-semibold text-gray-700">No {filter} reminders</p>
            <p className="text-xs text-gray-500 mt-1">
              {filter === 'overdue' ? `${petName} is all caught up!` : 'Nothing scheduled in this category.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((rem: any) => {
              const status = rem.status || 'upcoming';
              const color = WA_REMINDER_COLORS[status] || '#FF9500';
              const bg = WA_REMINDER_BG[status] || '#FFF6ED';
              const label = WA_REMINDER_LABELS[status] || 'UPCOMING';
              const isExpanded = expandedId === rem.id;

              return (
                <div
                  key={rem.id}
                  className="rounded-2xl overflow-hidden shadow-sm transition-all"
                  style={{ border: `1.5px solid ${color}30` }}
                >
                  {/* Card Header */}
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 text-left"
                    style={{ backgroundColor: bg }}
                    onClick={() => setExpandedId(isExpanded ? null : rem.id)}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-lg shrink-0">{rem.icon || '🔔'}</span>
                      <span className="text-xs font-semibold truncate" style={{ color }}>
                        {rem.title}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className="text-[9px] font-bold px-2 py-0.5 rounded-full"
                        style={{ color, backgroundColor: color + '20' }}
                      >
                        {label}
                      </span>
                      <svg
                        width="14" height="14" viewBox="0 0 14 14" fill="none"
                        className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      >
                        <path d="M3 5L7 9L11 5" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  </button>

                  {/* Expanded Content */}
                  {isExpanded && rem.body && (
                    <div className="px-4 py-3 bg-white border-t" style={{ borderColor: color + '15' }}>
                      <p className="text-[12px] text-gray-600 leading-relaxed">{rem.body}</p>
                      {rem.actions && rem.actions.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {rem.actions.map((a: any, j: number) => (
                            <button
                              key={j}
                              className="text-[11px] font-semibold px-4 py-2 rounded-full text-white shadow-sm"
                              style={{ backgroundColor: a.color }}
                            >
                              {a.label}
                            </button>
                          ))}
                        </div>
                      )}
                      {/* Timing info */}
                      <div className="mt-3 pt-2 border-t border-gray-100 flex items-center gap-1.5">
                        <span className="text-[10px] text-gray-400">
                          {rem.daysOut > 0 ? `${rem.daysOut} day${rem.daysOut !== 1 ? 's' : ''} from now` :
                           rem.daysOut === 0 ? 'Due today' :
                           `${Math.abs(rem.daysOut)} day${Math.abs(rem.daysOut) !== 1 ? 's' : ''} overdue`}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* How It Works Card */}
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 flex items-center gap-2" style={{ backgroundColor: '#075E54' }}>
            <span className="text-sm">💬</span>
            <span className="text-white text-xs font-semibold">How WhatsApp Reminders Work</span>
          </div>
          <div className="p-4 space-y-3">
            {REMINDER_EXPLAINER.map(([step, desc], i) => (
              <div key={i} className="flex gap-3">
                <div className="shrink-0 mt-0.5">
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                    style={{ backgroundColor: '#075E54' }}
                  >
                    {i + 1}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-800">{step}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Engine Rules */}
        <div className="bg-gray-50 rounded-2xl p-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">Engine Rules</p>
          <div className="space-y-1.5">
            {[
              ['Daily cron', '8:00 AM IST via GitHub Actions'],
              ['Deduplication', 'Enforced at DB level'],
              ['Rate limit', 'Max 20 msgs/min per number'],
              ['Retry', 'Single retry on API failure'],
              ['Condition meds', 'Separate refill series per medication'],
            ].map(([label, val], i) => (
              <div key={i} className="flex justify-between text-[11px]">
                <span className="text-gray-500">{label}</span>
                <span className="text-gray-700 font-medium">{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom padding */}
        <div className="h-8" />
      </div>
    </div>
  );
}
