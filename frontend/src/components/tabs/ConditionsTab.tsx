'use client';

import { useState, useEffect, useCallback } from 'react';
import type {
  DashboardData,
  ConditionItem,
  ConditionMedicationItem,
  ConditionMonitoringItem,
  TimelineEvent,
  ConditionRecommendation,
  LastVetVisit,
  VetQuestion,
} from '@/lib/api';
import {
  addCondition,
  deleteCondition,
  addConditionMedication,
  deleteConditionMedication,
  addConditionMonitoring,
  deleteConditionMonitoring,
  getConditionTimeline,
  getConditionRecommendations,
  getLastVetVisit,
  getHealthSummary,
  getVetQuestions,
  regenerateVetQuestions,
} from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import ReminderBar from '@/components/ui/ReminderBar';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import { formatApiDate } from '@/lib/dashboard-utils';

interface ConditionsTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
}

function getRefillStatus(refillDueDate: string | null): string {
  if (!refillDueDate) return 'ok';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const due = new Date(refillDueDate);
  if (isNaN(due.getTime())) return 'ok';
  const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff <= 0) return 'urgent';
  if (diff <= 14) return 'upcoming';
  return 'ok';
}

function getMonitoringStatus(nextDueDate: string | null): 'overdue' | 'upcoming' | 'done' | 'missing' {
  if (!nextDueDate) return 'missing';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const due = new Date(nextDueDate);
  if (isNaN(due.getTime())) return 'missing';
  const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return 'overdue';
  if (diff <= 30) return 'upcoming';
  return 'done';
}

