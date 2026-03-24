'use client';

import { useState, useCallback } from 'react';
import type { DashboardData, NudgeItem } from '@/lib/api';
import { dismissNudge } from '@/lib/api';
import { NUDGE_CATEGORY_ICONS, NUDGE_PRIORITY_COLORS } from '@/lib/dashboard-utils';

interface NudgesViewProps {
  data: DashboardData;
  nudges: NudgeItem[];
  token: string;
  onBack: () => void;
  onCartClick: (itemId?: string) => void;
  onRemindersClick: () => void;
  onNudgesChange: (nudges: NudgeItem[]) => void;
  nudgesLoading?: boolean;
  nudgesError?: boolean;
  onRetryNudges?: () => void;
  overdueCount?: number;
}

type FilterKey = 'all' | 'mandatory' | 'nutrition' | 'grooming';

export default function NudgesView({ data, nudges, token, onBack, onCartClick, onRemindersClick, onNudgesChange, nudgesLoading, nudgesError, onRetryNudges, overdueCount }: NudgesViewProps) {
  const [filter, setFilter] = useState<FilterKey>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  const mandatoryCount = nudges.filter(n => n.mandatory).length;
  const recommendedCount = nudges.length - mandatoryCount;

  const filtered = nudges.filter(n => {
    if (filter === 'mandatory') return n.mandatory;
    if (filter === 'nutrition') return n.category === 'nutrition';
    if (filter === 'grooming') return n.category === 'grooming';
    return true;
  });

  const filterCounts: Record<FilterKey, number> = {
    all: nudges.length,
    mandatory: mandatoryCount,
    nutrition: nudges.filter(n => n.category === 'nutrition').length,
    grooming: nudges.filter(n => n.category === 'grooming').length,
  };

  const filters: { key: FilterKey; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'mandatory', label: 'Must Do' },
    { key: 'nutrition', label: 'Nutrition' },
    { key: 'grooming', label: 'Grooming' },
  ];

  const handleDismiss = useCallback(async (nudgeId: string) => {
    setDismissingId(nudgeId);
    try {
      await dismissNudge(token, nudgeId);
      onNudgesChange(nudges.filter(n => n.id !== nudgeId));
      setExpandedId(null);
    } catch {
      // ignore
    } finally {
      setDismissingId(null);
    }
  }, [token, nudges, onNudgesChange]);

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      {/* Header */}
      <div style={{ background: 'var(--brand-gradient)' }} className="px-5 pt-8 pb-5">
        <div className="max-w-[430px] mx-auto">
          <button onClick={onBack} className="text-white/80 text-sm mb-3 flex items-center gap-1">
            <span>←</span> Back
          </button>
          <h1 className="font-display text-xl font-bold text-white">{data.pet.name}&apos;s Action Plan</h1>
          <p className="text-white/70 text-xs mt-1">
            {mandatoryCount} mandatory · {recommendedCount} recommended
          </p>
        </div>
      </div>

      <div className="max-w-[430px] mx-auto p-4 space-y-3">
        {/* WhatsApp Reminders Banner */}
        <button
          onClick={onRemindersClick}
          className="w-full flex items-center gap-3 rounded-xl p-3 text-left"
          style={{ backgroundColor: '#F0FFF4', border: '1px solid #34C75930' }}
        >
          <span className="w-9 h-9 rounded-full flex items-center justify-center text-lg" style={{ backgroundColor: '#34C759' }}>
            💬
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-green-800">WhatsApp Reminders Active</p>
            <p className="text-[11px] text-green-600">Tap to view your scheduled reminders →</p>
          </div>
        </button>

        {/* Filter Chips */}
        <div className="flex gap-2 overflow-x-auto pb-1">
          {filters.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className="shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors"
              style={filter === f.key
                ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                : { borderColor: '#E5E5EA', color: '#666', backgroundColor: 'white' }
              }
            >
              {f.label} ({filterCounts[f.key]})
            </button>
          ))}
        </div>

        {/* Nudge Cards */}
        {filtered.length > 0 ? (
          <div className="space-y-2">
            {filtered.map(nudge => {
              const priorityStyle = NUDGE_PRIORITY_COLORS[nudge.priority] || NUDGE_PRIORITY_COLORS.medium;
              const icon = nudge.icon || NUDGE_CATEGORY_ICONS[nudge.category] || '📌';
              const isExpanded = expandedId === nudge.id;

              return (
                <div
                  key={nudge.id}
                  className="bg-white rounded-xl overflow-hidden"
                  style={{
                    border: `1.5px solid ${priorityStyle.color}30`,
                    boxShadow: `0 2px 8px ${priorityStyle.color}15`,
                  }}
                >
                  {/* Card Header — tap to expand */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : nudge.id)}
                    className="w-full p-3 text-left"
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="w-11 h-11 rounded-full flex items-center justify-center shrink-0 text-lg"
                        style={{ backgroundColor: priorityStyle.bg }}
                      >
                        {icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
                          <span className="text-sm font-semibold text-gray-900 truncate">{nudge.title}</span>
                          <span
                            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                            style={{ color: priorityStyle.color, backgroundColor: priorityStyle.bg }}
                          >
                            {priorityStyle.label}
                          </span>
                          {nudge.mandatory && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 bg-red-50 text-red-500">
                              MANDATORY
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-gray-500 leading-snug">{nudge.message}</p>
                      </div>
                      <span className="text-gray-300 shrink-0 mt-1">{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </button>

                  {/* Expanded Action Area */}
                  {isExpanded && (
                    <div
                      className="px-4 py-3 flex items-center justify-between"
                      style={{ backgroundColor: priorityStyle.bg }}
                    >
                      <div className="flex gap-2">
                        {nudge.orderable && (
                          <button
                            onClick={() => onCartClick(nudge.cart_item_id || undefined)}
                            className="text-xs font-semibold text-white px-4 py-2 rounded-full"
                            style={{ backgroundColor: '#D44800' }}
                          >
                            {nudge.order_type === 'book' ? 'Book Now' : 'Order Now'}
                            {nudge.price ? ` · ${nudge.price}` : ''}
                          </button>
                        )}
                      </div>
                      {!nudge.mandatory && (
                        <button
                          onClick={() => handleDismiss(nudge.id)}
                          disabled={dismissingId === nudge.id}
                          className="text-xs font-medium text-gray-500 hover:text-gray-700 px-3 py-2"
                        >
                          {dismissingId === nudge.id ? 'Dismissing...' : 'Dismiss'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          /* Empty / Loading / Error State */
          nudgesLoading ? (
            <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
              <div
                className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
                style={{ borderColor: '#FFD5C2', borderTopColor: '#D44800' }}
              />
              <p className="text-sm text-gray-500">Loading actions...</p>
            </div>
          ) : nudgesError ? (
            <div className="bg-white rounded-2xl border border-red-100 p-8 text-center">
              <p className="text-2xl mb-2">⚠️</p>
              <p className="text-sm text-red-600 mb-3">Could not load actions right now.</p>
              <button
                onClick={onRetryNudges}
                className="rounded-xl px-4 py-2 text-sm font-medium text-white"
                style={{ background: 'var(--brand-gradient)' }}
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
              <p className="text-4xl mb-3">🎉</p>
              <h3 className="font-display text-lg font-bold text-gray-900 mb-1">All done!</h3>
              <p className="text-sm text-gray-500">{data.pet.name}&apos;s care is up to date here.</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}
