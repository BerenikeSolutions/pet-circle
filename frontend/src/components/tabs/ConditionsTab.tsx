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
} from '@/lib/api';
import {
  addCondition,
  deleteCondition,
  updateCondition,
  getConditionTimeline,
  getConditionRecommendations,
  getLastVetVisit,
  addConditionMedication,
  deleteConditionMedication,
  addConditionMonitoring,
  deleteConditionMonitoring,
} from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CollapsibleCard from '@/components/ui/CollapsibleCard';
import ReminderBar from '@/components/ui/ReminderBar';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import { formatApiDate, STATUS_CONFIG } from '@/lib/dashboard-utils';

interface ConditionsTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
}

/** Compute refill status from a date string */
function getRefillStatus(refillDueDate: string | null): string {
  if (!refillDueDate) return 'ok';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(refillDueDate);
  if (isNaN(due.getTime())) return 'ok';
  const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff <= 0) return 'urgent';
  if (diff <= 14) return 'upcoming';
  return 'ok';
}

/** Compute monitoring status from next_due_date */
function getMonitoringStatus(nextDueDate: string | null): string {
  if (!nextDueDate) return 'upcoming';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(nextDueDate);
  if (isNaN(due.getTime())) return 'upcoming';
  const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return 'overdue';
  if (diff <= 30) return 'upcoming';
  return 'done';
}

