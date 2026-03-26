'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, PreventiveRecord, WeightEntry, WeightHistoryResponse } from '@/lib/api';
import {
  updatePreventiveDate, updateWeight, updatePreventiveFrequency,
  getWeightHistory, addWeightEntry, updateMedicineName, addToCart,
  updateMonitoringDate,
} from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CareCard from '@/components/ui/CareCard';
import ReminderBar from '@/components/ui/ReminderBar';
import Toggle from '@/components/ui/Toggle';
import VaxFreqModal from '@/components/ui/VaxFreqModal';
import DateEditSheet from '@/components/ui/DateEditSheet';
import Ring from '@/components/ui/Ring';
import {
  filterByKeywords, filterVaccinesByAge, getStatusForRecord, formatApiDate,
  VACCINE_KW, DEWORMING_KW, FLEA_TICK_KW, CHECKUP_KW,
  freqToDays, daysToFreq, VAX_FREQ_LABELS,
} from '@/lib/dashboard-utils';

interface HealthTabProps {
  data: DashboardData;
  token: string;
  onUpdated: () => void;
  onCartClick: (itemId?: string) => void;
}

// ─── Status colour helpers ───────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = {
  done: '#34C759', up_to_date: '#34C759',
  upcoming: '#FF9500',
  overdue: '#FF3B30',
  missing: '#8E8E93',
};
const STATUS_BG: Record<string, string> = {
  done: '#F0FFF4', up_to_date: '#F0FFF4',
  upcoming: '#FFF6ED',
  overdue: '#FFF0F0',
  missing: '#F2F2F7',
};
const STATUS_LABEL: Record<string, string> = {
  done: 'Done', up_to_date: 'Done',
  upcoming: 'Due Soon',
  overdue: 'Overdue',
  missing: 'No Record',
};

function getColor(status: string) { return STATUS_COLOR[status] || '#8E8E93'; }
function getBg(status: string) { return STATUS_BG[status] || '#F2F2F7'; }
function getLabel(status: string) { return STATUS_LABEL[status] || 'No Record'; }

// ─── Monitoring item status ───────────────────────────────────────────────────
function monStatus(nextDue: string | null, lastDone: string | null): string {
  if (!lastDone && !nextDue) return 'missing';
  if (!nextDue) return lastDone ? 'done' : 'missing';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const due = new Date(nextDue);
  if (isNaN(due.getTime())) return 'missing';
  const diff = Math.ceil((due.getTime() - today.getTime()) / 86400000);
  return diff < 0 ? 'overdue' : diff <= 30 ? 'upcoming' : 'done';
}

