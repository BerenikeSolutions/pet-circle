'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DashboardData, ContactItem, DocumentItem, NutritionAnalysis, NudgeItem } from '@/lib/api';
import { addContact, updateContact, deleteContact, getNutritionAnalysis, getNudges, dismissNudge, uploadDocument, retryExtraction } from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CollapsibleCard from '@/components/ui/CollapsibleCard';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import {
  filterByKeywords, countOverdue, formatApiDate, getStatusForRecord,
  VACCINE_KW, DEWORMING_KW, FLEA_TICK_KW, CHECKUP_KW,
  WA_REMINDER_COLORS, WA_REMINDER_BG, WA_REMINDER_LABELS,
  NUDGE_CATEGORY_ICONS, NUDGE_PRIORITY_COLORS,
} from '@/lib/dashboard-utils';

interface OverviewTabProps {
  data: DashboardData;
  token: string;
  onTabChange: (tab: string) => void;
  onCartClick: (itemId?: string) => void;
  onUpdated?: () => void;
  onRemindersClick?: () => void;
}

const SCORE_LABEL_COLORS: Record<string, { color: string; bg: string }> = {
  Excellent: { color: '#34C759', bg: '#F0FFF4' },
  Good: { color: '#007AFF', bg: '#F0F6FF' },
  Fair: { color: '#FF9500', bg: '#FFF6ED' },
  Poor: { color: '#FF3B30', bg: '#FFF0F0' },
};

const CATEGORY_ICONS: Record<string, string> = {
  vaccines: '💉',
  deworming_flea: '🪱',
  conditions: '🏥',
  nutrition: '🥗',
  grooming: '✂️',
  checkups: '🩺',
};

const ROLE_LABELS: Record<string, string> = {
  veterinarian: 'Vet',
  groomer: 'Groomer',
  trainer: 'Trainer',
  specialist: 'Specialist',
  other: 'Other',
};