/** Format a date relative to today */
function getDateRelative(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const diff = Math.ceil((today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diff > 180) return '6+ months ago';
  if (diff > 30) return `${Math.floor(diff / 30)} months ago`;
  if (diff > 0) return `${diff} days ago`;
  return 'Today';
}

const TAG_COLORS: Record<string, string> = {
  Diagnosis: '#007AFF',
  'Vet Visit': '#34C759',
  Treatment: '#FF9500',
  Grooming: '#8E44AD',
  Overdue: '#FF3B30',
  Upcoming: '#FF9500',
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#FF3B30',
  high: '#FF9500',
  medium: '#007AFF',
};

const PRIORITY_BG: Record<string, string> = {
  urgent: '#FFF0F0',
  high: '#FFF6ED',
  medium: '#F0F6FF',
};

const PRIORITY_LABEL: Record<string, string> = {
  urgent: 'URGENT',
  high: 'RECOMMENDED',
  medium: 'SUGGESTED',
};

export default function ConditionsTab({ data, token, onCartClick }: ConditionsTabProps) {
  const [addSheet, setAddSheet] = useState(false);
  const [conditionForm, setConditionForm] = useState({
    name: '', diagnosis: '', since: '', notes: '', condition_type: 'chronic', icon: '', managed_by: '',
  });
  const [saving, setSaving] = useState(false);
  const [pdfState, setPdfState] = useState<'idle' | 'generating' | 'done'>('idle');
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [recommendations, setRecommendations] = useState<ConditionRecommendation[]>([]);
  const [vetVisit, setVetVisit] = useState<LastVetVisit | null>(null);
  const [addMedSheet, setAddMedSheet] = useState<string | null>(null);
  const [medForm, setMedForm] = useState({ name: '', dose: '', frequency: '', route: '' });
  const [addMonSheet, setAddMonSheet] = useState<string | null>(null);
  const [monForm, setMonForm] = useState({ name: '', frequency: '' });

  const conditions = data.conditions || [];
  const diagnostics = data.diagnostic_results || [];
  const petName = data.pet?.name || 'Pet';
  const hasConditions = conditions.length > 0;
  const hasDiagnostics = diagnostics.length > 0;

  // Group diagnostics by test_type
  const paramsByType = diagnostics.reduce((acc, d) => {
    const key = d.test_type || 'Other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {} as Record<string, typeof diagnostics>);

  // Load timeline, recommendations, and vet visit from API
  const loadSupplementary = useCallback(async () => {
    try {
      const [timelineRes, recsRes, vetRes] = await Promise.allSettled([
        getConditionTimeline(token),
        getConditionRecommendations(token),
        getLastVetVisit(token),
      ]);
      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value.events || []);
      if (recsRes.status === 'fulfilled') setRecommendations(recsRes.value.recommendations || []);
      if (vetRes.status === 'fulfilled') setVetVisit(vetRes.value);
    } catch {
      // Supplementary data — don't block
    }
  }, [token]);

  useEffect(() => {
    loadSupplementary();
  }, [loadSupplementary]);

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
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCondition = async (conditionId: string) => {
    if (!confirm('Deactivate this condition?')) return;
    try {
      await deleteCondition(token, conditionId);
      window.location.reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to remove condition');
    }
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
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to add medication');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteMed = async (medId: string) => {
    if (!confirm('Remove this medication?')) return;
    try {
      await deleteConditionMedication(token, medId);
      window.location.reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to remove medication');
    }
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
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to add monitoring');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteMon = async (monId: string) => {
    if (!confirm('Remove this monitoring item?')) return;
    try {
      await deleteConditionMonitoring(token, monId);
      window.location.reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to remove monitoring');
    }
  };

  const handleGeneratePdf = () => {
    setPdfState('generating');
    setTimeout(() => setPdfState('done'), 2200);
  };

  return (
    <div className="space-y-3" style={{ animation: 'slideUp 0.4s ease' }}>
      {/* Condition Cards */}
      {hasConditions ? (
        conditions.map((condition) => (
          <ConditionCard
            key={condition.id}
            condition={condition}
            recommendations={recommendations}
            onDelete={() => handleDeleteCondition(condition.id)}
            onAddMed={() => setAddMedSheet(condition.id)}
            onDeleteMed={handleDeleteMed}
            onAddMon={() => setAddMonSheet(condition.id)}
            onDeleteMon={handleDeleteMon}
            onCartClick={onCartClick}
          />
        ))
      ) : hasDiagnostics ? (
        Object.entries(paramsByType).map(([type, params]) => (
          <div key={type} className="bg-white rounded-2xl shadow-sm p-4 space-y-3" style={{ border: '1.5px solid #007AFF' }}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <span>🏥</span> {type.charAt(0).toUpperCase() + type.slice(1)} Results
              </h3>
              <StatusBadge status="managed" />
            </div>
            <div className="space-y-2">
              {params.map((p, i) => {
                const isNormal = p.status_flag === 'normal';
                return (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                    <div>
                      <p className="text-sm text-gray-800">{p.parameter_name}</p>
                      <p className="text-[11px] text-gray-500">
                        {p.value_numeric ?? p.value_text} {p.unit} · Ref: {p.reference_range || '—'}
                      </p>
                    </div>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                      style={{
                        color: isNormal ? '#34C759' : '#FF3B30',
                        backgroundColor: isNormal ? '#F0FFF4' : '#FFF0F0',
                      }}
                    >
                      {p.status_flag || 'Unknown'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))
      ) : (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 text-center">
          <span className="text-4xl mb-3 block">🎉</span>
          <h3 className="font-semibold text-sm text-gray-900 mb-1">No Conditions Recorded</h3>
          <p className="text-xs text-gray-500">
            When your vet identifies a condition, it will appear here with medication tracking, monitoring schedules, and management chronology.
          </p>
        </div>
      )}

      {/* Diagnostic Results (shown alongside conditions when both exist) */}
      {hasConditions && hasDiagnostics && (
        <CollapsibleCard icon="🔬" title="Diagnostic Results" subtitle="Lab values and reports">
          <div className="p-4 space-y-3">
            {Object.entries(paramsByType).map(([type, params]) => (
              <div key={type}>
                <p className="text-[10px] font-bold text-gray-400 uppercase mb-2">{type}</p>
                <div className="space-y-1">
                  {params.map((p, i) => {
                    const isNormal = p.status_flag === 'normal';
                    return (
                      <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                        <div>
                          <p className="text-sm text-gray-800">{p.parameter_name}</p>
                          <p className="text-[11px] text-gray-500">
                            {p.value_numeric ?? p.value_text} {p.unit} · Ref: {p.reference_range || '—'}
                          </p>
                        </div>
                        <span
                          className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                          style={{
                            color: isNormal ? '#34C759' : '#FF3B30',
                            backgroundColor: isNormal ? '#F0FFF4' : '#FFF0F0',
                          }}
                        >
                          {p.status_flag || 'Unknown'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleCard>
      )}

      {/* Add Another Condition — styled button matching JSX */}
      <button
        onClick={() => setAddSheet(true)}
        className="w-full text-left"
        style={{
          background: 'white',
          border: '1.5px dashed #C7C7CC',
          borderRadius: 14,
          padding: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          cursor: 'pointer',
        }}
      >
        <div style={{
          width: 40, height: 40, borderRadius: 12,
          background: '#F2F2F7', display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontSize: 20,
        }}>
          ➕
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>Add Another Condition</div>
          <div style={{ fontSize: 12, color: '#8E8E93' }}>Diabetes, allergies, skin conditions & more</div>
        </div>
      </button>

      {/* Last Vet Visit */}
      <LastVetVisitCard vetVisit={vetVisit} />

      {/* Management Chronology */}
      {(timeline.length > 0 || hasConditions) && (
        <ConditionsChronology timeline={timeline} conditions={conditions} />
      )}

      {/* Complete Health Analysis PDF */}
      <ConditionsPdfCard
        petName={petName}
        pdfState={pdfState}
        onGenerate={handleGeneratePdf}
        onReset={() => setPdfState('idle')}
      />

      {/* Add Condition Sheet */}
      <BottomSheet open={addSheet} onClose={() => setAddSheet(false)} title="Add Condition">
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Name</label>
            <input
              type="text"
              value={conditionForm.name}
              onChange={(e) => setConditionForm({ ...conditionForm, name: e.target.value })}
              placeholder="e.g. Hip Dysplasia"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Diagnosis</label>
            <input
              type="text"
              value={conditionForm.diagnosis}
              onChange={(e) => setConditionForm({ ...conditionForm, diagnosis: e.target.value })}
              placeholder="Brief diagnosis description"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Type</label>
            <div className="flex gap-2">
              {(['chronic', 'episodic', 'resolved'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setConditionForm({ ...conditionForm, condition_type: t })}
                  className="flex-1 py-2 rounded-xl text-xs font-semibold border transition-colors"
                  style={{
                    borderColor: conditionForm.condition_type === t ? '#D44800' : '#E5E7EB',
                    backgroundColor: conditionForm.condition_type === t ? '#FFF5F0' : 'white',
                    color: conditionForm.condition_type === t ? '#D44800' : '#6B7280',
                  }}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Diagnosed Since</label>
            <input
              type="text"
              value={conditionForm.since}
              onChange={(e) => setConditionForm({ ...conditionForm, since: e.target.value })}
              placeholder="DD/MM/YYYY"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Managing Vet</label>
            <input
              type="text"
              value={conditionForm.managed_by}
              onChange={(e) => setConditionForm({ ...conditionForm, managed_by: e.target.value })}
              placeholder="e.g. Dr. Meera Nair, Bandra"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Icon</label>
            <input
              type="text"
              value={conditionForm.icon}
              onChange={(e) => setConditionForm({ ...conditionForm, icon: e.target.value })}
              placeholder="e.g. 🦴"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              maxLength={4}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Notes</label>
            <textarea
              value={conditionForm.notes}
              onChange={(e) => setConditionForm({ ...conditionForm, notes: e.target.value })}
              placeholder="Additional notes..."
              rows={2}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand resize-none"
            />
          </div>
          <button
            onClick={handleAddCondition}
            disabled={saving || !conditionForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Adding...' : 'Add Condition'}
          </button>
        </div>
      </BottomSheet>

      {/* Add Medication Sheet */}
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
              <input
                type="text"
                value={(medForm as Record<string, string>)[field.key]}
                onChange={(e) => setMedForm({ ...medForm, [field.key]: e.target.value })}
                placeholder={field.placeholder}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
            </div>
          ))}
          <button
            onClick={handleAddMed}
            disabled={saving || !medForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Adding...' : 'Add Medication'}
          </button>
        </div>
      </BottomSheet>

      {/* Add Monitoring Sheet */}
      <BottomSheet open={!!addMonSheet} onClose={() => setAddMonSheet(null)} title="Add Monitoring">
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Check Name</label>
            <input
              type="text"
              value={monForm.name}
              onChange={(e) => setMonForm({ ...monForm, name: e.target.value })}
              placeholder="e.g. Blood Work"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Frequency</label>
            <input
              type="text"
              value={monForm.frequency}
              onChange={(e) => setMonForm({ ...monForm, frequency: e.target.value })}
              placeholder="e.g. Every 6 months"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
            />
          </div>
          <button
            onClick={handleAddMon}
            disabled={saving || !monForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {saving ? 'Adding...' : 'Add Monitoring'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Condition Card — matches JSX renderConditionsTab exactly    */
/* ───────────────────────────────────────────────────────────── */

function ConditionCard({
  condition,
  recommendations,
  onDelete,
  onAddMed,
  onDeleteMed,
  onAddMon,
  onDeleteMon,
  onCartClick,
}: {
  condition: ConditionItem;
  recommendations: ConditionRecommendation[];
  onDelete: () => void;
  onAddMed: () => void;
  onDeleteMed: (id: string) => void;
  onAddMon: () => void;
  onDeleteMon: (id: string) => void;
  onCartClick: (itemId?: string) => void;
}) {
  const statusMap: Record<string, string> = {
    chronic: 'managed',
    episodic: 'upcoming',
    resolved: 'done',
  };

  const badgeLabelMap: Record<string, string> = {
    chronic: 'MANAGED',
    episodic: 'EPISODIC',
    resolved: 'RESOLVED',
  };

  const hasUrgentMeds = condition.medications.some(
    m => m.status === 'active' && getRefillStatus(m.refill_due_date) !== 'ok'
  );

  // Filter recommendations relevant to this condition
  const condRecs = recommendations.filter(
    r => r.title.toLowerCase().includes(condition.name.toLowerCase()) ||
         r.reason.toLowerCase().includes(condition.name.toLowerCase())
  );

  return (
    <div
      className="bg-white rounded-2xl p-4"
      style={{
        border: '1.5px solid #007AFF',
        boxShadow: '0 2px 12px rgba(0,122,255,0.1)',
      }}
    >
      {/* Header with icon box */}
      <div className="flex items-center gap-2.5 mb-3">
        <div
          style={{
            width: 44, height: 44, borderRadius: 12,
            background: '#F0F6FF', display: 'flex',
            alignItems: 'center', justifyContent: 'center', fontSize: 22,
          }}
        >
          {condition.icon || '🏥'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-[15px]">{condition.name}</div>
          <div className="text-xs text-[#8E8E93]">
            {condition.diagnosed_at ? `Diagnosed ${formatApiDate(condition.diagnosed_at)}` : ''}
            {condition.managed_by ? ` · ${condition.managed_by}` : ''}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <StatusBadge
            status={statusMap[condition.condition_type] || 'managed'}
            label={badgeLabelMap[condition.condition_type] || condition.condition_type.toUpperCase()}
          />
          <button onClick={onDelete} className="text-gray-400 hover:text-red-500 text-xs" title="Remove">✕</button>
        </div>
      </div>

      {/* Current Medications */}
      <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
        Current medications
      </div>
      {condition.medications.length > 0 ? (
        condition.medications.map((med) => (
          <MedRow
            key={med.id}
            med={med}
            onDelete={() => onDeleteMed(med.id)}
            onOrder={() => onCartClick()}
          />
        ))
      ) : (
        <p className="text-xs text-gray-400 mb-2">No medications added</p>
      )}
      <AddRow label="Add medication" onClick={onAddMed} />

      {/* Order Medications button if any urgent/upcoming */}
      {hasUrgentMeds && (
        <button
          onClick={() => onCartClick()}
          style={{
            width: '100%', marginTop: 10, background: '#D44800',
            color: 'white', border: 'none', borderRadius: 10,
            padding: '10px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
          }}
        >
          🔄 Order Medications
        </button>
      )}

      {/* Monitoring Checkups */}
      <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5, margin: '14px 0 8px' }}>
        Monitoring checkups
      </div>
      {condition.monitoring.length > 0 ? (
        condition.monitoring.map((mon, j) => (
          <MonitorRow
            key={mon.id}
            mon={mon}
            isFirst={j === 0}
            onDelete={() => onDeleteMon(mon.id)}
          />
        ))
      ) : (
        <p className="text-xs text-gray-400 mb-2">No monitoring items</p>
      )}
      <button
        onClick={() => onCartClick()}
        style={{
          width: '100%', marginTop: 12, background: '#D44800',
          color: 'white', border: 'none', borderRadius: 10,
          padding: '10px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
        }}
      >
        📅 Book Tests
      </button>

      {/* PetCircle Recommendations */}
      {condRecs.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="flex items-center gap-1.5 mb-2.5">
            <div style={{
              width: 20, height: 20, borderRadius: 6, background: '#D44800',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
            }}>
              🐾
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#D44800', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              PetCircle Recommendations
            </div>
          </div>
          <div className="flex flex-col gap-2">
            {condRecs.map((rec, k) => {
              const pColor = PRIORITY_COLORS[rec.priority] || '#007AFF';
              const pBg = PRIORITY_BG[rec.priority] || '#F0F6FF';
              const pLabel = PRIORITY_LABEL[rec.priority] || 'INFO';
              return (
                <div
                  key={k}
                  style={{
                    background: pBg,
                    border: `1px solid ${pColor}22`,
                    borderRadius: 10,
                    padding: '10px 12px',
                  }}
                >
                  <div className="flex items-start gap-2.5">
                    <div style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>{rec.icon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#1A1A1A' }}>{rec.title}</div>
                        <div style={{
                          background: pColor + '22', color: pColor,
                          borderRadius: 20, padding: '1px 7px', fontSize: 10, fontWeight: 700, flexShrink: 0,
                        }}>
                          {pLabel}
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: '#555', lineHeight: 1.45, marginBottom: rec.cart_id ? 8 : 0 }}>
                        {rec.reason}
                      </div>
                      {rec.cart_id && (
                        <button
                          onClick={() => onCartClick(rec.cart_id!)}
                          style={{
                            background: pColor, color: 'white', border: 'none',
                            borderRadius: 8, padding: '6px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
                          }}
                        >
                          Order Now →
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {condition.notes && (
        <div style={{ marginTop: 12, background: '#F0F6FF', borderRadius: 10, padding: '10px 12px', fontSize: 12, color: '#007AFF', lineHeight: 1.5 }}>
          📋 Vet Notes: {condition.notes}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Med Row — refill due date + status badge matching JSX       */
/* ───────────────────────────────────────────────────────────── */

function MedRow({
  med,
  onDelete,
  onOrder,
}: {
  med: ConditionMedicationItem;
  onDelete: () => void;
  onOrder: () => void;
}) {
  const [reminderOn, setReminderOn] = useState(true);
  const [freq, setFreq] = useState(1);
  const [unit, setUnit] = useState('month');

  const refillStatus = getRefillStatus(med.refill_due_date);
  const st = STATUS_CONFIG[refillStatus] || STATUS_CONFIG.upcoming;
  const isUrgent = refillStatus === 'urgent';

  return (
    <div style={{
      background: isUrgent ? '#FFF0F0' : '#F7F4F0',
      borderRadius: 10, padding: '10px 12px', marginBottom: 6,
    }}>
      <div className="flex items-center gap-2.5">
        <div style={{ fontSize: 16 }}>💊</div>
        <div className="flex-1 min-w-0">
          <div style={{ fontWeight: 600, fontSize: 13 }}>{med.name}</div>
          <div style={{ fontSize: 11, color: '#8E8E93' }}>{med.dose || med.frequency || ''}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {med.refill_due_date && (
            <div style={{ fontSize: 10, color: st.color, fontWeight: 700 }}>
              Refill {formatApiDate(med.refill_due_date)}
            </div>
          )}
          <StatusBadge status={refillStatus === 'ok' ? (med.status === 'active' ? 'done' : 'missing') : refillStatus} label={refillStatus === 'ok' ? (med.status === 'active' ? 'Active' : 'Stopped') : st.label} />
        </div>
        <button onClick={onDelete} className="text-gray-300 hover:text-red-500 text-xs ml-1" title="Remove">✕</button>
      </div>
      <ReminderBar enabled={reminderOn} onToggle={setReminderOn} freq={freq} unit={unit} onFreqChange={(f, u) => { setFreq(f); setUnit(u); }} />
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Monitor Row — nextDue date + status badge matching JSX      */
/* ───────────────────────────────────────────────────────────── */

function MonitorRow({
  mon,
  isFirst,
  onDelete,
}: {
  mon: ConditionMonitoringItem;
  isFirst: boolean;
  onDelete: () => void;
}) {
  const [reminderOn, setReminderOn] = useState(true);
  const [freq, setFreq] = useState(6);
  const [unit, setUnit] = useState('month');

  const monStatus = getMonitoringStatus(mon.next_due_date);
  const st = STATUS_CONFIG[monStatus] || STATUS_CONFIG.upcoming;

  return (
    <div style={{
      borderTop: isFirst ? 'none' : '1px solid #F0EDE8',
      paddingTop: isFirst ? 0 : 8,
      marginTop: isFirst ? 0 : 8,
    }}>
      <div className="flex items-center gap-2.5 py-2">
        <div style={{ fontSize: 16 }}>🩺</div>
        <div className="flex-1 text-[13px] font-medium">{mon.name}</div>
        <div style={{ textAlign: 'right' }}>
          {mon.next_due_date && (
            <div style={{ fontSize: 11, color: '#8E8E93' }}>{formatApiDate(mon.next_due_date)}</div>
          )}
          <StatusBadge status={monStatus} label={st.label} />
        </div>
        <button onClick={onDelete} className="text-gray-300 hover:text-red-500 text-xs ml-1" title="Remove">✕</button>
      </div>
      <ReminderBar enabled={reminderOn} onToggle={setReminderOn} freq={freq} unit={unit} onFreqChange={(f, u) => { setFreq(f); setUnit(u); }} />
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Last Vet Visit — rich card matching JSX                     */
/* ───────────────────────────────────────────────────────────── */

function LastVetVisitCard({ vetVisit }: { vetVisit: LastVetVisit | null }) {
  if (!vetVisit) return null;

  const statusColors: Record<string, { color: string; bg: string; label: string }> = {
    overdue: { color: '#FF3B30', bg: '#FFF0F0', label: 'Overdue' },
    due_soon: { color: '#FF9500', bg: '#FFF6ED', label: 'Due Soon' },
    on_track: { color: '#34C759', bg: '#F0FFF4', label: 'On Track' },
  };

  const st = vetVisit.status ? statusColors[vetVisit.status] : null;

  return (
    <div style={{
      background: 'white', borderRadius: 16, padding: 16,
      border: '1.5px solid #34C75933',
      boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
    }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: '#F0FFF4', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0,
        }}>
          🩺
        </div>
        <div className="flex-1">
          <div style={{ fontWeight: 700, fontSize: 15 }}>Last Vet Visit</div>
          <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>Managing vet · condition follow-up</div>
        </div>
        {st && (
          <div style={{
            background: st.bg, color: st.color,
            borderRadius: 20, padding: '4px 11px',
            fontSize: 11, fontWeight: 700,
          }}>
            {st.label}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {/* Vet info */}
        {vetVisit.vet_name && (
          <div style={{
            display: 'flex', gap: 12, padding: '10px 12px',
            background: '#FAFAF9', borderRadius: 10, border: '1px solid #F0EDE8',
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: '#F0FFF4', display: 'flex',
              alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0,
            }}>
              👩‍⚕️
            </div>
            <div className="flex-1 min-w-0">
              <div style={{ fontWeight: 600, fontSize: 13, color: '#1A1A1A' }}>{vetVisit.vet_name}</div>
              {vetVisit.clinic_name && (
                <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 1 }}>
                  {vetVisit.clinic_name}{vetVisit.address ? ` · ${vetVisit.address}` : ''}
                </div>
              )}
              {vetVisit.managing_condition && (
                <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 1 }}>
                  {vetVisit.managing_condition} — managing since {vetVisit.managing_since ? formatApiDate(vetVisit.managing_since) : 'unknown'}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Date cards */}
        {(vetVisit.last_visit_date || vetVisit.next_due_date) && (
          <div className="flex gap-2">
            {vetVisit.last_visit_date && (
              <div className="flex-1" style={{ background: '#F7F4F0', borderRadius: 10, padding: '9px 12px' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 3 }}>
                  Last Visit
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A' }}>
                  {formatApiDate(vetVisit.last_visit_date)}
                </div>
                {(() => {
                  const rel = getDateRelative(vetVisit.last_visit_date);
                  return rel ? (
                    <div style={{ fontSize: 11, color: '#FF9500', fontWeight: 600, marginTop: 2 }}>
                      {rel}
                    </div>
                  ) : null;
                })()}
              </div>
            )}
            {vetVisit.next_due_date && (
              <div
                className="flex-1"
                style={{
                  background: vetVisit.status === 'overdue' ? '#FFF0F0' : '#FFF6ED',
                  borderRadius: 10,
                  border: `1px solid ${vetVisit.status === 'overdue' ? '#FF3B3033' : '#FF950033'}`,
                  padding: '9px 12px',
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 700, color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 3 }}>
                  Next Due
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A' }}>
                  {formatApiDate(vetVisit.next_due_date)}
                </div>
                {vetVisit.status && (
                  <div style={{
                    fontSize: 11, fontWeight: 600, marginTop: 2,
                    color: vetVisit.status === 'overdue' ? '#FF3B30' : vetVisit.status === 'due_soon' ? '#FF9500' : '#34C759',
                  }}>
                    {vetVisit.status === 'overdue' ? 'Overdue' : vetVisit.status === 'due_soon' ? 'Due Soon' : 'On Track'}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Vet Notes */}
        {vetVisit.notes && (
          <div style={{ background: '#F0F6FF', borderRadius: 10, padding: '10px 12px', fontSize: 12, color: '#007AFF', lineHeight: 1.5 }}>
            📋 Vet Notes: {vetVisit.notes}
          </div>
        )}

        {/* Empty state */}
        {!vetVisit.vet_name && !vetVisit.last_visit_date && (
          <p className="text-sm text-gray-500">No vet visit records available</p>
        )}
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Management History — vertical timeline matching JSX         */
/* ───────────────────────────────────────────────────────────── */

function ConditionsChronology({
  timeline,
  conditions,
}: {
  timeline: TimelineEvent[];
  conditions: ConditionItem[];
}) {
  const [open, setOpen] = useState(false);

  // Fallback timeline from conditions if API returns empty
  const displayTimeline = timeline.length > 0
    ? timeline
    : conditions
        .filter(c => c.diagnosed_at)
        .sort((a, b) => (b.diagnosed_at || '').localeCompare(a.diagnosed_at || ''))
        .map(c => ({
          date: c.diagnosed_at!,
          type: 'diagnostic',
          icon: c.icon || '🩺',
          title: `${c.name} diagnosed`,
          detail: c.diagnosis || c.condition_type,
          tag: 'Diagnosis',
        }));

  if (displayTimeline.length === 0) return null;

  return (
    <div style={{
      background: 'white', borderRadius: 16, overflow: 'hidden',
      border: '1.5px solid #8E8E9333',
      boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          padding: '14px 16px', display: 'flex', alignItems: 'center',
          gap: 12, cursor: 'pointer',
        }}
      >
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: '#F7F4F0', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0,
        }}>
          📅
        </div>
        <div className="flex-1">
          <div style={{ fontWeight: 700, fontSize: 15 }}>Management History</div>
          <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>
            Vet visits · diagnostics · treatments · last 2 years
          </div>
        </div>
        <div style={{
          fontSize: 13, color: '#C7C7CC',
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.2s',
        }}>
          ▾
        </div>
      </div>

      {open && (
        <div style={{ borderTop: '1px solid #F0EDE8', padding: '4px 16px 16px' }}>
          {displayTimeline.map((ev, i) => {
            const tagColor = TAG_COLORS[ev.tag] || '#8E8E93';
            return (
              <div key={i} style={{ display: 'flex', gap: 12, paddingTop: 14, position: 'relative' }}>
                {/* Vertical line */}
                {i < displayTimeline.length - 1 && (
                  <div style={{
                    position: 'absolute', left: 15, top: 30, bottom: -14,
                    width: 2, background: '#F0EDE8',
                  }} />
                )}
                {/* Circle */}
                <div style={{
                  width: 30, height: 30, borderRadius: '50%',
                  background: tagColor + '18',
                  border: `2px solid ${tagColor}44`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, flexShrink: 0, zIndex: 1,
                }}>
                  {ev.icon}
                </div>
                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                    <div style={{ fontWeight: 600, fontSize: 13, color: '#1A1A1A' }}>{ev.title}</div>
                    <div style={{
                      background: tagColor + '18', color: tagColor,
                      borderRadius: 20, padding: '1px 7px', fontSize: 10, fontWeight: 700,
                    }}>
                      {ev.tag}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: '#8E8E93', marginBottom: 2 }}>
                    {formatApiDate(ev.date)}
                  </div>
                  {ev.detail && (
                    <div style={{ fontSize: 12, color: '#555', lineHeight: 1.4 }}>{ev.detail}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Complete Health Analysis PDF — 2-column grid, dark button   */
/* ───────────────────────────────────────────────────────────── */

function ConditionsPdfCard({
  petName,
  pdfState,
  onGenerate,
  onReset,
}: {
  petName: string;
  pdfState: 'idle' | 'generating' | 'done';
  onGenerate: () => void;
  onReset: () => void;
}) {
  const pdfItems = [
    { icon: '🩺', label: 'Vet visits & exams' },
    { icon: '🔬', label: 'Diagnostics & imaging' },
    { icon: '💊', label: 'Medications & dosage' },
    { icon: '🦴', label: 'Conditions & diagnosis' },
    { icon: '📅', label: 'Treatment chronology' },
    { icon: '⚖️', label: 'Weight history' },
  ];

  return (
    <div style={{
      background: 'white', borderRadius: 16, padding: 16,
      border: '1.5px solid #1A1A1A22',
      boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
    }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: '#F7F4F0', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0,
        }}>
          📄
        </div>
        <div className="flex-1">
          <div style={{ fontWeight: 700, fontSize: 15 }}>Complete Health Analysis</div>
          <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>
            Download full PDF record for vet or insurance
          </div>
        </div>
      </div>

      {/* 2-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5, marginBottom: 14 }}>
        {pdfItems.map((r) => (
          <div
            key={r.label}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 8px', background: '#F7F4F0', borderRadius: 8,
            }}
          >
            <span style={{ fontSize: 13 }}>{r.icon}</span>
            <span style={{ fontSize: 11, color: '#555', fontWeight: 500 }}>{r.label}</span>
          </div>
        ))}
      </div>

      {pdfState === 'done' ? (
        <div style={{
          background: '#F0FFF4', border: '1px solid #34C75944',
          borderRadius: 12, padding: '12px 14px',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 20 }}>✅</span>
          <div className="flex-1">
            <div style={{ fontWeight: 700, fontSize: 13, color: '#1A6B2A' }}>
              {petName}_Complete_Health.pdf ready
            </div>
            <div style={{ fontSize: 11, color: '#34C759', marginTop: 2 }}>
              Saved to your downloads
            </div>
          </div>
          <button
            onClick={onReset}
            style={{ background: 'none', border: 'none', color: '#AEAEB2', fontSize: 11, cursor: 'pointer', padding: 0 }}
          >
            ↺
          </button>
        </div>
      ) : (
        <button
          onClick={onGenerate}
          disabled={pdfState === 'generating'}
          style={{
            width: '100%',
            background: pdfState === 'generating' ? '#F2EDE8' : '#1A1A1A',
            color: pdfState === 'generating' ? '#D44800' : 'white',
            border: 'none', borderRadius: 12, padding: 12,
            fontSize: 14, fontWeight: 700,
            cursor: pdfState === 'generating' ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all 0.2s',
          }}
        >
          {pdfState === 'generating' ? (
            <>
              <span style={{ animation: 'pulse 1s infinite' }}>⏳</span> Generating…
            </>
          ) : (
            <>📥 Download PDF</>
          )}
        </button>
      )}
    </div>
  );
}
