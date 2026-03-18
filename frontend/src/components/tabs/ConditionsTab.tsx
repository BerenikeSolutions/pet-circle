'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, ConditionItem, TimelineEvent } from '@/lib/api';
import {
  addCondition,
  deleteCondition,
  updateCondition,
  getConditionTimeline,
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
import { formatApiDate } from '@/lib/dashboard-utils';

interface ConditionsTabProps {
  data: DashboardData;
  token: string;
  onCartClick: (itemId?: string) => void;
}

export default function ConditionsTab({ data, token, onCartClick }: ConditionsTabProps) {
  const [addSheet, setAddSheet] = useState(false);
  const [conditionForm, setConditionForm] = useState({
    name: '', diagnosis: '', since: '', notes: '', condition_type: 'chronic',
  });
  const [saving, setSaving] = useState(false);
  const [pdfState, setPdfState] = useState<'idle' | 'generating' | 'done'>('idle');
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [addMedSheet, setAddMedSheet] = useState<string | null>(null);
  const [medForm, setMedForm] = useState({ name: '', dose: '', frequency: '', route: '' });
  const [addMonSheet, setAddMonSheet] = useState<string | null>(null);
  const [monForm, setMonForm] = useState({ name: '', frequency: '' });

  const conditions = data.conditions || [];
  const diagnostics = data.diagnostic_results || [];
  const documents = data.documents || [];
  const contacts = data.contacts || [];
  const hasConditions = conditions.length > 0;
  const hasDiagnostics = diagnostics.length > 0;

  // Group diagnostics by test_type
  const paramsByType = diagnostics.reduce((acc, d) => {
    const key = d.test_type || 'Other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {} as Record<string, typeof diagnostics>);

  // Last vet visit from documents
  const lastVetDate = documents.length > 0
    ? documents.reduce((latest, doc) => {
        if (!doc.uploaded_at) return latest;
        return !latest || doc.uploaded_at > latest ? doc.uploaded_at : latest;
      }, '' as string)
    : null;

  // Vet contact
  const vetContact = contacts.find(c => c.role === 'veterinarian');

  // Fetch timeline
  const loadTimeline = useCallback(async () => {
    try {
      const res = await getConditionTimeline(token);
      setTimeline(res.events || []);
    } catch {
      // Timeline is supplementary, don't block
    }
  }, [token]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

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
      });
      setConditionForm({ name: '', diagnosis: '', since: '', notes: '', condition_type: 'chronic' });
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
    setTimeout(() => setPdfState('done'), 2500);
  };

  // Recommendations based on conditions
  const recommendations = conditions.flatMap(c => {
    const recs: { icon: string; text: string; conditionName: string }[] = [];
    if (c.condition_type === 'chronic') {
      recs.push({ icon: '📋', text: `Regular monitoring for ${c.name}`, conditionName: c.name });
      if (c.medications.length > 0) {
        recs.push({ icon: '💊', text: `Continue ${c.medications[0].name} as prescribed`, conditionName: c.name });
      }
    }
    if (c.monitoring.length > 0) {
      c.monitoring.forEach(m => {
        recs.push({ icon: '🔬', text: `${m.name} — ${m.frequency || 'as needed'}`, conditionName: c.name });
      });
    }
    return recs;
  });

  return (
    <div className="space-y-4">
      {/* Condition Cards */}
      {hasConditions ? (
        conditions.map((condition) => (
          <ConditionCard
            key={condition.id}
            condition={condition}
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
          <div key={type} className="bg-white rounded-2xl shadow-sm border border-blue-100 p-4 space-y-3">
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

      {/* Add Condition */}
      <AddRow label="Add Condition" onClick={() => setAddSheet(true)} />

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
            <span>💡</span> Recommendations
          </h3>
          <div className="space-y-2">
            {recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2 py-1.5 border-b border-gray-50 last:border-0">
                <span className="text-sm mt-0.5">{rec.icon}</span>
                <div>
                  <p className="text-sm text-gray-800">{rec.text}</p>
                  <p className="text-[10px] text-gray-400">{rec.conditionName}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Last Vet Visit */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-2">
          <span>🩺</span> Last Vet Visit
        </h3>
        {lastVetDate ? (
          <div className="space-y-1">
            <p className="text-sm text-gray-800">{formatApiDate(lastVetDate)}</p>
            {vetContact && (
              <div className="mt-2 p-3 bg-gray-50 rounded-xl space-y-1">
                <p className="text-sm font-medium text-gray-900">{vetContact.name}</p>
                {vetContact.clinic_name && (
                  <p className="text-xs text-gray-500">{vetContact.clinic_name}</p>
                )}
                {vetContact.phone && (
                  <p className="text-xs text-gray-500">{vetContact.phone}</p>
                )}
              </div>
            )}
            <p className="text-[11px] text-gray-400 mt-1">Based on most recent document upload</p>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No records available</p>
        )}
      </div>

      {/* Management Chronology — from timeline API */}
      {(timeline.length > 0 || hasConditions) && (
        <CollapsibleCard icon="📅" title="Management History" subtitle="Chronological timeline">
          <div className="p-4">
            <div className="relative pl-6">
              <div className="absolute left-2 top-0 bottom-0 w-0.5 bg-gray-200" />
              {timeline.length > 0 ? (
                timeline.map((event, i) => (
                  <div key={i} className="relative mb-4 last:mb-0">
                    <div className="absolute -left-4 w-4 h-4 bg-white border-2 border-brand rounded-full flex items-center justify-center text-[8px]">
                      {event.icon}
                    </div>
                    <div className="ml-2">
                      <p className="text-[10px] text-gray-400 font-medium">
                        {formatApiDate(event.date)}
                      </p>
                      <p className="text-xs text-gray-800">{event.title}</p>
                      {event.detail && (
                        <p className="text-[11px] text-gray-500">{event.detail}</p>
                      )}
                      <span
                        className="inline-block mt-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                        style={{
                          color: event.tag === 'chronic' ? '#FF9500' : event.tag === 'active' ? '#34C759' : '#8E8E93',
                          backgroundColor: event.tag === 'chronic' ? '#FFF8F0' : event.tag === 'active' ? '#F0FFF4' : '#F5F5F5',
                        }}
                      >
                        {event.tag}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                // Fallback to condition-based timeline
                conditions
                  .filter(c => c.diagnosed_at)
                  .sort((a, b) => (a.diagnosed_at || '').localeCompare(b.diagnosed_at || ''))
                  .map((c) => (
                    <div key={c.id} className="relative mb-4 last:mb-0">
                      <div className="absolute -left-4 w-4 h-4 bg-white border-2 border-brand rounded-full flex items-center justify-center text-[8px]">
                        🩺
                      </div>
                      <div className="ml-2">
                        <p className="text-[10px] text-gray-400 font-medium">
                          {c.diagnosed_at ? formatApiDate(c.diagnosed_at) : ''}
                        </p>
                        <p className="text-xs text-gray-800">
                          {c.name}{c.diagnosis ? ` — ${c.diagnosis}` : ''}
                        </p>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>
        </CollapsibleCard>
      )}

      {/* Complete Health PDF Card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>📄</span> Complete Health Analysis PDF
        </h3>
        {pdfState === 'idle' && (
          <>
            <div className="grid grid-cols-3 gap-2 mb-4">
              {[
                { icon: '💉', label: 'Vaccines' },
                { icon: '🪱', label: 'Deworming' },
                { icon: '🏥', label: 'Conditions' },
                { icon: '🥗', label: 'Nutrition' },
                { icon: '🧴', label: 'Grooming' },
                { icon: '📊', label: 'Diagnostics' },
              ].map((item) => (
                <div key={item.label} className="flex flex-col items-center py-2 px-1 bg-gray-50 rounded-xl">
                  <span className="text-lg mb-1">{item.icon}</span>
                  <span className="text-[10px] text-gray-600 font-medium">{item.label}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Download a comprehensive PDF with all health records, conditions, diagnostics, and care history.
            </p>
            <button
              onClick={handleGeneratePdf}
              className="w-full py-2.5 rounded-xl text-white text-sm font-semibold"
              style={{ background: 'var(--brand-gradient)' }}
            >
              Generate PDF
            </button>
          </>
        )}
        {pdfState === 'generating' && (
          <div className="text-center py-4">
            <div className="inline-block w-8 h-8 border-3 border-brand border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-gray-500 mt-2">Generating PDF...</p>
          </div>
        )}
        {pdfState === 'done' && (
          <div className="text-center py-2">
            <span className="text-2xl mb-1 block">✅</span>
            <p className="text-sm font-semibold text-green-700">PDF Ready!</p>
            <button
              onClick={() => setPdfState('idle')}
              className="mt-2 text-xs text-brand font-semibold"
            >
              Download Again
            </button>
          </div>
        )}
      </div>

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
                value={(medForm as any)[field.key]}
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

function ConditionCard({
  condition,
  onDelete,
  onAddMed,
  onDeleteMed,
  onAddMon,
  onDeleteMon,
  onCartClick,
}: {
  condition: ConditionItem;
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

  const hasActiveMeds = condition.medications.some(m => m.status === 'active');

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-blue-100 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <span>🏥</span> {condition.name}
        </h3>
        <div className="flex items-center gap-2">
          <StatusBadge status={statusMap[condition.condition_type] || 'managed'} label={condition.condition_type} />
          <button
            onClick={onDelete}
            className="text-gray-400 hover:text-red-500 text-xs"
            title="Remove condition"
          >
            ✕
          </button>
        </div>
      </div>

      {condition.diagnosis && (
        <p className="text-xs text-gray-600">{condition.diagnosis}</p>
      )}

      {condition.diagnosed_at && (
        <p className="text-[11px] text-gray-400">Diagnosed: {formatApiDate(condition.diagnosed_at)}</p>
      )}

      {/* Medications */}
      <div className="border-t border-gray-100 pt-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-bold text-gray-400 uppercase">Medications</p>
          <button
            onClick={onAddMed}
            className="text-[10px] font-semibold text-brand"
          >
            + Add
          </button>
        </div>
        {condition.medications.length > 0 ? (
          <div className="space-y-2">
            {condition.medications.map((med) => (
              <MedRow
                key={med.id}
                name={`${med.name}${med.dose ? ` ${med.dose}` : ''}`}
                note={[med.frequency, med.route].filter(Boolean).join(' · ')}
                status={med.status === 'active' ? 'ok' : 'discontinued'}
                onDelete={() => onDeleteMed(med.id)}
                onOrder={() => onCartClick()}
              />
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">No medications added</p>
        )}
      </div>

      {/* Refill status for active medications */}
      {hasActiveMeds && (
        <div className="border-t border-gray-100 pt-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-[11px] text-gray-600">Medications active</span>
            </div>
            <button
              onClick={() => onCartClick()}
              className="text-[11px] font-semibold text-brand"
            >
              Refill Order
            </button>
          </div>
        </div>
      )}

      {/* Monitoring */}
      <div className="border-t border-gray-100 pt-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-bold text-gray-400 uppercase">Monitoring</p>
          <button
            onClick={onAddMon}
            className="text-[10px] font-semibold text-brand"
          >
            + Add
          </button>
        </div>
        {condition.monitoring.length > 0 ? (
          <div className="space-y-2">
            {condition.monitoring.map((mon) => (
              <MonitorRow
                key={mon.id}
                name={mon.name}
                freq={mon.frequency || 'As needed'}
                onDelete={() => onDeleteMon(mon.id)}
              />
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">No monitoring items</p>
        )}
      </div>

      {condition.notes && (
        <div className="border-t border-gray-100 pt-2">
          <p className="text-[11px] text-gray-500">{condition.notes}</p>
        </div>
      )}
    </div>
  );
}

function MedRow({
  name,
  note,
  status,
  onDelete,
  onOrder,
}: {
  name: string;
  note: string;
  status: string;
  onDelete: () => void;
  onOrder: () => void;
}) {
  const [reminderOn, setReminderOn] = useState(true);
  const [freq, setFreq] = useState(1);
  const [unit, setUnit] = useState('month');

  return (
    <div className="py-2">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-900">{name}</p>
          <p className="text-[11px] text-gray-500">{note}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={status === 'ok' ? 'done' : 'urgent'} label={status === 'ok' ? 'Active' : 'Stopped'} />
          <button onClick={onDelete} className="text-gray-300 hover:text-red-500 text-xs" title="Remove">✕</button>
        </div>
      </div>
      <ReminderBar enabled={reminderOn} onToggle={setReminderOn} freq={freq} unit={unit} onFreqChange={(f, u) => { setFreq(f); setUnit(u); }} />
    </div>
  );
}

function MonitorRow({
  name,
  freq,
  onDelete,
}: {
  name: string;
  freq: string;
  onDelete: () => void;
}) {
  const [reminderOn, setReminderOn] = useState(true);

  return (
    <div className="flex items-center justify-between py-1.5">
      <div>
        <p className="text-sm text-gray-800">{name}</p>
        <p className="text-[11px] text-gray-500">{freq}</p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{freq}</span>
        <div
          className="w-10 h-[22px] rounded-full cursor-pointer"
          style={{ backgroundColor: reminderOn ? '#D44800' : '#E5E5EA' }}
          onClick={() => setReminderOn(!reminderOn)}
        >
          <div
            className="w-[18px] h-[18px] bg-white rounded-full shadow mt-[2px] transition-transform"
            style={{ transform: reminderOn ? 'translateX(20px)' : 'translateX(2px)' }}
          />
        </div>
        <button onClick={onDelete} className="text-gray-300 hover:text-red-500 text-xs" title="Remove">✕</button>
      </div>
    </div>
  );
}