const ROLE_API_MAP: Record<string, string> = {
  Vet: 'veterinarian',
  Groomer: 'groomer',
  Trainer: 'trainer',
  Other: 'other',
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const DOC_CATEGORIES = ['Vaccination', 'Prescription', 'Diagnostic'] as const;

const DOC_CATEGORY_ICONS: Record<string, string> = {
  Vaccination: '💉',
  Prescription: '💊',
  Diagnostic: '🔬',
};

const DOC_CATEGORY_COLORS: Record<string, { color: string; bg: string }> = {
  Vaccination: { color: '#007AFF', bg: '#F0F6FF' },
  Prescription: { color: '#FF9500', bg: '#FFF6ED' },
  Diagnostic: { color: '#AF52DE', bg: '#F5F0FF' },
};

function inferDocCategory(doc: DocumentItem): string {
  const cat = (doc.document_category || '').trim();
  if (DOC_CATEGORIES.includes(cat as typeof DOC_CATEGORIES[number])) return cat;
  const name = `${doc.document_name || ''} ${doc.hospital_name || ''}`.toLowerCase();
  if (/(vaccin|rabies|booster|dhpp|fvrcp)/.test(name)) return 'Vaccination';
  if (/(prescription|rx|medicine|medication)/.test(name)) return 'Prescription';
  if (/(blood|cbc|urine|urinalysis|hematology|lab|diagnostic|xray|x-ray)/.test(name)) return 'Diagnostic';
  return 'Other';
}

export default function OverviewTab({ data, token, onTabChange, onCartClick, onUpdated, onRemindersClick }: OverviewTabProps) {
  const [contactSheet, setContactSheet] = useState(false);
  const [editContact, setEditContact] = useState<ContactItem | null>(null);
  const [contactForm, setContactForm] = useState({ type: 'Vet', name: '', clinic: '', phone: '', note: '' });
  const [savingContact, setSavingContact] = useState(false);
  const [nutritionData, setNutritionData] = useState<NutritionAnalysis | null>(null);
  const [nudges, setNudges] = useState<NudgeItem[]>([]);
  const [dismissingNudge, setDismissingNudge] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocumentItem | null>(null);
  const [retryingDoc, setRetryingDoc] = useState<string | null>(null);

  // Fetch nutrition analysis and nudges on mount
  useEffect(() => {
    getNutritionAnalysis(token).then(setNutritionData).catch(() => {});
    getNudges(token).then(setNudges).catch(() => {});
  }, [token]);

  // Lock body scroll when document viewer is open
  useEffect(() => {
    if (!viewingDoc) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setViewingDoc(null); };
    window.addEventListener('keydown', onEsc);
    return () => { document.body.style.overflow = original; window.removeEventListener('keydown', onEsc); };
  }, [viewingDoc]);

  const handleDismissNudge = useCallback(async (nudgeId: string) => {
    setDismissingNudge(nudgeId);
    try {
      await dismissNudge(token, nudgeId);
      setNudges(prev => prev.filter(n => n.id !== nudgeId));
    } catch {
      // ignore
    } finally {
      setDismissingNudge(null);
    }
  }, [token]);

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadDocument(token, file);
      onUpdated?.();
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }, [token, onUpdated]);

  const handleRetryExtraction = useCallback(async (docId: string) => {
    setRetryingDoc(docId);
    try {
      await retryExtraction(token, docId);
      onUpdated?.();
    } catch (err: any) {
      alert(err.message || 'Retry failed');
    } finally {
      setRetryingDoc(null);
    }
  }, [token, onUpdated]);

  // Group documents by category, sorted by event_date (most recent first)
  const allDocs = data.documents || [];
  const groupedDocs: Record<string, DocumentItem[]> = {};
  for (const cat of DOC_CATEGORIES) groupedDocs[cat] = [];
  groupedDocs['Other'] = [];
  for (const doc of allDocs) {
    const cat = inferDocCategory(doc);
    (groupedDocs[cat] || groupedDocs['Other']).push(doc);
  }
  // Sort each category by event_date descending (fallback to uploaded_at)
  for (const cat of Object.keys(groupedDocs)) {
    groupedDocs[cat].sort((a, b) => {
      const da = a.event_date || a.uploaded_at || '';
      const db2 = b.event_date || b.uploaded_at || '';
      return db2.localeCompare(da);
    });
  }
  const activeDocCategories = [...DOC_CATEGORIES, 'Other' as const].filter(c => groupedDocs[c]?.length > 0);

  const contacts = data.contacts || [];
  const hs = data.health_score;
  const labelStyle = SCORE_LABEL_COLORS[hs.label] || SCORE_LABEL_COLORS.Fair;

  const records = data.preventive_records || [];
  const vaccines = filterByKeywords(records, VACCINE_KW);
  const deworming = filterByKeywords(records, DEWORMING_KW);
  const fleaTick = filterByKeywords(records, FLEA_TICK_KW);
  const checkups = filterByKeywords(records, CHECKUP_KW);

  const tiles = [
    { icon: '💉', label: 'Vaccines', items: vaccines, tab: 'medical' },
    { icon: '🪱', label: 'Deworming', items: deworming, tab: 'medical' },
    { icon: '🐛', label: 'Flea & Tick', items: fleaTick, tab: 'medical' },
    { icon: '🪮', label: 'Daily Care', items: records.filter(r => r.circle === 'hygiene'), tab: 'grooming' },
    { icon: '✂️', label: 'Grooming', items: records.filter(r => r.circle === 'hygiene'), tab: 'grooming' },
    { icon: '🩺', label: 'Ann. Checkup', items: checkups, tab: 'medical' },
  ];

  const apiReminders = data.reminders || [];
  const conditions = data.conditions || [];
  const hasConditions = conditions.length > 0;

  const handleSaveContact = useCallback(async () => {
    setSavingContact(true);
    try {
      const body = {
        role: ROLE_API_MAP[contactForm.type] || 'other',
        name: contactForm.name,
        clinic_name: contactForm.clinic || undefined,
        phone: contactForm.phone || undefined,
      };
      if (editContact) {
        await updateContact(token, editContact.id, body);
      } else {
        await addContact(token, body);
      }
      onUpdated?.();
    } catch {
      // Silently fail — user can retry
    } finally {
      setSavingContact(false);
      setContactSheet(false);
      setEditContact(null);
      setContactForm({ type: 'Vet', name: '', clinic: '', phone: '', note: '' });
    }
  }, [contactForm, editContact, token, onUpdated]);

  const handleDeleteContact = useCallback(async (id: string) => {
    try {
      await deleteContact(token, id);
      onUpdated?.();
    } catch {
      // Silently fail
    }
  }, [token, onUpdated]);

  // SVG ring parameters
  const ringSize = 120;
  const strokeWidth = 10;
  const radius = (ringSize - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const scorePct = Math.min(hs.score, 100);
  const dashOffset = circumference - (scorePct / 100) * circumference;

  return (
    <div className="space-y-4">
      {/* Health Score Ring */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center gap-4">
          <div className="relative shrink-0" style={{ width: ringSize, height: ringSize }}>
            <svg width={ringSize} height={ringSize} className="-rotate-90">
              <circle
                cx={ringSize / 2} cy={ringSize / 2} r={radius}
                fill="none" stroke="#F2F2F7" strokeWidth={strokeWidth}
              />
              <circle
                cx={ringSize / 2} cy={ringSize / 2} r={radius}
                fill="none" stroke={labelStyle.color} strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={dashOffset}
                style={{ transition: 'stroke-dashoffset 0.6s ease' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold" style={{ color: labelStyle.color }}>{hs.score}</span>
              <span className="text-[10px] font-semibold text-gray-400">/ 100</span>
            </div>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-xs font-bold px-2 py-0.5 rounded-full"
                style={{ color: labelStyle.color, backgroundColor: labelStyle.bg }}
              >
                {hs.label}
              </span>
            </div>
            <p className="text-xs text-gray-500 mb-2">
              {data.pet.name}&apos;s overall health score based on 6 care categories.
            </p>
            {/* Draggers */}
            {hs.draggers.length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] font-semibold text-red-500">Needs attention:</p>
                {hs.draggers.map((d, i) => (
                  <p key={i} className="text-[10px] text-red-400">
                    {CATEGORY_ICONS[d.category.toLowerCase().replace(/ & /g, '_').replace(/ /g, '_')] || '!'} {d.category} — {d.score}%
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Breakdown bars */}
        <div className="mt-4 space-y-2">
          {hs.breakdown.map((b) => (
            <div key={b.key} className="flex items-center gap-2">
              <span className="text-sm shrink-0">{CATEGORY_ICONS[b.key] || '?'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[11px] font-medium text-gray-700 truncate">{b.category}</span>
                  <span className="text-[10px] text-gray-500 shrink-0">{b.score}% <span className="text-gray-300">({b.weight}%)</span></span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(b.score, 100)}%`,
                      backgroundColor: b.score >= 75 ? '#34C759' : b.score >= 50 ? '#FF9500' : '#FF3B30',
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Action Plan (Nudges) */}
      {nudges.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-500 mb-2">Action Plan</h3>
          <div className="space-y-2">
            {nudges.map((nudge) => {
              const priorityStyle = NUDGE_PRIORITY_COLORS[nudge.priority] || NUDGE_PRIORITY_COLORS.medium;
              const icon = nudge.icon || NUDGE_CATEGORY_ICONS[nudge.category] || '📌';
              return (
                <div
                  key={nudge.id}
                  className="bg-white rounded-xl border border-gray-100 shadow-sm p-3"
                  style={{ borderLeftWidth: 3, borderLeftColor: priorityStyle.color }}
                >
                  <div className="flex items-start gap-2.5">
                    <span className="text-lg shrink-0 mt-0.5">{icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-semibold text-gray-900 truncate">{nudge.title}</span>
                        <span
                          className="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                          style={{ color: priorityStyle.color, backgroundColor: priorityStyle.bg }}
                        >
                          {priorityStyle.label}
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-500 leading-snug">{nudge.message}</p>
                      <div className="flex items-center gap-2 mt-2">
                        {nudge.orderable && (
                          <button
                            onClick={() => onCartClick(nudge.cart_item_id || undefined)}
                            className="text-[11px] font-semibold text-white px-3 py-1 rounded-full"
                            style={{ backgroundColor: '#D44800' }}
                          >
                            Order {nudge.price ? `· ${nudge.price}` : ''}
                          </button>
                        )}
                        {!nudge.mandatory && (
                          <button
                            onClick={() => handleDismissNudge(nudge.id)}
                            disabled={dismissingNudge === nudge.id}
                            className="text-[11px] text-gray-400 hover:text-gray-600"
                          >
                            {dismissingNudge === nudge.id ? 'Dismissing...' : 'Dismiss'}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Care at a Glance */}
      <div>
        <h3 className="text-sm font-semibold text-gray-500 mb-2">Care at a Glance</h3>
        <div className="grid grid-cols-3 gap-2">
          {tiles.map((tile, i) => {
            const overdueCount = countOverdue(tile.items);
            const topItem = tile.items[0];
            const status = topItem ? getStatusForRecord(topItem) : 'missing';
            return (
              <button
                key={i}
                onClick={() => onTabChange(tile.tab)}
                className="bg-white rounded-xl p-3 border border-gray-100 shadow-sm text-center hover:shadow-md transition-shadow flex flex-col items-center"
              >
                <span className="text-xl">{tile.icon}</span>
                <p className="text-[11px] font-medium text-gray-700 mt-1 truncate">{tile.label}</p>
                <StatusBadge status={status} />
                {overdueCount > 0 && (
                  <p className="text-[10px] text-red-500 font-medium mt-1">{overdueCount} overdue</p>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Condition Summary */}
      {hasConditions && (
        <div className="bg-white rounded-2xl shadow-sm border border-blue-100 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">🏥</span>
            <h3 className="font-semibold text-sm">Condition Summary</h3>
          </div>
          {conditions.map((cond) => (
            <div key={cond.id} className="mb-2 last:mb-0">
              <p className="text-xs font-semibold text-gray-800">{cond.name}</p>
              {cond.medications.length > 0 && (
                <p className="text-[11px] text-gray-500">
                  {cond.medications.length} medication{cond.medications.length !== 1 ? 's' : ''}
                  {cond.monitoring.length > 0 && ` · ${cond.monitoring.length} monitoring`}
                </p>
              )}
              {cond.monitoring.length > 0 && (
                <p className="text-[11px] text-gray-400">
                  Next follow-up: {cond.monitoring
                    .filter(m => m.next_due_date)
                    .map(m => formatApiDate(m.next_due_date))
                    .join(', ') || 'Not scheduled'}
                </p>
              )}
            </div>
          ))}
          <button
            onClick={() => onTabChange('conditions')}
            className="mt-2 text-xs text-brand font-semibold"
          >
            View Details →
          </button>
        </div>
      )}

      {/* Order Now CTA */}
      <button
        onClick={() => onCartClick()}
        className="w-full py-3.5 rounded-2xl text-white font-semibold text-sm shadow-sm"
        style={{ background: 'var(--brand-gradient)' }}
      >
        🛒 Order Now — Care Essentials
      </button>

      {/* Nutrition Note — real data or fallback */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <span>🥗</span> Nutrition Note
        </h3>
        {nutritionData ? (
          <>
            <div className="rounded-xl p-3" style={{ backgroundColor: '#FFF6ED', borderLeft: '3px solid #FF9500' }}>
              <p className="text-xs font-semibold text-amber-800 mb-1">Overall Diet</p>
              <p className="text-xs text-amber-700">
                {nutritionData.calories.actual}/{nutritionData.calories.target} kcal/day — {nutritionData.overall_label.toLowerCase()}.
              </p>
              <p className="text-xs text-amber-600 mt-1">
                {(nutritionData as any).diet_summary || (
                  nutritionData.overall_label === 'Good' || nutritionData.overall_label === 'Excellent'
                    ? 'Calorie intake matches daily energy needs, supporting healthy weight maintenance and sustained energy levels.'
                    : nutritionData.calories.actual < nutritionData.calories.target
                      ? 'Calorie intake is below the recommended level, which may lead to energy deficiency, muscle loss, and weakened immunity over time.'
                      : 'Calorie intake exceeds the recommended level, which can contribute to weight gain, joint stress, and increased health risks.'
                )}
              </p>
            </div>
            {nutritionData.improvements.length > 0 && (
              <div className="rounded-xl p-3" style={{ backgroundColor: '#F0F6FF', borderLeft: '3px solid #007AFF' }}>
                <p className="text-xs font-semibold text-blue-800 mb-1">What to Improve</p>
                <ul className="space-y-1">
                  {nutritionData.improvements.slice(0, 3).map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-blue-700">
                      <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: item.dot }} />
                      {item.text}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {nutritionData.recommendation && (
              <div className="rounded-xl p-3" style={{ backgroundColor: '#F0FFF4', borderLeft: '3px solid #34C759' }}>
                <p className="text-xs font-semibold text-green-800 mb-1">Recommendation</p>
                <p className="text-xs text-green-700">{nutritionData.recommendation}</p>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="rounded-xl p-3" style={{ backgroundColor: '#FFF6ED', borderLeft: '3px solid #FF9500' }}>
              <p className="text-xs font-semibold text-amber-800 mb-1">Overall Diet</p>
              <p className="text-xs text-amber-700">Add diet items in the Nutrition tab to see your analysis.</p>
            </div>
            <button
              onClick={() => onTabChange('nutrition')}
              className="text-xs text-brand font-semibold"
            >
              Go to Nutrition →
            </button>
          </>
        )}
      </div>

      {/* WhatsApp Reminders */}
      <CollapsibleCard
        icon="💬"
        title="WhatsApp Reminders"
        subtitle={`${apiReminders.length} scheduled`}
        headerBg="#075E54"
        headerColor="white"
      >
        <div className="p-4 space-y-3">
          {/* Reminder Items */}
          {apiReminders.length > 0 ? (
            apiReminders.map((rem: any, i: number) => {
              const status = rem.status || 'upcoming';
              const color = WA_REMINDER_COLORS[status] || '#FF9500';
              const bg = WA_REMINDER_BG[status] || '#FFF6ED';
              const label = WA_REMINDER_LABELS[status] || 'UPCOMING';
              return (
                <div key={rem.id || i} className="rounded-xl border overflow-hidden" style={{ borderColor: color + '30' }}>
                  <div className="flex items-center justify-between px-3 py-2" style={{ backgroundColor: bg }}>
                    <div className="flex items-center gap-2">
                      <span>{rem.icon || '🔔'}</span>
                      <span className="text-xs font-semibold" style={{ color }}>{rem.title || rem.item_name}</span>
                    </div>
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ color, backgroundColor: color + '20' }}>
                      {label}
                    </span>
                  </div>
                  {rem.body && (
                    <div className="px-3 py-2 bg-white">
                      <p className="text-[11px] text-gray-600">{rem.body}</p>
                      {rem.actions && (
                        <div className="flex gap-2 mt-2">
                          {rem.actions.map((a: any, j: number) => (
                            <button
                              key={j}
                              className="text-[10px] font-semibold px-3 py-1.5 rounded-full text-white"
                              style={{ backgroundColor: a.color }}
                            >
                              {a.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-center py-4">
              <p className="text-xs text-gray-500">No reminders scheduled yet.</p>
              <p className="text-[11px] text-gray-400 mt-1">Reminders will appear here once preventive care records are added.</p>
            </div>
          )}
          {onRemindersClick && (
            <button
              onClick={onRemindersClick}
              className="w-full mt-2 py-2.5 rounded-xl text-xs font-semibold text-white"
              style={{ backgroundColor: '#075E54' }}
            >
              View All Reminders
            </button>
          )}
        </div>
      </CollapsibleCard>

      {/* Documents */}
      <CollapsibleCard
        icon="📁"
        title="Uploaded Documents"
        subtitle={`${allDocs.length} files`}
      >
        <div className="p-4 space-y-4">
          {allDocs.length > 0 ? (
            activeDocCategories.map(cat => {
              const catStyle = DOC_CATEGORY_COLORS[cat] || { color: '#8E8E93', bg: '#F2F2F7' };
              const catIcon = DOC_CATEGORY_ICONS[cat] || '📄';
              return (
                <div key={cat}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{catIcon}</span>
                    <span className="text-xs font-bold" style={{ color: catStyle.color }}>{cat}s</span>
                    <span className="text-[10px] text-gray-400">({groupedDocs[cat].length})</span>
                  </div>
                  <div className="space-y-2">
                    {groupedDocs[cat].map(doc => (
                      <div
                        key={doc.id}
                        className="bg-gray-50 rounded-xl p-3 border border-gray-100"
                        style={{ borderLeftWidth: 3, borderLeftColor: catStyle.color }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <button
                            onClick={() => setViewingDoc(doc)}
                            className="min-w-0 text-left flex-1"
                          >
                            <p className="text-sm font-medium text-gray-900 truncate hover:text-brand transition-colors">
                              {doc.mime_type === 'application/pdf' ? '📄' : '🖼️'} {doc.document_name || 'Uploaded Document'}
                            </p>
                            <p className="text-[11px] text-gray-500 mt-0.5">
                              {doc.event_date ? formatApiDate(doc.event_date) : (doc.uploaded_at ? formatApiDate(doc.uploaded_at) : 'No date')}
                              {doc.doctor_name && ` · Dr. ${doc.doctor_name}`}
                            </p>
                          </button>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                              style={{
                                color: doc.extraction_status === 'success' ? '#34C759' : doc.extraction_status === 'pending' ? '#FF9500' : '#FF3B30',
                                backgroundColor: doc.extraction_status === 'success' ? '#F0FFF4' : doc.extraction_status === 'pending' ? '#FFF6ED' : '#FFF0F0',
                              }}
                            >
                              {doc.extraction_status === 'success' ? '✓' : doc.extraction_status === 'pending' ? '...' : '✗'}
                            </span>
                            {doc.extraction_status === 'failed' && (
                              <button
                                onClick={() => handleRetryExtraction(doc.id)}
                                disabled={retryingDoc === doc.id}
                                className="text-[10px] font-semibold px-2 py-0.5 rounded-full text-white disabled:opacity-50"
                                style={{ backgroundColor: '#FF3B30' }}
                              >
                                {retryingDoc === doc.id ? '...' : 'Retry'}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-center py-4">
              <p className="text-xs text-gray-500">No documents uploaded yet.</p>
              <p className="text-[11px] text-gray-400 mt-1">Upload vaccination cards, prescriptions, or reports via WhatsApp or the button below.</p>
            </div>
          )}
          <label className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-xs font-semibold text-gray-500 block text-center cursor-pointer hover:border-brand hover:text-brand transition-colors">
            {uploading ? 'Uploading...' : '+ Upload Document'}
            <input
              type="file"
              accept="image/jpeg,image/png,application/pdf"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
          </label>
        </div>
      </CollapsibleCard>

      {/* Document Viewer Modal */}
      {viewingDoc && (
        <div
          className="fixed inset-0 z-[100] bg-black/75 backdrop-blur-sm flex flex-col"
          onClick={() => setViewingDoc(null)}
        >
          <div
            className="flex-1 flex flex-col bg-white mx-auto w-full max-w-[430px] safe-area-inset"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
              <p className="text-sm font-semibold text-gray-900 truncate pr-3">
                {viewingDoc.document_name || 'Document'}
              </p>
              <button
                onClick={() => setViewingDoc(null)}
                className="text-xs font-semibold px-3 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-2">
              {viewingDoc.mime_type === 'application/pdf' ? (
                <iframe
                  src={`${API_BASE}/dashboard/${token}/document/${viewingDoc.id}`}
                  className="w-full h-full min-h-[75vh] rounded border"
                  title={viewingDoc.document_name || 'Document'}
                />
              ) : (
                <img
                  src={`${API_BASE}/dashboard/${token}/document/${viewingDoc.id}`}
                  alt={viewingDoc.document_name || 'Document'}
                  className="w-full max-h-[82vh] rounded border object-contain"
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Care Contacts — wired to real API */}
      <CollapsibleCard icon="📞" title="Care Contacts" subtitle={`${contacts.length} saved`}>
        <div className="p-4 space-y-3">
          {contacts.map(c => (
            <div key={c.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-900">{c.name}</p>
                <p className="text-[11px] text-gray-500">
                  {ROLE_LABELS[c.role] || c.role} · {c.clinic_name || 'No clinic'} · {c.phone || 'No phone'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setEditContact(c);
                    const displayRole = Object.entries(ROLE_API_MAP).find(([, v]) => v === c.role)?.[0] || 'Other';
                    setContactForm({ type: displayRole, name: c.name, clinic: c.clinic_name || '', phone: c.phone || '', note: '' });
                    setContactSheet(true);
                  }}
                  className="text-xs text-brand font-semibold"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDeleteContact(c.id)}
                  className="text-xs text-red-500 font-semibold"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
          <AddRow label="Add Contact" onClick={() => {
            setEditContact(null);
            setContactForm({ type: 'Vet', name: '', clinic: '', phone: '', note: '' });
            setContactSheet(true);
          }} />
        </div>
      </CollapsibleCard>

      {/* Contact BottomSheet */}
      <BottomSheet
        open={contactSheet}
        onClose={() => { setContactSheet(false); setEditContact(null); }}
        title={editContact ? 'Edit Contact' : 'Add Contact'}
      >
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-500 mb-1 block">Type</label>
            <div className="flex gap-2">
              {['Vet', 'Groomer', 'Trainer', 'Other'].map(t => (
                <button
                  key={t}
                  onClick={() => setContactForm({ ...contactForm, type: t })}
                  className="px-3 py-1.5 rounded-full text-xs font-semibold border"
                  style={contactForm.type === t
                    ? { backgroundColor: '#D44800', color: 'white', borderColor: '#D44800' }
                    : { borderColor: '#E5E5EA', color: '#666' }
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          {['name', 'clinic', 'phone'].map(field => (
            <div key={field}>
              <label className="text-xs font-semibold text-gray-500 mb-1 block capitalize">{field}</label>
              <input
                type={field === 'phone' ? 'tel' : 'text'}
                value={(contactForm as any)[field]}
                onChange={(e) => setContactForm({ ...contactForm, [field]: e.target.value })}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-brand"
              />
            </div>
          ))}
          <button
            onClick={handleSaveContact}
            disabled={savingContact || !contactForm.name.trim()}
            className="w-full py-3 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {savingContact ? 'Saving...' : editContact ? 'Save Changes' : 'Add Contact'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
