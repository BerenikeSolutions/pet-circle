'use client';

import { useState } from 'react';
import type { DashboardData } from '@/lib/api';

interface RemindersViewProps {
  data: DashboardData;
  onBack: () => void;
}

const FREQ_OPTIONS = [
  { label: 'Weekly', days: 7 },
  { label: 'Every 2 weeks', days: 14 },
  { label: 'Monthly', days: 30 },
  { label: 'Every 3 months', days: 90 },
  { label: 'Every 6 months', days: 180 },
  { label: 'Annual', days: 365 },
  { label: 'One-time', days: null },
];

// Convert date to ISO string (YYYY-MM-DD)
function toISO(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '';
  return date.toISOString().split('T')[0];
}

// Compute next due date based on last done and frequency
function computeNextDue(lastDoneISO: string, freqLabel: string): string {
  const opt = FREQ_OPTIONS.find(f => f.label === freqLabel);
  if (!opt || !opt.days || !lastDoneISO) return '—';
  const d = new Date(lastDoneISO);
  d.setDate(d.getDate() + opt.days);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

// Get color class for status
const dotClass: Record<string, { bg: string; border: string }> = {
  red: { bg: '#FF3B30', border: '#FF3B30' },
  orange: { bg: '#FF9500', border: '#FF9500' },
  green: { bg: '#34C759', border: '#34C759' },
};

// Map reminder status to dot color
function getStatusDot(status: string | undefined): { bg: string; border: string } {
  if (!status) return dotClass.orange;
  if (status.toLowerCase() === 'red') return dotClass.red;
  if (status.toLowerCase() === 'overdue') return dotClass.red;
  if (status.toLowerCase() === 'upcoming') return dotClass.orange;
  if (status.toLowerCase() === 'done') return dotClass.green;
  return dotClass.orange;
}

interface ReminderItem {
  id: string;
  freq: string;
  lastDone?: string;
  nextDue?: string;
  status?: string;
  name: string;
  section: string;
}

interface EditVals {
  freq: string;
  lastISO: string;
}

export default function RemindersView({ data, onBack }: RemindersViewProps) {
  const pet = data.pet || { carePlan: [] };
  const carePlanV2 = data.care_plan_v2;

  // Flatten care plan sections into single array
  const flattenCarePlan = () => {
    if (!carePlanV2) return [];
    const allSections = [
      ...(carePlanV2.continue || []),
      ...(carePlanV2.attend || []),
      ...(carePlanV2.add || []),
    ];
    return allSections;
  };
  // Extract and filter reminder items from care plan
  const [items, setItems] = useState<ReminderItem[]>(() => {
    const carePlanSections = flattenCarePlan();
    return carePlanSections.flatMap(
      (s: any) => (s.items || [])
        .filter((i: any) => i.freq?.toLowerCase() !== 'daily')
        .map((i: any) => ({ ...i, section: s.section }))
    );
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editVals, setEditVals] = useState<EditVals>({
    freq: '',
    lastISO: '',
  });
  const [confirmDel, setConfirmDel] = useState<string | null>(null);

  // Get unique sections
  const sections = Array.from(new Set(items.map((i: ReminderItem) => i.section)));

  // Start editing an item
  const startEdit = (item: ReminderItem) => {
    setEditingId(item.id);
    setEditVals({
      freq: item.freq,
      lastISO: toISO(item.lastDone || null),
    });
  };

  // Save edit
  const saveEdit = () => {
    const nextDue = computeNextDue(editVals.lastISO, editVals.freq);
    const lastDisplay = editVals.lastISO
      ? new Date(editVals.lastISO).toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
        })
      : '—';
    setItems((prev: ReminderItem[]) =>
      prev.map((i: ReminderItem) =>
        i.id === editingId
          ? { ...i, freq: editVals.freq, lastDone: lastDisplay, nextDue }
          : i
      )
    );
    setEditingId(null);
  };

  // Delete item
  const deleteItem = (id: string) => {
    setItems((prev: ReminderItem[]) => prev.filter((i: ReminderItem) => i.id !== id));
    setConfirmDel(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg, #f5f5f5)',
        paddingBottom: 80,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border, #e0e0e0)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <button
          onClick={onBack}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 20,
            cursor: 'pointer',
          }}
        >
          ←
        </button>
        <div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: 'var(--t1, #000)',
            }}
          >
            Care Reminders
          </div>
        </div>
      </div>

      {/* Empty state */}
      {items.length === 0 && (
        <div
          className="card"
          style={{
            textAlign: 'center',
            padding: '32px 0',
            color: 'var(--t3, #999)',
            fontSize: 14,
            margin: '16px',
          }}
        >
          No reminders set
        </div>
      )}

      {/* Grouped sections */}
      {sections
        .filter((sec: string) => items.some((i: ReminderItem) => i.section === sec))
        .map((sec: string) => {
          const secItems = items.filter((i: ReminderItem) => i.section === sec);
          return (
            <div key={sec} className="card" style={{ margin: '12px' }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--t2, #666)',
                  textTransform: 'uppercase',
                  marginBottom: 12,
                  paddingBottom: 8,
                  borderBottom: '1px solid var(--border, #e0e0e0)',
                }}
              >
                {sec}
              </div>

              {secItems.map((item: ReminderItem) => {
                const statusDot = getStatusDot(item.status);
                return (
                  <div
                    key={item.id}
                    className="rem-row"
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'stretch',
                      gap: 0,
                      paddingBottom: 12,
                      marginBottom: 12,
                      borderBottom: '1px solid var(--border, #e0e0e0)',
                    }}
                  >
                    {/* Main row */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                      {/* Status dot */}
                      <div
                        style={{
                          width: 12,
                          height: 12,
                          borderRadius: '50%',
                          background: statusDot.bg,
                          marginTop: 6,
                          flexShrink: 0,
                        }}
                      />

                      {/* Item info */}
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: 'var(--t1, #000)',
                            lineHeight: 1.3,
                          }}
                        >
                          {item.name}
                        </div>

                        {editingId !== item.id && (
                          <div
                            style={{
                              display: 'flex',
                              gap: 12,
                              marginTop: 4,
                              fontSize: 11,
                              color: 'var(--t3, #999)',
                            }}
                          >
                            <span>
                              Freq:{' '}
                              <strong style={{ color: 'var(--t2, #666)' }}>
                                {item.freq}
                              </strong>
                            </span>
                            <span>
                              Last:{' '}
                              <strong style={{ color: 'var(--t2, #666)' }}>
                                {item.lastDone || '—'}
                              </strong>
                            </span>
                            <span>
                              Next:{' '}
                              <strong
                                style={{
                                  color:
                                    item.status === 'red'
                                      ? 'var(--red, #FF3B30)'
                                      : 'var(--t2, #666)',
                                }}
                              >
                                {item.nextDue || '—'}
                              </strong>
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                        {editingId === item.id ? (
                          <button
                            onClick={saveEdit}
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: '#fff',
                              background: '#34C759',
                              border: 'none',
                              borderRadius: 8,
                              padding: '3px 8px',
                              cursor: 'pointer',
                              fontFamily: 'inherit',
                            }}
                          >
                            Save
                          </button>
                        ) : (
                          <button
                            onClick={() => startEdit(item)}
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: '#007AFF',
                              background: 'var(--tr, transparent)',
                              border: 'none',
                              borderRadius: 8,
                              padding: '3px 8px',
                              cursor: 'pointer',
                              fontFamily: 'inherit',
                            }}
                          >
                            Edit
                          </button>
                        )}

                        {confirmDel !== item.id && editingId !== item.id && (
                          <button
                            onClick={() => setConfirmDel(item.id)}
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: '#c0392b',
                              background: 'var(--tr, transparent)',
                              border: 'none',
                              borderRadius: 8,
                              padding: '3px 8px',
                              cursor: 'pointer',
                              fontFamily: 'inherit',
                            }}
                          >
                            🗑
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Delete confirmation */}
                    {confirmDel === item.id && (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          marginTop: 8,
                          background: 'var(--tr, rgba(0,0,0,0.05))',
                          borderRadius: 8,
                          padding: '8px 10px',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 12,
                            color: '#c0392b',
                            flex: 1,
                          }}
                        >
                          Remove this reminder?
                        </span>
                        <button
                          onClick={() => deleteItem(item.id)}
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            background: '#c0392b',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 7,
                            padding: '4px 10px',
                            cursor: 'pointer',
                            fontFamily: 'inherit',
                          }}
                        >
                          Remove
                        </button>
                        <button
                          onClick={() => setConfirmDel(null)}
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            background: 'var(--white, #fff)',
                            color: 'var(--t2, #666)',
                            border: '1px solid var(--border, #e0e0e0)',
                            borderRadius: 7,
                            padding: '4px 10px',
                            cursor: 'pointer',
                            fontFamily: 'inherit',
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    )}

                    {/* Edit form */}
                    {editingId === item.id && (
                      <div
                        style={{
                          marginTop: 10,
                          paddingLeft: 18,
                        }}
                      >
                        {/* Frequency select */}
                        <div style={{ marginBottom: 8 }}>
                          <div
                            style={{
                              fontSize: 10,
                              color: 'var(--t3, #999)',
                              marginBottom: 3,
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              letterSpacing: '0.5px',
                            }}
                          >
                            Frequency
                          </div>
                          <select
                            value={editVals.freq}
                            onChange={e =>
                              setEditVals(v => ({ ...v, freq: e.target.value }))
                            }
                            style={{
                              width: '100%',
                              fontSize: 13,
                              border: '1.5px solid #FF9500',
                              borderRadius: 6,
                              padding: '5px 8px',
                              fontFamily: 'inherit',
                              background: 'var(--white, #fff)',
                              outline: 'none',
                              color: 'var(--t1, #000)',
                            }}
                          >
                            {FREQ_OPTIONS.map(f => (
                              <option key={f.label} value={f.label}>
                                {f.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Date input */}
                        <div style={{ marginBottom: 8 }}>
                          <div
                            style={{
                              fontSize: 10,
                              color: 'var(--t3, #999)',
                              marginBottom: 3,
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              letterSpacing: '0.5px',
                            }}
                          >
                            Last Done
                          </div>
                          <input
                            type="date"
                            value={editVals.lastISO}
                            onChange={e =>
                              setEditVals(v => ({
                                ...v,
                                lastISO: e.target.value,
                              }))
                            }
                            style={{
                              width: '100%',
                              fontSize: 13,
                              border: '1px solid var(--border, #e0e0e0)',
                              borderRadius: 6,
                              padding: '5px 8px',
                              fontFamily: 'inherit',
                              background: 'var(--white, #fff)',
                              outline: 'none',
                              color: 'var(--t1, #000)',
                            }}
                          />
                        </div>

                        {/* Auto-computed next due */}
                        <div
                          style={{
                            background: 'var(--ta, rgba(255, 149, 0, 0.1))',
                            borderRadius: 8,
                            padding: '7px 10px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <span
                            style={{
                              fontSize: 11,
                              color: 'var(--t3, #999)',
                              fontWeight: 600,
                            }}
                          >
                            Next due (auto)
                          </span>
                          <span
                            style={{
                              fontSize: 13,
                              fontWeight: 700,
                              color: '#b85c00',
                            }}
                          >
                            {computeNextDue(editVals.lastISO, editVals.freq)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}

      {/* Home floater */}
      <button
        onClick={onBack}
        style={{
          position: 'fixed',
          bottom: 28,
          right: 16,
          width: 48,
          height: 48,
          borderRadius: '50%',
          background: '#000',
          color: '#fff',
          fontSize: 24,
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        🏠
      </button>
    </div>
  );
}
