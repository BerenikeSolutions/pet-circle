'use client';

import { useState } from 'react';
import type { DashboardData } from '@/lib/api';
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
  const [conditionForm, setConditionForm] = useState({ name: '', diagnosis: '', since: '', notes: '' });
  const [pdfState, setPdfState] = useState<'idle' | 'generating' | 'done'>('idle');

  const diagnostics = data.diagnostic_results || [];
  const documents = data.documents || [];
  const hasDiagnostics = diagnostics.length > 0;

  const paramsByType = diagnostics.reduce((acc, d) => {
    const key = d.test_type || 'Other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {} as Record<string, typeof diagnostics>);

  const lastVetDate = documents.length > 0
    ? documents.reduce((latest, doc) => {
        if (!doc.uploaded_at) return latest;
        return !latest || doc.uploaded_at > latest ? doc.uploaded_at : latest;
      }, '' as string)
    : null;

  const mockTimeline = [
    { date: '10 Sep 2023', event: 'Hip X-Ray — Mild dysplasia confirmed', icon: '🩻' },
    { date: '10 Sep 2023', event: 'Started Meloxicam 1mg daily', icon: '💊' },
    { date: '12 Oct 2023', event: 'Follow-up — Mobility improved', icon: '🩺' },
    { date: '15 Jan 2024', event: 'Added Omega-3 supplement', icon: '🐟' },
    { date: '01 Mar 2024', event: 'Blood work — Liver enzymes normal', icon: '🔬' },
  ];

  const handleGeneratePdf = () => {
    setPdfState('generating');
    setTimeout(() => setPdfState('done'), 2500);
  };

  return (
    <div className="space-y-4">
      {/* Condition Cards */}
      {hasDiagnostics ? (
        Object.entries(paramsByType).map(([type, params]) => (
          <div key={type} className="bg-white rounded-2xl shadow-sm border border-blue-100 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <span>🏥</span> {type}
              </h3>
              <StatusBadge status="managed" />
            </div>

            {/* Parameters */}
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

            {/* Medications section (mocked if diagnostics present) */}
            <div className="border-t border-gray-100 pt-3">
              <p className="text-[10px] font-bold text-gray-400 uppercase mb-2">Medications</p>
              <div className="space-y-2">
                <MedRow name="Meloxicam 1mg" note="Once daily · Anti-inflammatory" status="ok" />
                <MedRow name="Omega-3 Supplement" note="1 capsule daily · Joint support" status="ok" />
              </div>
            </div>

            {/* Monitoring */}
            <div className="border-t border-gray-100 pt-3">
              <p className="text-[10px] font-bold text-gray-400 uppercase mb-2">Monitoring</p>
              <div className="space-y-2">
                <MonitorRow name="Follow-up Vet Visit" freq="Every 6 months" />
                <MonitorRow name="Blood Work" freq="Yearly" />
              </div>
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

      {/* Add Condition */}
      <AddRow label="Add Condition" onClick={() => setAddSheet(true)} />

      {/* Last Vet Visit */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-2">
          <span>🩺</span> Last Vet Visit
        </h3>
        <p className="text-sm text-gray-800">
          {lastVetDate ? formatApiDate(lastVetDate) : 'No records available'}
        </p>
        {lastVetDate && (
          <p className="text-[11px] text-gray-500 mt-0.5">Based on most recent document upload</p>
        )}
      </div>

      {/* Management Chronology */}
      <CollapsibleCard icon="📅" title="Management Chronology" subtitle="Timeline of events">
        <div className="p-4">
          <div className="relative pl-6">
            <div className="absolute left-2 top-0 bottom-0 w-0.5 bg-gray-200" />
            {mockTimeline.map((ev, i) => (
              <div key={i} className="relative mb-4 last:mb-0">
                <div className="absolute -left-4 w-4 h-4 bg-white border-2 border-brand rounded-full flex items-center justify-center text-[8px]">
                  {ev.icon}
                </div>
                <div className="ml-2">
                  <p className="text-[10px] text-gray-400 font-medium">{ev.date}</p>
                  <p className="text-xs text-gray-800">{ev.event}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CollapsibleCard>

      {/* Health PDF Card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>📄</span> Complete Health PDF
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          Generate a comprehensive PDF with all health records, diagnostics, and care history.
        </p>
        {pdfState === 'idle' && (
          <button
            onClick={handleGeneratePdf}
            className="w-full py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Generate PDF
          </button>
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
          {['name', 'diagnosis', 'since', 'notes'].map(field => (
            <div key={field}>
              <label className="text-xs font-semibold text-gray-500 mb-1 block capitalize">
                {field === 'since' ? 'Diagnosed Since' : field}
              </label>
              <input
                type="text"
                value={(conditionForm as any)[field]}
                onChange={(e) => setConditionForm({ ...conditionForm, [field]: e.target.value })}
                placeholder={field === 'since' ? 'DD/MM/YYYY' : ''}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
            </div>
          ))}
          <button
            onClick={() => setAddSheet(false)}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Add Condition
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}

function MedRow({ name, note, status }: { name: string; note: string; status: string }) {
  const [reminderOn, setReminderOn] = useState(true);
  const [freq, setFreq] = useState(1);
  const [unit, setUnit] = useState('month');

  return (
    <div className="py-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">{name}</p>
          <p className="text-[11px] text-gray-500">{note}</p>
        </div>
        <StatusBadge status={status === 'ok' ? 'done' : 'urgent'} label={status === 'ok' ? 'Active' : 'Refill'} />
      </div>
      <ReminderBar enabled={reminderOn} onToggle={setReminderOn} freq={freq} unit={unit} onFreqChange={(f, u) => { setFreq(f); setUnit(u); }} />
    </div>
  );
}

function MonitorRow({ name, freq }: { name: string; freq: string }) {
  const [reminderOn, setReminderOn] = useState(true);

  return (
    <div className="flex items-center justify-between py-1.5">
      <div>
        <p className="text-sm text-gray-800">{name}</p>
        <p className="text-[11px] text-gray-500">{freq}</p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{freq}</span>
        <div className="w-10 h-[22px] rounded-full cursor-pointer" style={{ backgroundColor: reminderOn ? '#D44800' : '#E5E5EA' }} onClick={() => setReminderOn(!reminderOn)}>
          <div className="w-[18px] h-[18px] bg-white rounded-full shadow mt-[2px] transition-transform" style={{ transform: reminderOn ? 'translateX(20px)' : 'translateX(2px)' }} />
        </div>
      </div>
    </div>
  );
}
