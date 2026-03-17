'use client';

import { useState, useEffect } from 'react';
import type { DashboardData } from '@/lib/api';
import StatusBadge from '@/components/ui/StatusBadge';
import CollapsibleCard from '@/components/ui/CollapsibleCard';
import AddRow from '@/components/ui/AddRow';
import BottomSheet from '@/components/ui/BottomSheet';
import {
  filterByKeywords, countOverdue, formatApiDate, getStatusForRecord,
  VACCINE_KW, DEWORMING_KW, FLEA_TICK_KW, CHECKUP_KW,
  MOCK_NUTRITION_DATA, MOCK_WA_REMINDERS, MOCK_DOC_SECTIONS,
  WA_REMINDER_COLORS, WA_REMINDER_BG, WA_REMINDER_LABELS,
  REMINDER_EXPLAINER, STATUS_CONFIG,
} from '@/lib/dashboard-utils';

interface OverviewTabProps {
  data: DashboardData;
  token: string;
  onTabChange: (tab: string) => void;
  onCartClick: (itemId?: string) => void;
}

interface Contact {
  id: string;
  type: string;
  name: string;
  clinic: string;
  phone: string;
  note: string;
}

export default function OverviewTab({ data, token, onTabChange, onCartClick }: OverviewTabProps) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactSheet, setContactSheet] = useState(false);
  const [editContact, setEditContact] = useState<Contact | null>(null);
  const [contactForm, setContactForm] = useState({ type: 'Vet', name: '', clinic: '', phone: '', note: '' });

  useEffect(() => {
    const saved = localStorage.getItem(`petcircle_contacts_${token}`);
    if (saved) setContacts(JSON.parse(saved));
  }, [token]);

  const saveContacts = (list: Contact[]) => {
    setContacts(list);
    localStorage.setItem(`petcircle_contacts_${token}`, JSON.stringify(list));
  };

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
  const hasDiagnostics = (data.diagnostic_results || []).length > 0;

  const handleSaveContact = () => {
    const newContact: Contact = {
      id: editContact?.id || Date.now().toString(),
      ...contactForm,
    };
    if (editContact) {
      saveContacts(contacts.map(c => c.id === editContact.id ? newContact : c));
    } else {
      saveContacts([...contacts, newContact]);
    }
    setContactSheet(false);
    setEditContact(null);
    setContactForm({ type: 'Vet', name: '', clinic: '', phone: '', note: '' });
  };

  return (
    <div className="space-y-4">
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
                className="bg-white rounded-xl p-3 border border-gray-100 shadow-sm text-left hover:shadow-md transition-shadow"
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

      {/* Condition Summary — only if diagnostics exist */}
      {hasDiagnostics && (
        <div className="bg-white rounded-2xl shadow-sm border border-blue-100 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">🏥</span>
            <h3 className="font-semibold text-sm">Condition Summary</h3>
          </div>
          <p className="text-xs text-gray-500">
            {data.diagnostic_results!.length} diagnostic parameter{data.diagnostic_results!.length !== 1 ? 's' : ''} on file.
            Check the Conditions tab for details.
          </p>
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

      {/* Nutrition Note */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <span>🥗</span> Nutrition Note
        </h3>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#FFF6ED', borderLeft: '3px solid #FF9500' }}>
          <p className="text-xs font-semibold text-amber-800 mb-1">Overall Diet</p>
          <p className="text-xs text-amber-700">
            {MOCK_NUTRITION_DATA.calories.current}/{MOCK_NUTRITION_DATA.calories.target} kcal/day — slightly below target.
          </p>
        </div>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#F0F6FF', borderLeft: '3px solid #007AFF' }}>
          <p className="text-xs font-semibold text-blue-800 mb-1">What to Improve</p>
          <ul className="space-y-1">
            {MOCK_NUTRITION_DATA.improve.slice(0, 3).map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-blue-700">
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: item.dot }} />
                {item.text}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl p-3" style={{ backgroundColor: '#F0FFF4', borderLeft: '3px solid #34C759' }}>
          <p className="text-xs font-semibold text-green-800 mb-1">Recommendation</p>
          <p className="text-xs text-green-700">Consider adding joint supplements and increasing protein intake.</p>
        </div>
      </div>

      {/* WhatsApp Reminders */}
      <CollapsibleCard
        icon="💬"
        title="WhatsApp Reminders"
        subtitle={`${apiReminders.length || MOCK_WA_REMINDERS.length} scheduled`}
        headerBg="#075E54"
        headerColor="white"
      >
        <div className="p-4 space-y-3">
          {/* Explainer */}
          <div className="bg-gray-50 rounded-xl p-3 space-y-2">
            <p className="text-xs font-semibold text-gray-700">How reminders work:</p>
            {REMINDER_EXPLAINER.map(([step, desc], i) => (
              <div key={i} className="flex gap-2 text-[11px]">
                <span className="font-semibold text-gray-600 shrink-0">{step}:</span>
                <span className="text-gray-500">{desc}</span>
              </div>
            ))}
          </div>
          {/* Reminder Items */}
          {(apiReminders.length > 0 ? apiReminders : MOCK_WA_REMINDERS).map((rem: any, i: number) => {
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
          })}
        </div>
      </CollapsibleCard>

      {/* Documents */}
      <CollapsibleCard
        icon="📁"
        title="Uploaded Documents"
        subtitle={`${(data.documents || []).length} files`}
      >
        <div className="p-4 space-y-3">
          {(data.documents && data.documents.length > 0) ? (
            data.documents.map((doc, i) => (
              <div key={doc.id || i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{doc.document_name}</p>
                  <p className="text-[11px] text-gray-500">
                    {doc.document_category || 'Uncategorized'} · {formatApiDate(doc.uploaded_at)}
                  </p>
                </div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{
                    color: doc.extraction_status === 'success' ? '#34C759' : doc.extraction_status === 'pending' ? '#FF9500' : '#FF3B30',
                    backgroundColor: doc.extraction_status === 'success' ? '#F0FFF4' : doc.extraction_status === 'pending' ? '#FFF6ED' : '#FFF0F0',
                  }}
                >
                  {doc.extraction_status === 'success' ? 'Parsed ✓' : doc.extraction_status === 'pending' ? 'Processing' : 'Failed'}
                </span>
              </div>
            ))
          ) : (
            MOCK_DOC_SECTIONS.map(section => (
              <div key={section.id} className="space-y-2">
                <div className="flex items-center gap-2">
                  <span>{section.icon}</span>
                  <span className="text-xs font-semibold" style={{ color: section.color }}>{section.label}</span>
                </div>
                {section.files.map((f, j) => (
                  <div key={j} className="pl-7 py-1.5">
                    <p className="text-xs text-gray-800">{f.parsed}</p>
                    <p className="text-[10px] text-gray-500">{f.note}</p>
                  </div>
                ))}
              </div>
            ))
          )}
          <button className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-xs font-semibold text-gray-500">
            + Upload Document
          </button>
        </div>
      </CollapsibleCard>

      {/* Care Contacts */}
      <CollapsibleCard icon="📞" title="Care Contacts" subtitle={`${contacts.length} saved`}>
        <div className="p-4 space-y-3">
          {contacts.map(c => (
            <div key={c.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-900">{c.name}</p>
                <p className="text-[11px] text-gray-500">{c.type} · {c.clinic || 'No clinic'} · {c.phone}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setEditContact(c);
                    setContactForm({ type: c.type, name: c.name, clinic: c.clinic, phone: c.phone, note: c.note });
                    setContactSheet(true);
                  }}
                  className="text-xs text-brand font-semibold"
                >
                  Edit
                </button>
                <button
                  onClick={() => saveContacts(contacts.filter(x => x.id !== c.id))}
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
          {['name', 'clinic', 'phone', 'note'].map(field => (
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
            className="w-full py-3 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'var(--brand-gradient)' }}
          >
            {editContact ? 'Save Changes' : 'Add Contact'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
