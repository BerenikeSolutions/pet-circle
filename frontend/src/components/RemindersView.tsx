'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  fetchDashboardFresh,
  getPreventiveMedicineOptions,
  type DashboardData,
  updateMedicineName,
  updatePreventiveDate,
  updatePreventiveFrequency,
} from '@/lib/api';
import { normalizeStatusTag } from '@/components/dashboard/dashboard-utils';

interface RemindersViewProps {
  data: DashboardData;
  token: string;
  onBack: () => void;
  onDashboardDataUpdated?: (nextData: DashboardData) => void;
}

interface ReminderItem {
  id: string;
  backendItemName: string;
  itemName: string;
  section: string;
  recurrenceDays: number;
  freqLabel: string;
  lastISO: string;
  nextISO: string | null;
  status?: string;
  medicineName?: string;
  isMedicineEligible: boolean;
}

interface EditVals {
  freqLabel: string;
  lastISO: string;
  medicineChoice: string;
  customMedicine: string;
  medicineOptions: string[];
  loadingMedicineOptions: boolean;
}

const FREQ_OPTIONS = [
  { label: 'Weekly', days: 7 },
  { label: 'Every 2 weeks', days: 14 },
  { label: 'Monthly', days: 30 },
  { label: 'Every 3 months', days: 90 },
  { label: 'Every 6 months', days: 180 },
  { label: 'Annual', days: 365 },
];

// Keep status windows aligned with care plan dashboard logic.
const CARE_PLAN_DUE_SOON_DAYS = 7;

const MEDICINE_OTHER = 'Other';

function formatISO(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  return d.toISOString().split('T')[0];
}