// ─── VaxRow — must be defined outside HealthTab so React keeps a stable
//     component identity across re-renders (avoids unmount/remount on every
//     parent state change which resets all internal useState values).
interface VaxRowProps {
  vax: PreventiveRecord;
  isOptional: boolean;
  onEditVax: (name: string) => void;
  onFreqChange: (name: string, months: number, unit: string) => void;
}
function VaxRow({ vax, isOptional, onEditVax, onFreqChange }: VaxRowProps) {
  const status = getStatusForRecord(vax);
  const initialFreq = daysToFreq(vax.custom_recurrence_days ?? vax.recurrence_days);
  const [reminderOn, setReminderOn] = useState(true);
  const [freq, setFreq] = useState(initialFreq.freq);
  const [freqUnit, setFreqUnit] = useState(initialFreq.unit);
  const [showVaxFreq, setShowVaxFreq] = useState(false);
  const currentDays = vax.custom_recurrence_days ?? vax.recurrence_days;
  const currentMonths = Math.round(currentDays / 30) || 12;
  const vaxFreqLabel = VAX_FREQ_LABELS[currentMonths] || `Every ${currentMonths} months`;

  return (
    <div className="py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getColor(status) }} />
          <div>
            <p className="text-sm font-medium text-gray-900">{vax.item_name}</p>
            <p className="text-[11px] text-gray-500">
              Given: {formatApiDate(vax.last_done_date)} · Next: {formatApiDate(vax.next_due_date)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={status} />
          <button onClick={() => onEditVax(vax.item_name)} className="text-xs text-brand font-semibold">Edit</button>
        </div>
      </div>
      {isOptional && (
        <div className="mt-1 pl-4 flex items-center justify-between py-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Reminder</span>
            <button
              onClick={() => setShowVaxFreq(true)}
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200"
            >
              {vaxFreqLabel}
            </button>
          </div>
          <Toggle checked={reminderOn} onChange={setReminderOn} />
          <VaxFreqModal
            open={showVaxFreq}
            onClose={() => setShowVaxFreq(false)}
            currentMonths={currentMonths}
            onSave={(months) => { onFreqChange(vax.item_name, months, 'month'); }}
          />
        </div>
      )}
    </div>
  );
}

// ─── BundleSubItem — must be defined outside HealthTab for the same reason.
type SubItemProps = {
  item: {
    key: string;
    name: string;
    source: 'petcircle' | 'vet';
    status: string;
    lastDone: string | null;
    nextDue: string | null;
    note?: string;
    onLog: () => void;
  };
};
function BundleSubItem({ item }: SubItemProps) {
  const [reminderOn, setReminderOn] = useState(true);
  const [rFreq, setRFreq] = useState(1);
  const [rUnit, setRUnit] = useState('month');
  const c = getColor(item.status);
  const bg = getBg(item.status);
  const lbl = getLabel(item.status);
  return (
    <div style={{ borderTop: '1px solid #F0EDE8', padding: '9px 12px 0' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ width: 2, alignSelf: 'stretch', background: c + '44', borderRadius: 2, flexShrink: 0, marginTop: 3, marginLeft: 6 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap', marginBottom: 3 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#1A1A1A' }}>{item.name}</span>
            {item.source === 'petcircle' ? (
              <span style={{ background: '#FFF3EE', color: '#D44800', borderRadius: 20, padding: '1px 7px', fontSize: 9, fontWeight: 700 }}>🐾 PetCircle Recommended</span>
            ) : (
              <span style={{ background: '#F0F6FF', color: '#007AFF', borderRadius: 20, padding: '1px 7px', fontSize: 9, fontWeight: 700 }}>Vet Prescribed</span>
            )}
          </div>
          <div style={{ fontSize: 10.5, color: '#AEAEB2', lineHeight: 1.4, marginBottom: 4 }}>
            {item.lastDone
              ? `Last: ${formatApiDate(item.lastDone)}${item.nextDue ? ' · Next: ' + formatApiDate(item.nextDue) : ''}`
              : (item.note || 'No record')}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ background: bg, color: c, borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>{lbl}</div>
            <button
              onClick={item.onLog}
              style={{ background: '#F2EDE8', border: 'none', borderRadius: 7, padding: '3px 7px', fontSize: 10, color: '#555', cursor: 'pointer', fontWeight: 600 }}
            >
              ✎ Log
            </button>
          </div>
        </div>
      </div>
      <div style={{ marginLeft: 16, marginBottom: 8 }}>
        <ReminderBar
          enabled={reminderOn} onToggle={setReminderOn}
          freq={rFreq} unit={rUnit}
          onFreqChange={(f, u) => { setRFreq(f); setRUnit(u); }}
        />
      </div>
    </div>
  );
}

export default function HealthTab({ data, token, onUpdated, onCartClick }: HealthTabProps) {
  const [editingVax, setEditingVax] = useState<string | null>(null);
  const [editingCheckup, setEditingCheckup] = useState<string | null>(null);
  const [editingMonId, setEditingMonId] = useState<string | null>(null);

  const [weightInput, setWeightInput] = useState('');
  const [weightSaving, setWeightSaving] = useState(false);
  const [weightMsg, setWeightMsg] = useState('');

  const [weightHistory, setWeightHistory] = useState<WeightEntry[]>([]);
  const [idealRange, setIdealRange] = useState<{ min: number; max: number } | null>(null);
  const [weightLoading, setWeightLoading] = useState(true);

  const records = data.preventive_records || [];
  const allVaccines = filterByKeywords(records, VACCINE_KW);
  const vaccines = filterVaccinesByAge(allVaccines, data.pet.dob, data.pet.species);
  const deworming = filterByKeywords(records, DEWORMING_KW);
  const fleaTick = filterByKeywords(records, FLEA_TICK_KW);
  const checkups = filterByKeywords(records, CHECKUP_KW);
  const mandatoryVax = vaccines.filter(v => v.category === 'essential');
  const optionalVax = vaccines.filter(v => v.category !== 'essential');

  const pet = data.pet;

  // ── Base checkup items ────────────────────────────────────────────────────
  const BASE_CHECKUP_NAMES = ['Vet Visit', 'Blood Work'];
  const baseCheckupItems = BASE_CHECKUP_NAMES.map(name => ({
    key: name,
    name,
    source: 'petcircle' as const,
    record: checkups.find(c => c.item_name.toLowerCase().includes(name.toLowerCase())),
  }));

  // ── Infer sample type from monitoring item name ───────────────────────────
  function inferSampleType(name: string): string {
    const n = name.toLowerCase();
    if (n.includes('blood') || n.includes('cbc') || n.includes('panel') || n.includes('chem') ||
        n.includes('hematol') || n.includes('lft') || n.includes('kft') || n.includes('serology') ||
        n.includes('titer') || n.includes('tick')) return 'Blood Draw';
    if (n.includes('urine') || n.includes(' ua') || n.includes('urinalysis') || n.includes('usg') ||
        n.match(/^ua\b/)) return 'Urine Sample';
    if (n.includes('x-ray') || n.includes('xray') || n.includes('ultrasound') ||
        n.includes('imaging') || n.includes('scan') || n.includes('radiograph')) return 'Imaging';
    return 'Vet Visit';
  }

  const SAMPLE_TYPE_META: Record<string, { icon: string; actionLabel: string }> = {
    'Blood Draw':   { icon: '🩸', actionLabel: 'Requires blood sample at lab/clinic' },
    'Urine Sample': { icon: '🧪', actionLabel: 'Requires urine sample collection' },
    'Imaging':      { icon: '📷', actionLabel: 'Requires imaging at clinic' },
    'Vet Visit':    { icon: '🩺', actionLabel: 'Requires in-person vet consultation' },
  };

  // Flat list of all condition monitoring items with sample-type inference
  const allMonItems = (data.conditions || [])
    .filter(cond => cond.is_active && cond.monitoring.length > 0)
    .flatMap(cond => cond.monitoring.map(mon => ({
      key: `${cond.id}_${mon.id}`,
      name: mon.name,
      conditionName: cond.name,
      monitoringItem: mon,
      sampleType: inferSampleType(mon.name),
    })));

  // Group by sample type
  const sampleTypeGroups = allMonItems.reduce<Record<string, typeof allMonItems>>((acc, item) => {
    (acc[item.sampleType] = acc[item.sampleType] || []).push(item);
    return acc;
  }, {});

  // Legacy conditionBundles kept for progress count only
  const conditionBundles = (data.conditions || [])
    .filter(cond => cond.is_active && cond.monitoring.length > 0)
    .flatMap(cond => cond.monitoring.map(mon => ({
      monitoringItem: mon,
    })));

  // ── Progress counts (flat list for total) ────────────────────────────────
  const allCheckupFlat = [
    ...baseCheckupItems.map(item => ({
      isDone: !!(item.record && (item.record.status === 'up_to_date' || item.record.status === 'done')),
    })),
    ...conditionBundles.map(it => ({
      isDone: !!it.monitoringItem.last_done_date,
    })),
  ];
  const totalItems = allCheckupFlat.length;
  const completedItems = allCheckupFlat.filter(i => i.isDone).length;
  const pct = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;
  const barColor = pct === 100 ? '#34C759' : pct >= 50 ? '#FF9500' : '#FF3B30';

  // ── Weight history ─────────────────────────────────────────────────────────
  const loadWeightHistory = useCallback(async () => {
    try {
      const resp: WeightHistoryResponse = await getWeightHistory(token);
      setWeightHistory(resp.entries);
      setIdealRange(resp.ideal_range);
    } catch { /* ignore */ } finally {
      setWeightLoading(false);
    }
  }, [token]);

  useEffect(() => { loadWeightHistory(); }, [loadWeightHistory]);

  const effectiveHistory = weightHistory.length === 0 && pet.weight
    ? [{ id: 'onboarding', weight: pet.weight, recorded_at: new Date().toISOString().split('T')[0], note: 'Onboarding weight' } as WeightEntry]
    : weightHistory;

  const sortedHistory = [...effectiveHistory].sort((a, b) =>
    (a.recorded_at || '').localeCompare(b.recorded_at || ''),
  );
  const chartEntries = sortedHistory.slice(-6);
  const maxWeight = Math.max(...chartEntries.map(w => w.weight), 1);

  // ── Chart math (zayn style, relative baseline) ──────────────────────────
  const chartMin = idealRange ? Math.max(0, idealRange.min - 5) : Math.max(0, maxWeight * 0.85);
  const chartMax = idealRange ? idealRange.max + 5 : maxWeight * 1.1;
  const chartH = 80;
  const barHeightPx = (w: number) => {
    const range = chartMax - chartMin;
    if (range <= 0) return 10;
    return Math.max(6, Math.round(((w - chartMin) / range) * chartH));
  };

  // Ideal range band positioning (top/height in px within chartH)
  const idealBandTop = idealRange
    ? chartH - barHeightPx(Math.min(idealRange.max, chartMax))
    : null;
  const idealBandBottom = idealRange
    ? chartH - barHeightPx(Math.max(idealRange.min, chartMin))
    : null;
  const idealBandHeight = idealBandTop !== null && idealBandBottom !== null
    ? Math.max(0, idealBandBottom - idealBandTop)
    : 0;

  // ── Event handlers ────────────────────────────────────────────────────────
  const handleDateSave = async (itemName: string, dateStr: string) => {
    await updatePreventiveDate(token, itemName, dateStr);
    onUpdated();
  };

  const handleFreqChange = async (itemName: string, freq: number, unit: string) => {
    const days = freqToDays(freq, unit);
    try { await updatePreventiveFrequency(token, itemName, days); onUpdated(); } catch { /* silent */ }
  };

  const handleMedicineSave = async (itemName: string, medicineName: string) => {
    await updateMedicineName(token, itemName, medicineName);
    onUpdated();
  };

  const handleOrderWithMedicine = async (medicineName: string | null | undefined, category: string, fallbackId: string) => {
    if (medicineName) {
      try {
        const productId = `med_${medicineName.toLowerCase().replace(/\s+/g, '_')}`;
        await addToCart(token, {
          product_id: productId, name: medicineName, price: 0,
          icon: category === 'deworming' ? '🪱' : '🐛',
          sub: category === 'deworming' ? 'Deworming medicine' : 'Flea & Tick treatment',
          tag: 'Reorder', tag_color: '#D44800',
        });
        onCartClick(productId);
      } catch { onCartClick(fallbackId); }
    } else { onCartClick(fallbackId); }
  };

  const handleMonitoringLog = async (monId: string, dateStr: string) => {
    try {
      await updateMonitoringDate(token, monId, dateStr);
      onUpdated();
    } catch { /* silent */ }
  };

  const handleWeightSave = async () => {
    const w = parseFloat(weightInput);
    if (!w || w < 0.01 || w > 999.99) {
      setWeightMsg(idealRange
        ? `Expected range for ${pet.breed || pet.species}: ${idealRange.min}–${idealRange.max} kg`
        : `Enter valid weight (0.01–999.99 kg)`);
      return;
    }
    setWeightSaving(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      await addWeightEntry(token, w, today);
      await updateWeight(token, w);
      setWeightMsg('Saved!');
      setWeightInput('');
      loadWeightHistory();
      onUpdated();
    } catch { setWeightMsg('Failed to save'); } finally { setWeightSaving(false); }
  };

  // VaxRow and BundleSubItem are defined above HealthTab (module level)
  // to give them stable identities and prevent remount on every parent re-render.

  // ── Bundle sub-component ──────────────────────────────────────────────────
  const CheckupBundle = ({
    bundleIcon,
    bundleLabel,
    actionLabel,
    items,
  }: {
    bundleIcon: string;
    bundleLabel: string;
    actionLabel: string;
    items: Array<{
      key: string;
      name: string;
      source: 'petcircle' | 'vet';
      status: string;
      lastDone: string | null;
      nextDue: string | null;
      note?: string;
      onLog: () => void;
    }>;
  }) => {
    const bundleDone = items.filter(i => i.status === 'done' || i.status === 'up_to_date').length;
    const bundleTotal = items.length;
    const allDone = bundleDone === bundleTotal;
    const anyDone = bundleDone > 0;
    const bColor = allDone ? '#34C759' : anyDone ? '#FF9500' : '#8E8E93';
    const bBg = allDone ? '#F0FFF4' : anyDone ? '#FFF6ED' : '#F2F2F7';
    const bLbl = allDone ? 'Done' : anyDone ? 'In Progress' : 'No Record';

    return (
      <div style={{ border: `1.5px solid ${bColor}33`, borderRadius: 12, overflow: 'hidden', background: 'white', marginBottom: 10 }}>
        {/* Bundle header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: bBg + '88' }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: bBg, border: `1.5px solid ${bColor}44`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>
            {bundleIcon}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#1A1A1A' }}>{bundleLabel}</div>
            <div style={{ fontSize: 10.5, color: '#8E8E93', marginTop: 1 }}>{actionLabel}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <div style={{ background: bBg, color: bColor, borderRadius: 20, padding: '3px 9px', fontSize: 10, fontWeight: 700 }}>{bLbl}</div>
            {bundleTotal > 1 && (
              <div style={{ background: '#F2F2F7', color: '#8E8E93', borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 600 }}>
                {bundleTotal} items
              </div>
            )}
          </div>
        </div>

        {/* Sub-items */}
        {items.map((item) => (
          <BundleSubItem key={item.key} item={item} />
        ))}
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* ── Vaccinations ───────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
          <span>💉</span> Vaccinations
        </h3>
        {mandatoryVax.length > 0 && (
          <div className="mb-3">
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Mandatory</p>
            {mandatoryVax.map(v => <VaxRow key={v.item_name} vax={v} isOptional={false} onEditVax={setEditingVax} onFreqChange={handleFreqChange} />)}
          </div>
        )}
        {optionalVax.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Optional</p>
            {optionalVax.map(v => <VaxRow key={v.item_name} vax={v} isOptional={true} onEditVax={setEditingVax} onFreqChange={handleFreqChange} />)}
          </div>
        )}
        {vaccines.length === 0 && (
          <p className="text-xs text-gray-400 py-4 text-center">No vaccine records found</p>
        )}
        {vaccines.some(v => getStatusForRecord(v) === 'overdue') && (
          <button
            onClick={() => onCartClick('c1')}
            className="w-full mt-3 py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Book Now
          </button>
        )}
      </div>

      {/* ── Deworming ──────────────────────────────────────────────────────── */}
      {deworming.length > 0 ? deworming.map(d => (
        <CareCard
          key={d.item_name}
          icon="🪱"
          title={d.item_name}
          product={d.medicine_name || undefined}
          lastDone={d.last_done_date}
          nextDue={d.next_due_date}
          status={getStatusForRecord(d)}
          recurrenceDays={d.recurrence_days}
          medicineDependant={d.medicine_dependent}
          medicineName={d.medicine_name}
          onDateSave={(dateStr) => handleDateSave(d.item_name, dateStr)}
          onOrderClick={() => handleOrderWithMedicine(d.medicine_name, 'deworming', 'c2')}
          onFreqChange={(f, u) => handleFreqChange(d.item_name, f, u)}
          onMedicineSave={(name) => handleMedicineSave(d.item_name, name)}
        />
      )) : (
        <CareCard
          icon="🪱" title="Deworming" product="No record found"
          lastDone={null} nextDue={null} status="missing" recurrenceDays={90}
          onDateSave={() => Promise.resolve()} onOrderClick={() => onCartClick('c2')}
        />
      )}

      {/* ── Flea & Tick ────────────────────────────────────────────────────── */}
      {fleaTick.length > 0 ? fleaTick.map(f => (
        <CareCard
          key={f.item_name}
          icon="🐛"
          title={f.item_name}
          product={f.medicine_name || undefined}
          lastDone={f.last_done_date}
          nextDue={f.next_due_date}
          status={getStatusForRecord(f)}
          recurrenceDays={f.recurrence_days}
          medicineDependant={f.medicine_dependent}
          medicineName={f.medicine_name}
          onDateSave={(dateStr) => handleDateSave(f.item_name, dateStr)}
          onOrderClick={() => handleOrderWithMedicine(f.medicine_name, 'flea_tick', 'c5')}
          onFreqChange={(freq, unit) => handleFreqChange(f.item_name, freq, unit)}
          onMedicineSave={(name) => handleMedicineSave(f.item_name, name)}
        />
      )) : (
        <CareCard
          icon="🐛" title="Flea & Tick" product="No record found"
          lastDone={null} nextDue={null} status="missing" recurrenceDays={30}
          onDateSave={() => Promise.resolve()} onOrderClick={() => onCartClick('c5')}
        />
      )}

      {/* ── Preventive Check-up Plan ────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: '#F2F2F7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>🩺</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Preventive Check-up Plan</div>
            <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>
              Personalised · PetCircle recommended + vet prescribed
            </div>
          </div>
          <div style={{
            background: pct === 100 ? '#F0FFF4' : pct === 0 ? '#F2F2F7' : '#FFF6ED',
            color: pct === 100 ? '#34C759' : pct === 0 ? '#8E8E93' : '#FF9500',
            borderRadius: 20, padding: '4px 11px', fontSize: 11, fontWeight: 700,
          }}>
            {pct === 100 ? 'Up to Date' : pct === 0 ? 'No Record' : 'In Progress'}
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#8E8E93', marginBottom: 4 }}>
            <span>{completedItems}/{totalItems} completed</span>
            <span style={{ fontWeight: 700, color: barColor }}>{pct}%</span>
          </div>
          <div style={{ height: 6, borderRadius: 3, background: '#F2F2F7', overflow: 'hidden' }}>
            <div style={{ height: '100%', borderRadius: 3, background: barColor, width: `${pct}%`, transition: 'width 0.5s ease' }} />
          </div>
        </div>

        {/* Vet Visit bundle (PetCircle base items — wellness exam items go here by default) */}
        <CheckupBundle
          bundleIcon="🩺"
          bundleLabel="Vet Visit"
          actionLabel="Annual wellness exam"
          items={[
            ...baseCheckupItems.map(item => {
              const status = item.record ? getStatusForRecord(item.record) : 'missing';
              return {
                key: item.key,
                name: item.name,
                source: 'petcircle' as const,
                status,
                lastDone: item.record?.last_done_date || null,
                nextDue: item.record?.next_due_date || null,
                onLog: () => setEditingCheckup(item.record?.item_name || item.name),
              };
            }),
            // Monitoring items inferred as "Vet Visit" type go in this bundle too
            ...(sampleTypeGroups['Vet Visit'] || []).map(it => {
              const st = monStatus(it.monitoringItem.next_due_date, it.monitoringItem.last_done_date);
              return {
                key: it.key,
                name: `${it.name} (${it.conditionName})`,
                source: 'vet' as const,
                status: st,
                lastDone: it.monitoringItem.last_done_date,
                nextDue: it.monitoringItem.next_due_date,
                onLog: () => setEditingMonId(it.monitoringItem.id),
              };
            }),
          ]}
        />

        {/* Sample-type bundles for vet-prescribed monitoring */}
        {(['Blood Draw', 'Urine Sample', 'Imaging'] as const).map(sType => {
          const groupItems = sampleTypeGroups[sType];
          if (!groupItems || groupItems.length === 0) return null;
          const meta = SAMPLE_TYPE_META[sType];
          return (
            <CheckupBundle
              key={sType}
              bundleIcon={meta.icon}
              bundleLabel={sType}
              actionLabel={meta.actionLabel}
              items={groupItems.map(it => {
                const st = monStatus(it.monitoringItem.next_due_date, it.monitoringItem.last_done_date);
                return {
                  key: it.key,
                  name: `${it.name} (${it.conditionName})`,
                  source: 'vet' as const,
                  status: st,
                  lastDone: it.monitoringItem.last_done_date,
                  nextDue: it.monitoringItem.next_due_date,
                  onLog: () => setEditingMonId(it.monitoringItem.id),
                };
              })}
            />
          );
        })}

      </div>

      {/* ── Weight Log ─────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4"
        style={{ borderColor: '#007AFF33' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: '#F0F6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>⚖️</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Weight Log</div>
            {idealRange && (
              <div style={{ fontSize: 11, color: '#AEAEB2', marginTop: 1 }}>
                Ideal range for {pet.breed}: {idealRange.min}–{idealRange.max} kg
              </div>
            )}
          </div>
          {pet.weight && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 800, fontSize: 20, color: '#1A1A1A', lineHeight: 1 }}>
                {pet.weight} <span style={{ fontSize: 12, fontWeight: 500, color: '#8E8E93' }}>kg</span>
              </div>
              {(() => {
                if (effectiveHistory.length < 2) return null;
                const latest = effectiveHistory[0];
                const prev = effectiveHistory[1];
                if (!latest || !prev) return null;
                const diff = Math.round((latest.weight - prev.weight) * 10) / 10;
                if (diff === 0) return <div style={{ fontSize: 11, fontWeight: 700, color: '#007AFF' }}>→ stable</div>;
                return (
                  <div style={{ fontSize: 11, fontWeight: 700, color: diff > 0 ? '#FF9500' : '#34C759' }}>
                    {diff > 0 ? '↑' : '↓'} {Math.abs(diff)} kg since last
                  </div>
                );
              })()}
            </div>
          )}
        </div>

        {/* Status pill */}
        {pet.weight && idealRange && (
          <div style={{
            background: pet.weight >= idealRange.min && pet.weight <= idealRange.max ? '#F0FFF4' : '#FFF6ED',
            border: `1px solid ${pet.weight >= idealRange.min && pet.weight <= idealRange.max ? '#34C75944' : '#FF950044'}`,
            borderRadius: 8, padding: '6px 10px', marginBottom: 16,
            fontSize: 11, fontWeight: 600,
            color: pet.weight >= idealRange.min && pet.weight <= idealRange.max ? '#1A6B2A' : '#8B5E00',
          }}>
            {pet.weight >= idealRange.min && pet.weight <= idealRange.max
              ? `✅ Weight is within healthy range for ${pet.breed}`
              : pet.weight > idealRange.max
                ? '⚠️ Weight slightly above ideal — monitor closely'
                : '⚠️ Weight slightly below ideal — monitor closely'}
          </div>
        )}

        {/* Bar chart — only when 3+ entries */}
        {effectiveHistory.length >= 3 && (
          <>
            <div style={{ position: 'relative', marginBottom: 4 }}>
              {/* Ideal range band */}
              {idealRange && idealBandTop !== null && idealBandHeight > 0 && (
                <div style={{
                  position: 'absolute', left: 32, right: 0,
                  top: idealBandTop, height: idealBandHeight,
                  background: 'rgba(52,199,89,0.08)',
                  borderTop: '1px dashed #34C75966',
                  borderBottom: '1px dashed #34C75966',
                  pointerEvents: 'none', zIndex: 0,
                }} />
              )}

              {/* Y-axis + bars */}
              <div style={{ display: 'flex', alignItems: 'flex-end', height: chartH, paddingLeft: 32, position: 'relative', zIndex: 1 }}>
                {chartEntries.map((e, i) => {
                  const h = barHeightPx(e.weight);
                  const isLast = i === chartEntries.length - 1;
                  return (
                    <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: isLast ? '#007AFF' : '#8E8E93', marginBottom: 2 }}>{e.weight}</div>
                      <div style={{
                        width: '60%', height: h,
                        borderRadius: '4px 4px 0 0',
                        background: isLast ? '#007AFF' : '#007AFF55',
                        transition: 'height 0.5s ease',
                      }} />
                    </div>
                  );
                })}
              </div>

              {/* Y-axis labels */}
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 28, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                {[chartMax, (chartMax + chartMin) / 2, chartMin].map((v, i) => (
                  <div key={i} style={{ fontSize: 8, color: '#C7C7CC', textAlign: 'right', paddingRight: 4, lineHeight: 1 }}>
                    {Math.round(v)}
                  </div>
                ))}
              </div>

              {/* Baseline */}
              <div style={{ height: 1, background: '#E8E4DF', marginLeft: 32 }} />
            </div>

            {/* X-axis date labels */}
            <div style={{ display: 'flex', paddingLeft: 32, marginBottom: 10 }}>
              {chartEntries.map((e, i) => (
                <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 9, color: '#AEAEB2', marginTop: 3 }}>
                  {e.recorded_at
                    ? new Date(e.recorded_at + 'T00:00:00').toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
                    : ''}
                </div>
              ))}
            </div>

            {/* Ideal range legend */}
            {idealRange && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
                <div style={{ width: 12, height: 8, background: 'rgba(52,199,89,0.15)', border: '1px dashed #34C75966', borderRadius: 2 }} />
                <div style={{ fontSize: 10, color: '#8E8E93' }}>Ideal range: {idealRange.min}–{idealRange.max} kg</div>
              </div>
            )}
          </>
        )}

        {/* Log table — only when 2+ entries */}
        {!weightLoading && effectiveHistory.length >= 2 && (
          <>
            {effectiveHistory.length >= 3 && (
              <div style={{ height: 1, background: '#F0EDE8', marginBottom: 12 }} />
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
              {[...effectiveHistory].reverse().slice(0, 5).map((e, i) => (
                <div key={e.id} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px',
                  background: i === 0 ? '#F0F6FF' : '#FAFAF9',
                  borderRadius: 8,
                  border: i === 0 ? '1px solid #007AFF22' : '1px solid #F0EDE8',
                }}>
                  <div style={{ fontSize: 11, color: '#8E8E93', width: 80, flexShrink: 0, fontWeight: 600 }}>
                    {e.recorded_at ? formatApiDate(e.recorded_at) : '—'}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: '#1A1A1A', flexShrink: 0 }}>{e.weight} kg</div>
                  {e.note && <div style={{ fontSize: 11, color: '#AEAEB2', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.note}</div>}
                  {i === 0 && <div style={{ fontSize: 10, fontWeight: 700, color: '#007AFF', flexShrink: 0 }}>Latest</div>}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Empty state — fewer than 2 entries */}
        {!weightLoading && effectiveHistory.length < 2 && (
          <p className="text-xs text-gray-400 py-3 text-center mb-2">
            {effectiveHistory.length === 0
              ? 'No weight entries yet. Log your first entry below.'
              : 'Log one more weight entry to see history.'}
          </p>
        )}

        {/* Log weight input */}
        <div className="flex gap-2">
          <input
            type="number" step="0.1"
            value={weightInput}
            onChange={(e) => setWeightInput(e.target.value)}
            placeholder="Enter weight (kg)"
            className="flex-1 px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
          />
          <button
            onClick={handleWeightSave}
            disabled={weightSaving}
            className="px-4 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {weightSaving ? '...' : 'Log'}
          </button>
        </div>
        {weightMsg && <p className="text-xs text-gray-500 mt-1">{weightMsg}</p>}
      </div>

      {/* ── Date Edit Sheets ────────────────────────────────────────────────── */}
      {editingVax && (
        <DateEditSheet
          open={!!editingVax}
          onClose={() => setEditingVax(null)}
          title={`Edit ${editingVax}`}
          subtitle="When was this vaccine given?"
          currentDate={vaccines.find(v => v.item_name === editingVax)?.last_done_date || null}
          recurrenceDays={vaccines.find(v => v.item_name === editingVax)?.recurrence_days}
          onSave={(d) => handleDateSave(editingVax, d)}
        />
      )}
      {editingCheckup && (
        <DateEditSheet
          open={!!editingCheckup}
          onClose={() => setEditingCheckup(null)}
          title={`Log ${editingCheckup}`}
          subtitle="When was this last done?"
          currentDate={checkups.find(c => c.item_name.toLowerCase().includes(editingCheckup.toLowerCase()))?.last_done_date || null}
          recurrenceDays={365}
          onSave={(d) => handleDateSave(editingCheckup, d)}
        />
      )}
      {editingMonId && (() => {
        // Find the monitoring item across all monitoring items
        const found = allMonItems.find(it => it.monitoringItem.id === editingMonId);
        const monName = found ? found.name : '';
        return (
          <DateEditSheet
            open={!!editingMonId}
            onClose={() => setEditingMonId(null)}
            title={`Log ${monName}`}
            subtitle="When was this last done?"
            currentDate={null}
            recurrenceDays={180}
            onSave={(d) => handleMonitoringLog(editingMonId, d)}
          />
        );
      })()}
    </div>
  );
}