function getDateRelative(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const diff = Math.ceil((today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diff > 180) return '6+ months ago';
  if (diff > 30) return `${Math.floor(diff / 30)} months ago`;
  if (diff > 0) return `${diff} days ago`;
  return 'Today';
}

const PRIORITY_COLOR: Record<string, string> = { urgent: '#FF3B30', high: '#FF9500', medium: '#007AFF' };
const PRIORITY_BG: Record<string, string>    = { urgent: '#FFF0F0', high: '#FFF6ED', medium: '#F0F6FF' };
const PRIORITY_LABEL: Record<string, string> = { urgent: 'URGENT', high: 'RECOMMENDED', medium: 'SUGGESTED' };

/* ─────────────────────────────────────────────────────────────────
   Conditions Summary Card (ring removed — score shown in header)
───────────────────────────────────────────────────────────────── */
function HealthScoreCard({
  activeCount, summary, conditions,
}: {
  activeCount: number; summary: string; conditions: ConditionItem[];
}) {
  const hasConditions = conditions.length > 0;
  const cardBg = hasConditions ? '#FFF9F5' : '#F0FFF4';
  const cardBorder = hasConditions ? '#D4480033' : '#34C75933';

  return (
    <div style={{
      background: cardBg, borderRadius: 20, padding: 20,
      border: `1.5px solid ${cardBorder}`, boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
      marginBottom: 12,
    }}>
      <div style={{ marginBottom: conditions.length > 0 ? 14 : 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
            background: hasConditions ? '#FFF5F0' : '#E8FAF0',
            color: hasConditions ? '#D44800' : '#34C759',
          }}>
            {activeCount} OPEN {activeCount === 1 ? 'CONDITION' : 'CONDITIONS'}
          </span>
        </div>
        <p style={{ fontSize: 12, color: '#3C3C43', lineHeight: 1.5, margin: 0 }}>
          {summary || 'Loading conditions summary…'}
        </p>
      </div>

      {/* Status pills */}
      {conditions.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {conditions.map((c) => (
            <span key={c.id} style={{
              fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 20,
              background: c.condition_type === 'chronic' ? '#FFF5F0' : c.condition_type === 'episodic' ? '#FFF6ED' : '#E8FAF0',
              color: c.condition_type === 'chronic' ? '#D44800' : c.condition_type === 'episodic' ? '#FF9500' : '#34C759',
            }}>
              {c.icon || '🏥'} {c.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Med Row
───────────────────────────────────────────────────────────────── */
function MedRow({ med, onDelete }: { med: ConditionMedicationItem; onDelete: () => void }) {
  const [reminderOn, setReminderOn] = useState(false);
  const [rFreq, setRFreq] = useState(1);
  const [rUnit, setRUnit] = useState('day');
  const refillStatus = getRefillStatus(med.refill_due_date);

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, background: '#F0F6FF',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0,
        }}>💊</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: '#1C1C1E' }}>{med.name}</div>
              <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 1 }}>
                {[med.dose, med.frequency, med.route].filter(Boolean).join(' · ')}
              </div>
              {med.refill_due_date && (
                <div style={{ fontSize: 11, color: refillStatus === 'urgent' ? '#FF3B30' : '#FF9500', marginTop: 2 }}>
                  Refill due: {formatApiDate(med.refill_due_date)}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <StatusBadge
                status={med.status === 'active' ? (refillStatus === 'ok' ? 'done' : refillStatus) : 'resolved'}
                label={med.status === 'active' ? 'ACTIVE' : 'STOPPED'}
              />
              <button onClick={onDelete} style={{ color: '#C7C7CC', fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
            </div>
          </div>
        </div>
      </div>
      <div style={{ marginLeft: 46 }}>
        <ReminderBar
          enabled={reminderOn} onToggle={setReminderOn}
          freq={rFreq} unit={rUnit}
          onFreqChange={(f, u) => { setRFreq(f); setRUnit(u); }}
        />
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Monitor Row
───────────────────────────────────────────────────────────────── */
function MonitorRow({ mon, onDelete }: { mon: ConditionMonitoringItem; onDelete: () => void }) {
  const status = getMonitoringStatus(mon.next_due_date);
  const lastDone = getDateRelative(mon.last_done_date);

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 10 }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10, background: '#FFF6ED',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0,
      }}>🩺</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#1C1C1E' }}>{mon.name}</div>
            <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 1 }}>
              {mon.frequency || 'As needed'}
              {lastDone ? ` · Last: ${lastDone}` : ' · Never done'}
            </div>
            {mon.next_due_date && (
              <div style={{ fontSize: 11, color: status === 'overdue' ? '#FF3B30' : '#FF9500', marginTop: 2 }}>
                {status === 'overdue' ? 'Overdue: ' : 'Due: '}{formatApiDate(mon.next_due_date)}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <StatusBadge
              status={status}
              label={status === 'overdue' ? 'OVERDUE' : status === 'done' ? 'DONE' : 'DUE SOON'}
            />
            <button onClick={onDelete} style={{ color: '#C7C7CC', fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Condition Card
───────────────────────────────────────────────────────────────── */
function ConditionCard({
  condition, onDelete, onAddMed, onDeleteMed, onAddMon, onDeleteMon,
}: {
  condition: ConditionItem;
  onDelete: () => void;
  onAddMed: () => void;
  onDeleteMed: (id: string) => void;
  onAddMon: () => void;
  onDeleteMon: (id: string) => void;
}) {
  const hasOverdueMon = condition.monitoring?.some(m => getMonitoringStatus(m.next_due_date) === 'overdue');
  const hasNoMeds = condition.condition_type === 'chronic' && condition.medications.length === 0;
  const overdueMons = condition.monitoring?.filter(m => getMonitoringStatus(m.next_due_date) === 'overdue') || [];

  const badgeLabelMap: Record<string, string> = { chronic: 'MANAGED', episodic: 'EPISODIC', resolved: 'RESOLVED' };
  const statusMap: Record<string, string> = { chronic: 'managed', episodic: 'upcoming', resolved: 'done' };

  return (
    <div style={{ padding: '14px 16px 8px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12, background: '#F0F6FF',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0,
        }}>
          {condition.icon || '🏥'}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 15, color: '#1C1C1E' }}>{condition.name}</span>
            {condition.condition_type === 'episodic' && condition.episode_count && condition.episode_count > 1 && (
              <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 20, background: '#FFF6ED', color: '#FF9500' }}>
                {condition.episode_count} episodes
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: '#8E8E93' }}>
            {condition.diagnosed_at ? `Diagnosed ${formatApiDate(condition.diagnosed_at)}` : ''}
            {condition.managed_by ? ` · ${condition.managed_by}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <StatusBadge
            status={statusMap[condition.condition_type] || 'managed'}
            label={badgeLabelMap[condition.condition_type] || condition.condition_type.toUpperCase()}
          />
          <button onClick={onDelete} style={{ color: '#C7C7CC', fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }} title="Remove">✕</button>
        </div>
      </div>

      {/* Alert boxes */}
      {hasOverdueMon && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          background: '#FFFBEB', border: '1px solid #FCD34D', borderRadius: 10,
          padding: '8px 12px', marginBottom: 10, fontSize: 12, color: '#92400E',
        }}>
          <span>⚠️</span>
          <span>
            {overdueMons.length === 1
              ? `${overdueMons[0].name} monitoring is overdue. Schedule a check-up soon.`
              : `${overdueMons.length} monitoring items are overdue.`}
          </span>
        </div>
      )}
      {hasNoMeds && !hasOverdueMon && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 10,
          padding: '8px 12px', marginBottom: 10, fontSize: 12, color: '#1D4ED8',
        }}>
          <span>ℹ️</span>
          <span>No medications recorded for this chronic condition. Ask your vet if management is needed.</span>
        </div>
      )}

      {/* Medications */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        borderLeft: '3px solid #007AFF', paddingLeft: 8,
        marginBottom: 10,
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: '#007AFF', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Vet Prescribed · Medications
        </span>
      </div>
      {condition.medications.length > 0 ? (
        condition.medications.map((med) => (
          <MedRow key={med.id} med={med} onDelete={() => onDeleteMed(med.id)} />
        ))
      ) : (
        <div style={{ fontSize: 12, color: '#C7C7CC', marginBottom: 10, paddingLeft: 4 }}>No medications recorded</div>
      )}
      <AddRow label="Add Medication" onClick={onAddMed} />

      {/* Monitoring */}
      {condition.monitoring && condition.monitoring.length > 0 && (
        <>
          <div style={{ height: 1, background: '#F2F2F7', margin: '12px 0' }} />
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            borderLeft: '3px solid #FF9500', paddingLeft: 8,
            marginBottom: 10,
          }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#FF9500', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Vet Prescribed · Monitoring
            </span>
          </div>
          {condition.monitoring.map((mon) => (
            <MonitorRow key={mon.id} mon={mon} onDelete={() => onDeleteMon(mon.id)} />
          ))}
          {overdueMons.length > 0 && (
            <button style={{
              width: '100%', padding: '10px', background: '#FFF6ED',
              border: '1px solid #FF9500', borderRadius: 10,
              fontSize: 12, fontWeight: 600, color: '#FF9500', cursor: 'pointer', marginBottom: 4,
            }}>
              📅 Book Follow-up Tests
            </button>
          )}
        </>
      )}
      <AddRow label="Add Monitoring" onClick={onAddMon} />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Last Vet Visit Card
───────────────────────────────────────────────────────────────── */
function LastVetVisitCard({ vetVisit }: { vetVisit: LastVetVisit | null }) {
  if (!vetVisit) return null;
  return (
    <div style={{
      background: 'white', borderRadius: 16, padding: 16,
      border: '1.5px solid #E5E5EA', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
        Last Vet Visit
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, background: '#E8FAF0',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        }}>🏥</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#1C1C1E' }}>
            {vetVisit.clinic_name || 'Vet Clinic'}
          </div>
          <div style={{ fontSize: 12, color: '#8E8E93' }}>
            {vetVisit.last_visit_date ? formatApiDate(vetVisit.last_visit_date) : ''}
            {vetVisit.vet_name ? ` · ${vetVisit.vet_name}` : ''}
          </div>
          {vetVisit.notes && (
            <div style={{ fontSize: 11, color: '#3C3C43', marginTop: 4 }}>{vetVisit.notes}</div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Ask The Vet Section
───────────────────────────────────────────────────────────────── */
function AskTheVetSection({
  questions, loading, onRegenerate,
}: {
  questions: VetQuestion[];
  loading: boolean;
  onRegenerate: () => void;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  return (
    <div style={{
      background: 'white', borderRadius: 20, padding: 16,
      border: '1.5px solid #E5E5EA', boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: '#E8FAF0',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
          }}>🩺</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#1C1C1E' }}>Ask the Vet</div>
            <div style={{ fontSize: 11, color: '#8E8E93' }}>AI-generated questions for your next visit</div>
          </div>
        </div>
        <button
          onClick={onRegenerate}
          disabled={loading}
          style={{
            width: 30, height: 30, borderRadius: 8, background: '#F2F2F7',
            border: 'none', cursor: loading ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, opacity: loading ? 0.5 : 1,
          }}
          title="Regenerate questions"
        >
          {loading ? '⏳' : '🔄'}
        </button>
      </div>

      {loading && questions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0', color: '#8E8E93', fontSize: 12 }}>
          Generating questions…
        </div>
      ) : questions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0', color: '#8E8E93', fontSize: 12 }}>
          No questions generated yet. Tap 🔄 to generate.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {questions.map((q, i) => {
            const isOpen = expanded.has(i);
            const col = PRIORITY_COLOR[q.priority] || '#007AFF';
            const bg = PRIORITY_BG[q.priority] || '#F0F6FF';
            const lbl = PRIORITY_LABEL[q.priority] || 'SUGGESTED';
            return (
              <div
                key={i}
                onClick={() => toggle(i)}
                style={{
                  border: `1px solid ${col}22`, borderRadius: 12,
                  background: isOpen ? bg : 'white', cursor: 'pointer',
                  overflow: 'hidden',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px' }}>
                  <span style={{ fontSize: 18, flexShrink: 0 }}>{q.icon || '🩺'}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{
                        fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 20,
                        background: col, color: 'white',
                      }}>{lbl}</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: 13, color: '#1C1C1E', lineHeight: 1.4 }}>{q.q}</div>
                  </div>
                  <span style={{ color: '#C7C7CC', fontSize: 12, flexShrink: 0, marginTop: 2 }}>
                    {isOpen ? '▲' : '▼'}
                  </span>
                </div>
                {isOpen && (
                  <div style={{
                    padding: '0 12px 12px 12px',
                    fontSize: 12, color: '#3C3C43', lineHeight: 1.6,
                    borderTop: `1px solid ${col}22`,
                    paddingTop: 8,
                  }}>
                    {q.context}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Conditions Chronology (zayn two-column layout)
───────────────────────────────────────────────────────────────── */
function ConditionsChronology({
  timeline, total,
}: {
  timeline: TimelineEvent[];
  total: number;
}) {
  const [isFull, setIsFull] = useState(false);

  const visibleEvents = isFull ? timeline : timeline.slice(0, 1);
  const hasMore = timeline.length > 1;

  const formatDate = (d: string | undefined) => {
    if (!d) return '';
    const dt = new Date(d);
    if (isNaN(dt.getTime())) return d;
    return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' });
  };

  return (
    <div style={{
      background: 'white', borderRadius: 20, overflow: 'hidden',
      border: '1.5px solid #E5E5EA', boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px',
        borderBottom: '1px solid #F2F2F7',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8, background: '#FFF5F0',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
          }}>📅</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#1C1C1E' }}>Health Management Timeline</div>
            <div style={{ fontSize: 11, color: '#8E8E93' }}>{total || timeline.length} events recorded</div>
          </div>
        </div>
        {isFull && (
          <button
            onClick={() => setIsFull(false)}
            style={{
              fontSize: 11, fontWeight: 600, color: '#8E8E93',
              background: 'none', border: 'none', cursor: 'pointer',
            }}
          >
            ↑ Collapse
          </button>
        )}
      </div>

      {/* Events */}
      {timeline.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', color: '#C7C7CC', fontSize: 12 }}>
          No events recorded yet.
        </div>
      ) : (
        <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {visibleEvents.map((ev, idx) => {
            const labelColor = ev.label_color || '#007AFF';
            const labelBg = `${labelColor}12`;
            const border = ev.border || labelColor;

            return (
              <div key={idx} style={{ display: 'flex', gap: 12 }}>
                {/* Left column — 80px label box */}
                <div style={{
                  width: 80, flexShrink: 0,
                  background: labelBg, border: `1px solid ${border}30`,
                  borderRadius: 12, padding: '10px 6px',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  gap: 3, textAlign: 'center',
                }}>
                  <span style={{ fontSize: 18 }}>{ev.icon || '📋'}</span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: labelColor,
                    textTransform: 'uppercase', letterSpacing: 0.3, lineHeight: 1.2,
                  }}>
                    {ev.tag || ev.type}
                  </span>
                  {ev.sublabel && (
                    <span style={{ fontSize: 9, color: '#8E8E93', lineHeight: 1.2 }}>{ev.sublabel}</span>
                  )}
                  <span style={{ fontSize: 9, color: '#8E8E93', marginTop: 2 }}>
                    {formatDate(ev.date)}
                  </span>
                </div>

                {/* Right column — white card */}
                <div style={{
                  flex: 1, minWidth: 0,
                  background: 'white', border: '1px solid #E5E5EA',
                  borderRadius: 12, padding: '10px 12px',
                }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: '#1C1C1E', marginBottom: 3 }}>
                    {ev.title}
                  </div>
                  {ev.source_text && (
                    <div style={{ fontSize: 11, color: '#8E8E93', marginBottom: 6 }}>{ev.source_text}</div>
                  )}
                  {/* Pills */}
                  {ev.pills && ev.pills.length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {ev.pills.map((pill, pi) => (
                        <span key={pi} style={{
                          fontSize: 10, fontWeight: 600,
                          padding: '2px 8px', borderRadius: 20,
                          background: pill.bg || '#F2F2F7',
                          color: pill.c || '#3C3C43',
                        }}>
                          {pill.t}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Fallback: notes */}
                  {(!ev.pills || ev.pills.length === 0) && ev.detail && (
                    <div style={{ fontSize: 11, color: '#3C3C43', lineHeight: 1.5 }}>{ev.detail}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* See All / Expand button */}
      {hasMore && !isFull && (
        <div style={{ padding: '0 16px 16px' }}>
          <button
            onClick={() => setIsFull(true)}
            style={{
              width: '100%', padding: '12px',
              background: '#D44800', border: 'none', borderRadius: 12,
              fontSize: 13, fontWeight: 700, color: 'white', cursor: 'pointer',
              letterSpacing: 0.2,
            }}
          >
            See all {total || timeline.length} events ↓
          </button>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   PDF Card
───────────────────────────────────────────────────────────────── */
function ConditionsPdfCard({
  petName, pdfState, onGenerate, onReset,
}: {
  petName: string;
  pdfState: 'idle' | 'generating' | 'done';
  onGenerate: () => void;
  onReset: () => void;
}) {
  return (
    <div style={{
      background: 'white', borderRadius: 16, padding: 16,
      border: '1.5px solid #E5E5EA', textAlign: 'center',
    }}>
      <div style={{ fontSize: 24, marginBottom: 6 }}>📋</div>
      <div style={{ fontWeight: 700, fontSize: 14, color: '#1C1C1E', marginBottom: 4 }}>
        Complete Health Analysis
      </div>
      <div style={{ fontSize: 12, color: '#8E8E93', marginBottom: 14 }}>
        Download {petName}&apos;s full health report with conditions, medications, and timeline.
      </div>
      {pdfState === 'done' ? (
        <button
          onClick={onReset}
          style={{
            width: '100%', padding: '11px', borderRadius: 12,
            background: '#E8FAF0', border: 'none', fontSize: 13,
            fontWeight: 600, color: '#34C759', cursor: 'pointer',
          }}
        >
          ✓ Report Generated!
        </button>
      ) : (
        <button
          onClick={onGenerate}
          disabled={pdfState === 'generating'}
          style={{
            width: '100%', padding: '11px', borderRadius: 12,
            background: 'var(--brand-gradient)', border: 'none', fontSize: 13,
            fontWeight: 600, color: 'white', cursor: pdfState === 'generating' ? 'default' : 'pointer',
            opacity: pdfState === 'generating' ? 0.7 : 1,
          }}
        >
          {pdfState === 'generating' ? '⏳ Generating…' : '⬇ Download PDF Report'}
        </button>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Main Export
───────────────────────────────────────────────────────────────── */
export default function ConditionsTab({ data, token, onCartClick }: ConditionsTabProps) {
  const [addSheet, setAddSheet] = useState(false);
  const [conditionForm, setConditionForm] = useState({
    name: '', diagnosis: '', since: '', notes: '', condition_type: 'chronic', icon: '', managed_by: '',
  });
  const [saving, setSaving] = useState(false);
  const [pdfState, setPdfState] = useState<'idle' | 'generating' | 'done'>('idle');

  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [timelineTotal, setTimelineTotal] = useState(0);
  const [vetVisit, setVetVisit] = useState<LastVetVisit | null>(null);

  const [healthSummary, setHealthSummary] = useState('');
  const [vetQuestions, setVetQuestions] = useState<VetQuestion[]>([]);
  const [vetQLoading, setVetQLoading] = useState(false);

  const [addMedSheet, setAddMedSheet] = useState<string | null>(null);
  const [medForm, setMedForm] = useState({ name: '', dose: '', frequency: '', route: '' });
  const [addMonSheet, setAddMonSheet] = useState<string | null>(null);
  const [monForm, setMonForm] = useState({ name: '', frequency: '' });

  const conditions = data.conditions || [];
  const petName = data.pet?.name || 'Pet';
  const healthScore = data.health_score || { score: 0, label: 'Unknown', breakdown: [], draggers: [] };
  const activeCount = conditions.filter(c => c.condition_type !== 'resolved').length;

  const loadData = useCallback(async () => {
    const [timelineRes, vetRes, summaryRes, qRes] = await Promise.allSettled([
      getConditionTimeline(token),
      getLastVetVisit(token),
      getHealthSummary(token),
      getVetQuestions(token),
    ]);
    if (timelineRes.status === 'fulfilled') {
      setTimeline(timelineRes.value.events || []);
      setTimelineTotal(timelineRes.value.total || (timelineRes.value.events || []).length);
    }
    if (vetRes.status === 'fulfilled') setVetVisit(vetRes.value);
    if (summaryRes.status === 'fulfilled') setHealthSummary(summaryRes.value.summary || '');
    if (qRes.status === 'fulfilled') setVetQuestions(qRes.value);
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRegenerate = async () => {
    setVetQLoading(true);
    try {
      const q = await regenerateVetQuestions(token);
      setVetQuestions(q);
    } finally {
      setVetQLoading(false);
    }
  };

  const handleAddCondition = async () => {
    if (!conditionForm.name.trim()) return;
    setSaving(true);
    try {
      await addCondition(token, {
        name: conditionForm.name.trim(),
        diagnosis: conditionForm.diagnosis.trim() || undefined,
        condition_type: conditionForm.condition_type,
        diagnosed_at: conditionForm.since.trim() || undefined,
        notes: conditionForm.notes.trim() || undefined,
        icon: conditionForm.icon.trim() || undefined,
        managed_by: conditionForm.managed_by.trim() || undefined,
      });
      setConditionForm({ name: '', diagnosis: '', since: '', notes: '', condition_type: 'chronic', icon: '', managed_by: '' });
      setAddSheet(false);
      window.location.reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to add condition');
    } finally { setSaving(false); }
  };

  const handleDeleteCondition = async (conditionId: string) => {
    if (!confirm('Deactivate this condition?')) return;
    try {
      await deleteCondition(token, conditionId);
      window.location.reload();
    } catch (e) { alert(e instanceof Error ? e.message : 'Failed to remove condition'); }
  };

  const handleAddMed = async () => {
    if (!addMedSheet || !medForm.name.trim()) return;
    setSaving(true);
    try {
      await addConditionMedication(token, addMedSheet, {
        name: medForm.name.trim(),
        dose: medForm.dose.trim() || undefined,
        frequency: medForm.frequency.trim() || undefined,
        route: medForm.route.trim() || undefined,
      });
      setMedForm({ name: '', dose: '', frequency: '', route: '' });
      setAddMedSheet(null);
      window.location.reload();
    } catch (e) { alert(e instanceof Error ? e.message : 'Failed to add medication'); }
    finally { setSaving(false); }
  };

  const handleDeleteMed = async (medId: string) => {
    if (!confirm('Remove this medication?')) return;
    try { await deleteConditionMedication(token, medId); window.location.reload(); }
    catch (e) { alert(e instanceof Error ? e.message : 'Failed to remove medication'); }
  };

  const handleAddMon = async () => {
    if (!addMonSheet || !monForm.name.trim()) return;
    setSaving(true);
    try {
      await addConditionMonitoring(token, addMonSheet, {
        name: monForm.name.trim(),
        frequency: monForm.frequency.trim() || undefined,
      });
      setMonForm({ name: '', frequency: '' });
      setAddMonSheet(null);
      window.location.reload();
    } catch (e) { alert(e instanceof Error ? e.message : 'Failed to add monitoring'); }
    finally { setSaving(false); }
  };

  const handleDeleteMon = async (monId: string) => {
    if (!confirm('Remove this monitoring item?')) return;
    try { await deleteConditionMonitoring(token, monId); window.location.reload(); }
    catch (e) { alert(e instanceof Error ? e.message : 'Failed to remove monitoring'); }
  };

  const handleGeneratePdf = async () => {
    setPdfState('generating');
    try {
      const { generateHealthPdf } = await import('@/lib/generate-pdf');
      generateHealthPdf(data);
      setPdfState('done');
    } catch (err) {
      console.error('PDF generation failed:', err);
      setPdfState('idle');
      alert('Could not generate PDF. Please try again.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, animation: 'slideUp 0.4s ease' }}>

      {/* 1. Health Score Card — only shown when there are conditions */}
      {conditions.length > 0 && (
        <HealthScoreCard
          activeCount={activeCount}
          summary={healthSummary}
          conditions={conditions.filter(c => c.condition_type !== 'resolved')}
        />
      )}

      {/* 2. Unified Conditions Card */}
      {conditions.length > 0 ? (
        <div style={{
          background: 'white', borderRadius: 20,
          border: '1.5px solid #E5E5EA', boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
          overflow: 'hidden',
        }}>
          {/* Card header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 16px', borderBottom: '1px solid #F2F2F7',
          }}>
            <span style={{ fontWeight: 700, fontSize: 15, color: '#1C1C1E' }}>Ongoing Conditions</span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20,
              background: '#FFF5F0', color: '#D44800',
            }}>
              {activeCount} Active
            </span>
          </div>

          {/* One ConditionCard per condition, separated by dividers */}
          {conditions.map((condition, idx) => (
            <div key={condition.id}>
              {idx > 0 && <div style={{ height: 1, background: '#F2F2F7', margin: '0 16px' }} />}
              <div style={{ padding: '0 0 8px' }}>
                <ConditionCard
                  condition={condition}
                  onDelete={() => handleDeleteCondition(condition.id)}
                  onAddMed={() => setAddMedSheet(condition.id)}
                  onDeleteMed={handleDeleteMed}
                  onAddMon={() => setAddMonSheet(condition.id)}
                  onDeleteMon={handleDeleteMon}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          background: 'white', borderRadius: 20, padding: 24, textAlign: 'center',
          border: '1.5px solid #E5E5EA',
        }}>
          <span style={{ fontSize: 36, display: 'block', marginBottom: 8 }}>🎉</span>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#1C1C1E', marginBottom: 4 }}>No Conditions Recorded</div>
          <div style={{ fontSize: 12, color: '#8E8E93', lineHeight: 1.5 }}>
            When your vet identifies a condition, it will appear here with medication tracking, monitoring schedules, and management chronology.
          </div>
        </div>
      )}

      {/* 4. Add Another Condition */}
      <button
        onClick={() => setAddSheet(true)}
        style={{
          width: '100%', background: 'white', border: '1.5px dashed #C7C7CC',
          borderRadius: 14, padding: 16, display: 'flex', alignItems: 'center',
          gap: 12, cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{
          width: 40, height: 40, borderRadius: 12, background: '#F2F2F7',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        }}>➕</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>Add Another Condition</div>
          <div style={{ fontSize: 12, color: '#8E8E93' }}>Diabetes, allergies, skin conditions & more</div>
        </div>
      </button>

      {/* 5. Last Vet Visit */}
      <LastVetVisitCard vetVisit={vetVisit} />

      {/* 6. Ask the Vet — only shown when there are conditions */}
      {conditions.length > 0 && (
        <AskTheVetSection
          questions={vetQuestions}
          loading={vetQLoading}
          onRegenerate={handleRegenerate}
        />
      )}

      {/* 7. Health Management Timeline */}
      {(timeline.length > 0 || conditions.length > 0) && (
        <ConditionsChronology timeline={timeline} total={timelineTotal} />
      )}

      {/* 8. PDF Card */}
      <ConditionsPdfCard
        petName={petName}
        pdfState={pdfState}
        onGenerate={handleGeneratePdf}
        onReset={() => setPdfState('idle')}
      />

      {/* ─── Sheets ─── */}
      <BottomSheet open={addSheet} onClose={() => setAddSheet(false)} title="Add Condition">
        <div className="space-y-3">
          {[
            { key: 'name', label: 'Name', placeholder: 'e.g. Hip Dysplasia' },
            { key: 'diagnosis', label: 'Diagnosis', placeholder: 'Brief diagnosis description' },
            { key: 'since', label: 'Diagnosed Since', placeholder: 'DD/MM/YYYY' },
            { key: 'managed_by', label: 'Managing Vet', placeholder: 'e.g. Dr. Meera Nair, Bandra' },
            { key: 'icon', label: 'Icon', placeholder: 'e.g. 🦴' },
          ].map(field => (
            <div key={field.key}>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">{field.label}</label>
              <input
                type="text"
                value={(conditionForm as Record<string, string>)[field.key]}
                onChange={(e) => setConditionForm({ ...conditionForm, [field.key]: e.target.value })}
                placeholder={field.placeholder}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
                maxLength={field.key === 'icon' ? 4 : undefined}
              />
            </div>
          ))}
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Type</label>
            <div className="flex gap-2">
              {(['chronic', 'episodic', 'resolved'] as const).map(t => (
                <button key={t} onClick={() => setConditionForm({ ...conditionForm, condition_type: t })}
                  className="flex-1 py-2 rounded-xl text-xs font-semibold border transition-colors"
                  style={{
                    borderColor: conditionForm.condition_type === t ? '#D44800' : '#E5E7EB',
                    backgroundColor: conditionForm.condition_type === t ? '#FFF5F0' : 'white',
                    color: conditionForm.condition_type === t ? '#D44800' : '#6B7280',
                  }}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Notes</label>
            <textarea value={conditionForm.notes}
              onChange={(e) => setConditionForm({ ...conditionForm, notes: e.target.value })}
              placeholder="Additional notes..." rows={2}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand resize-none" />
          </div>
          <button onClick={handleAddCondition} disabled={saving || !conditionForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}>
            {saving ? 'Adding…' : 'Add Condition'}
          </button>
        </div>
      </BottomSheet>

      <BottomSheet open={!!addMedSheet} onClose={() => setAddMedSheet(null)} title="Add Medication">
        <div className="space-y-3">
          {[
            { key: 'name', label: 'Medication Name', placeholder: 'e.g. Gabapentin' },
            { key: 'dose', label: 'Dose', placeholder: 'e.g. 100mg' },
            { key: 'frequency', label: 'Frequency', placeholder: 'e.g. Twice daily' },
            { key: 'route', label: 'Route', placeholder: 'e.g. Oral' },
          ].map(field => (
            <div key={field.key}>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">{field.label}</label>
              <input type="text" value={(medForm as Record<string, string>)[field.key]}
                onChange={(e) => setMedForm({ ...medForm, [field.key]: e.target.value })}
                placeholder={field.placeholder}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand" />
            </div>
          ))}
          <button onClick={handleAddMed} disabled={saving || !medForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}>
            {saving ? 'Adding…' : 'Add Medication'}
          </button>
        </div>
      </BottomSheet>

      <BottomSheet open={!!addMonSheet} onClose={() => setAddMonSheet(null)} title="Add Monitoring">
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Check Name</label>
            <input type="text" value={monForm.name}
              onChange={(e) => setMonForm({ ...monForm, name: e.target.value })}
              placeholder="e.g. Blood Work"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Frequency</label>
            <input type="text" value={monForm.frequency}
              onChange={(e) => setMonForm({ ...monForm, frequency: e.target.value })}
              placeholder="e.g. Every 6 months"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand" />
          </div>
          <button onClick={handleAddMon} disabled={saving || !monForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}>
            {saving ? 'Adding…' : 'Add Monitoring'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