function displayDate(isoDate: string | null | undefined): string {
  if (!isoDate) return '-';
  const d = new Date(isoDate);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function recurrenceLabel(days: number): string {
  const found = FREQ_OPTIONS.find((f) => f.days === days);
  if (found) return found.label;
  return `Every ${days} days`;
}

function recurrenceDays(label: string, fallback: number): number {
  const found = FREQ_OPTIONS.find((f) => f.label === label);
  if (found?.days) return found.days;
  const dynamicMatch = label.match(/^Every\s+(\d+)\s+days$/i);
  if (dynamicMatch) {
    const parsed = Number.parseInt(dynamicMatch[1], 10);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return fallback;
}

function computeNextISO(lastDoneISO: string, days: number): string | null {
  if (!lastDoneISO || !days) return null;
  const d = new Date(lastDoneISO);
  if (Number.isNaN(d.getTime())) return null;
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

function computeNextDue(lastDoneISO: string, days: number): string {
  const next = computeNextISO(lastDoneISO, days);
  return next ? displayDate(next) : '-';
}

function isMedicineItem(name: string): boolean {
  const n = name.toLowerCase();
  return n.includes('deworm') || n.includes('flea') || n.includes('tick');
}

const _DISPLAY_NAME_MAP: Record<string, string> = {
  'dhppi': 'DHPPi (Nobivac)',
  'rabies vaccine': 'Rabies (Nobivac RL)',
  'tick/flea': 'Flea & Tick Protection',
};

function displayItemName(itemName: string): string {
  const normalized = itemName.trim().toLowerCase();
  if (_DISPLAY_NAME_MAP[normalized]) {
    return _DISPLAY_NAME_MAP[normalized];
  }
  if (normalized.includes('flea') && normalized.includes('tick')) {
    return 'Flea & Tick Protection';
  }
  return itemName;
}

function dateRank(isoDate: string | null | undefined): number {
  if (!isoDate) return Number.MIN_SAFE_INTEGER;
  const ts = new Date(isoDate).getTime();
  return Number.isNaN(ts) ? Number.MIN_SAFE_INTEGER : ts;
}

function toReminderItems(records: DashboardData['preventive_records']): ReminderItem[] {
  const coreRecords = (records || []).filter((r) => !!r.is_core);

  // The backend update endpoints target a preventive item by name and operate
  // on the latest active record. Mirror that here so saved values read back
  // to the exact row users edit.
  const latestByItem = new Map<string, DashboardData['preventive_records'][number]>();
  for (const record of coreRecords) {
    const key = (record.item_name || '').trim().toLowerCase();
    if (!key) continue;

    const existing = latestByItem.get(key);
    if (!existing) {
      latestByItem.set(key, record);
      continue;
    }

    const recordLast = dateRank(record.last_done_date);
    const existingLast = dateRank(existing.last_done_date);
    if (recordLast > existingLast) {
      latestByItem.set(key, record);
      continue;
    }
    if (recordLast < existingLast) {
      continue;
    }

    const recordNext = dateRank(record.next_due_date);
    const existingNext = dateRank(existing.next_due_date);
    if (recordNext > existingNext) {
      latestByItem.set(key, record);
      continue;
    }
    if (recordNext < existingNext) {
      continue;
    }

    const recordCreated = dateRank(record.created_at);
    const existingCreated = dateRank(existing.created_at);
    if (recordCreated > existingCreated) {
      latestByItem.set(key, record);
      continue;
    }
  }

  return Array.from(latestByItem.values())
    .sort((a, b) => {
      const ad = a.next_due_date ? new Date(a.next_due_date).getTime() : Number.MAX_SAFE_INTEGER;
      const bd = b.next_due_date ? new Date(b.next_due_date).getTime() : Number.MAX_SAFE_INTEGER;
      return ad - bd;
    })
    .map((r) => {
      const recurrence = r.custom_recurrence_days || r.recurrence_days;
      return {
        id: r.item_name.toLowerCase(),
        backendItemName: r.item_name,
        itemName: displayItemName(r.item_name),
        section: 'Vaccines & Preventive Care',
        recurrenceDays: recurrence,
        freqLabel: recurrenceLabel(recurrence),
        lastISO: formatISO(r.last_done_date),
        nextISO: formatISO(r.next_due_date) || null,
        status: r.status,
        medicineName: r.medicine_name || undefined,
        isMedicineEligible: isMedicineItem(r.item_name),
      };
    });
}

function mapStatusFromNext(nextISO: string | null, fallback: string, lastISO?: string): string {
  if (!nextISO) {
    // Keep missing last+next aligned with Care Plan "not started" urgency.
    if (!lastISO) return 'overdue';
    return fallback;
  }
  const next = new Date(nextISO);
  if (Number.isNaN(next.getTime())) return fallback;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const ms = next.getTime() - now.getTime();
  const days = Math.floor(ms / 86400000);
  if (days < 0) return 'overdue';
  if (days <= CARE_PLAN_DUE_SOON_DAYS) return 'upcoming';
  return 'up_to_date';
}

const dotClass: Record<string, { bg: string; border: string }> = {
  red: { bg: '#FF3B30', border: '#FF3B30' },
  orange: { bg: '#FF9500', border: '#FF9500' },
  green: { bg: '#34C759', border: '#34C759' },
};

function getStatusDot(status: string | undefined): { bg: string; border: string } {
  const normalized = normalizeStatusTag(status || '');
  if (normalized === 'Urgent') return dotClass.red;
  if (normalized === 'Due soon') return dotClass.orange;
  return dotClass.green;
}

const editFieldStyle: CSSProperties = {
  width: '100%',
  height: 36,
  minHeight: 36,
  fontSize: 13,
  border: '1px solid var(--border, #e0e0e0)',
  borderRadius: 6,
  padding: '6px 8px',
  fontFamily: 'inherit',
  background: 'var(--white, #fff)',
  outline: 'none',
  color: 'var(--t1, #000)',
  boxSizing: 'border-box',
};

const dateFieldStyle: CSSProperties = {
  ...editFieldStyle,
  appearance: 'none',
  WebkitAppearance: 'none',
  lineHeight: '22px',
};

export default function RemindersView({ data, token, onBack, onDashboardDataUpdated }: RemindersViewProps) {
  const baseItems = useMemo<ReminderItem[]>(() => {
    return toReminderItems(data.preventive_records || []);
  }, [data.preventive_records]);

  const [items, setItems] = useState<ReminderItem[]>(baseItems);
  const editRequestIdRef = useRef(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editVals, setEditVals] = useState<EditVals>({
    freqLabel: '',
    lastISO: '',
    medicineChoice: '',
    customMedicine: '',
    medicineOptions: [],
    loadingMedicineOptions: false,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string>('');

  useEffect(() => {
    // Sync from server payload only when the payload itself changes.
    // Do not resync on edit-mode toggle, otherwise freshly saved local values
    // get overwritten by stale props until a full dashboard refresh.
    setItems(baseItems);
  }, [baseItems]);

  const sections = Array.from(new Set(items.map((i) => i.section)));

  const freqOptions = useMemo(() => {
    const labels = FREQ_OPTIONS.map((f) => f.label);
    if (editVals.freqLabel && !labels.includes(editVals.freqLabel)) {
      return [editVals.freqLabel, ...labels];
    }
    return labels;
  }, [editVals.freqLabel]);

  const startEdit = async (item: ReminderItem) => {
    const reqId = ++editRequestIdRef.current;
    setEditingId(item.id);
    setSaveError('');

    let options: string[] = [];
    let medicineChoice = item.medicineName || '';
    let customMedicine = '';

    setEditVals((prev) => ({
      ...prev,
      medicineOptions: [],
      loadingMedicineOptions: item.isMedicineEligible,
    }));

    if (item.isMedicineEligible) {
      try {
        const res = await getPreventiveMedicineOptions(token, item.backendItemName);
        if (editRequestIdRef.current !== reqId) return;
        options = res.options || [];
        console.debug('[RemindersView] medicine options:', { item: item.backendItemName, options });
      } catch (e) {
        if (editRequestIdRef.current !== reqId) return;
        console.warn('[RemindersView] medicine options fetch failed', e);
        options = [];
      }

      // Keep current saved medicine visible/editable even if options API fails or list changed.
      if (item.medicineName && !options.includes(item.medicineName)) {
        medicineChoice = MEDICINE_OTHER;
        customMedicine = item.medicineName;
      }
    }

    if (editRequestIdRef.current !== reqId) return;

    setEditVals({
      freqLabel: item.freqLabel,
      lastISO: item.lastISO,
      medicineChoice,
      customMedicine,
      medicineOptions: options,
      loadingMedicineOptions: false,
    });
  };

  const saveEdit = async (item: ReminderItem) => {
    const nextDays = recurrenceDays(editVals.freqLabel, item.recurrenceDays);
    const selectedMedicine =
      editVals.medicineChoice === MEDICINE_OTHER
        ? editVals.customMedicine.trim()
        : editVals.medicineChoice.trim();

    if (item.isMedicineEligible && editVals.medicineChoice === MEDICINE_OTHER && !selectedMedicine) {
      setSaveError('Please enter medicine name for Other.');
      return;
    }

    setSaveError('');
    setSaving(true);
    const nextISO = computeNextISO(editVals.lastISO, nextDays);

    // Build list of independent update calls to run in parallel.
    const updates: Promise<unknown>[] = [];

    if (nextDays !== item.recurrenceDays) {
      updates.push(updatePreventiveFrequency(token, item.backendItemName, nextDays));
    }

    if (editVals.lastISO && editVals.lastISO !== item.lastISO) {
      updates.push(updatePreventiveDate(token, item.backendItemName, editVals.lastISO));
    }

    if (item.isMedicineEligible && selectedMedicine && selectedMedicine !== (item.medicineName || '')) {
      updates.push(updateMedicineName(token, item.backendItemName, selectedMedicine));
    }

    const optimisticItems = items.map((entry) =>
      entry.id !== item.id
        ? entry
        : {
            ...entry,
            recurrenceDays: nextDays,
            freqLabel: recurrenceLabel(nextDays),
            lastISO: editVals.lastISO || entry.lastISO,
            nextISO,
            status: mapStatusFromNext(nextISO, entry.status || 'upcoming', editVals.lastISO || entry.lastISO),
            medicineName: selectedMedicine || entry.medicineName,
          }
    );

    const patchedData = (): DashboardData => ({
      ...data,
      preventive_records: (data.preventive_records || []).map((r) => {
        if (r.item_name.toLowerCase() !== item.backendItemName.toLowerCase()) return r;
        return {
          ...r,
          last_done_date: editVals.lastISO || r.last_done_date,
          next_due_date: nextISO,
          status: mapStatusFromNext(nextISO, r.status || 'upcoming', editVals.lastISO || formatISO(r.last_done_date)),
          custom_recurrence_days: nextDays !== r.recurrence_days ? nextDays : r.custom_recurrence_days,
          medicine_name: selectedMedicine || r.medicine_name,
        };
      }),
    });

    if (updates.length === 0) {
      // Nothing changed — just close the editor.
      setSaving(false);
      setEditingId(null);
      return;
    }

    // Apply optimistic update and close editor IMMEDIATELY so the UI never
    // buffers on the network round-trip. Reconcile (or surface errors) once
    // the writes settle.
    setItems(optimisticItems);
    setEditingId(null);
    setSaving(false);

    Promise.all(updates)
      .then(() => {
        fetchDashboardFresh(token)
          .then((latest) => {
            setItems(toReminderItems(latest.preventive_records || []));
            onDashboardDataUpdated?.(latest);
          })
          .catch(() => {
            onDashboardDataUpdated?.(patchedData());
          });
      })
      .catch((err: unknown) => {
        onDashboardDataUpdated?.(patchedData());
        setSaveError(
          err instanceof Error
            ? err.message
            : 'Some changes may not have saved. Refresh to confirm.'
        );
      });
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg, #f5f5f5)',
        paddingBottom: 80,
      }}
    >
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--border, #e0e0e0)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--white, #fff)',
        }}
      >
        <button
          onClick={onBack}
          style={{
            width: 34,
            height: 34,
            borderRadius: '50%',
            border: '1.5px solid var(--border, #e0e0e0)',
            background: 'var(--white, #fff)',
            fontSize: 16,
            cursor: 'pointer',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--t1, #111)',
            lineHeight: 1,
          }}
          aria-label="Back"
        >
          &larr;
        </button>
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: 'var(--t1, #000)',
            letterSpacing: '-0.01em',
            lineHeight: 1.1,
          }}
        >
          Care Reminders
        </div>
      </div>

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

      {sections
        .filter((sec) => items.some((i) => i.section === sec))
        .map((sec) => {
          const secItems = items.filter((i) => i.section === sec);
          return (
            <div key={sec} className="card" style={{ margin: '12px' }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: 'var(--t2, #666)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: 12,
                  paddingBottom: 8,
                  borderBottom: '1px solid var(--border, #e0e0e0)',
                }}
              >
                {`💉 ${sec.toUpperCase()}`}
              </div>

              {secItems.map((item) => {
                const effectiveStatus = mapStatusFromNext(item.nextISO, item.status || 'upcoming', item.lastISO);
                const statusDot = getStatusDot(effectiveStatus);
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
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
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

                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: 'var(--t1, #000)',
                            lineHeight: 1.3,
                          }}
                        >
                          {item.itemName}
                        </div>

                        {editingId !== item.id && (
                          <>
                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                                columnGap: 10,
                                rowGap: 4,
                                marginTop: 4,
                                fontSize: 11,
                                color: 'var(--t3, #999)',
                                lineHeight: 1.35,
                              }}
                            >
                              <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                                Freq: <strong style={{ color: 'var(--t2, #666)' }}>{item.freqLabel}</strong>
                              </span>
                              <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                                Last: <strong style={{ color: 'var(--t2, #666)' }}>{displayDate(item.lastISO)}</strong>
                              </span>
                              <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                                Next: <strong style={{ color: 'var(--t2, #666)' }}>{displayDate(item.nextISO)}</strong>
                              </span>
                            </div>

                            {item.isMedicineEligible && (
                              <div
                                style={{
                                  marginTop: 4,
                                  fontSize: 11,
                                  color: 'var(--t3, #999)',
                                  lineHeight: 1.35,
                                }}
                              >
                                Medicine: <strong style={{ color: 'var(--t2, #666)', overflowWrap: 'anywhere' }}>{item.medicineName || '--'}</strong>
                              </div>
                            )}
                          </>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                        {editingId === item.id ? (
                          <button
                            onClick={() => void saveEdit(item)}
                            disabled={saving}
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: '#fff',
                              background: '#34C759',
                              border: 'none',
                              borderRadius: 8,
                              padding: '3px 8px',
                              cursor: saving ? 'not-allowed' : 'pointer',
                              fontFamily: 'inherit',
                              opacity: saving ? 0.7 : 1,
                            }}
                          >
                            {saving ? 'Saving...' : 'Save'}
                          </button>
                        ) : (
                          <button
                            onClick={() => void startEdit(item)}
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

                      </div>
                    </div>

                    {editingId === item.id && (
                      <div
                        style={{
                          marginTop: 10,
                          paddingLeft: 18,
                        }}
                      >
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
                            value={editVals.freqLabel}
                            onChange={(e) => setEditVals((v) => ({ ...v, freqLabel: e.target.value }))}
                            style={{
                              ...editFieldStyle,
                              border: '1.5px solid #FF9500',
                            }}
                          >
                            {freqOptions.map((label) => (
                              <option key={label} value={label}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </div>

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
                            onChange={(e) => setEditVals((v) => ({ ...v, lastISO: e.target.value }))}
                            style={dateFieldStyle}
                          />
                        </div>

                        {item.isMedicineEligible && (
                          <>
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
                                Medicine
                              </div>
                              <select
                                value={editVals.medicineChoice}
                                onChange={(e) => setEditVals((v) => ({ ...v, medicineChoice: e.target.value }))}
                                disabled={editVals.loadingMedicineOptions}
                                style={editFieldStyle}
                              >
                                <option value="">Select medicine</option>
                                {editVals.medicineOptions.map((option) => (
                                  <option key={option} value={option}>
                                    {option}
                                  </option>
                                ))}
                                <option value={MEDICINE_OTHER}>{MEDICINE_OTHER}</option>
                              </select>
                            </div>

                            {editVals.medicineChoice === MEDICINE_OTHER && (
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
                                  Enter medicine name
                                </div>
                                <input
                                  type="text"
                                  value={editVals.customMedicine}
                                  onChange={(e) => setEditVals((v) => ({ ...v, customMedicine: e.target.value }))}
                                  placeholder="Type medicine name"
                                  style={editFieldStyle}
                                />
                              </div>
                            )}
                          </>
                        )}

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
                              color: 'var(--t2, #666)',
                            }}
                          >
                            {computeNextDue(editVals.lastISO, recurrenceDays(editVals.freqLabel, item.recurrenceDays))}
                          </span>
                        </div>

                        {saveError && (
                          <div style={{ marginTop: 8, fontSize: 11, color: '#c0392b' }}>{saveError}</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}

    </div>
  );
}

