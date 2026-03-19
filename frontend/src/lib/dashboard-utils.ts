import type { PreventiveRecord, ReminderItem } from './api';

// ─── Status Config ───────────────────────────────────────────────
export const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  overdue:  { color: '#FF3B30', bg: '#FFF0F0', label: 'Overdue' },
  upcoming: { color: '#FF9500', bg: '#FFF6ED', label: 'Due Soon' },
  done:     { color: '#34C759', bg: '#F0FFF4', label: 'Up to Date' },
  up_to_date: { color: '#34C759', bg: '#F0FFF4', label: 'Up to Date' },
  missing:  { color: '#8E8E93', bg: '#F2F2F7', label: 'No Record' },
  incomplete: { color: '#8E8E93', bg: '#F2F2F7', label: 'No Record' },
  managed:  { color: '#007AFF', bg: '#F0F6FF', label: 'Managed' },
  urgent:   { color: '#FF3B30', bg: '#FFF0F0', label: 'Refill Now' },
  ok:       { color: '#34C759', bg: '#F0FFF4', label: 'Adequate' },
  cancelled: { color: '#8E8E93', bg: '#F2F2F7', label: 'Cancelled' },
};

// ─── Keyword Arrays ──────────────────────────────────────────────
export const VACCINE_KW = ["vaccine", "rabies", "dhpp", "core vaccine", "feline core", "bordetella"];
export const DEWORMING_KW = ["deworming", "deworm"];
export const FLEA_TICK_KW = ["tick", "flea"];
export const CHECKUP_KW = ["checkup", "annual", "wellness", "blood test", "preventive blood"];

// ─── Nudge Constants ─────────────────────────────────────────────
export const NUDGE_CATEGORY_ICONS: Record<string, string> = {
  vaccine: '💉',
  deworming: '💊',
  flea: '🐛',
  condition: '📋',
  nutrition: '🍽️',
  grooming: '✂️',
  checkup: '🩸',
};

export const NUDGE_PRIORITY_COLORS: Record<string, { color: string; bg: string; label: string }> = {
  urgent: { color: '#FF3B30', bg: '#FFF0F0', label: 'Urgent' },
  high:   { color: '#FF9500', bg: '#FFF6ED', label: 'High' },
  medium: { color: '#007AFF', bg: '#F0F6FF', label: 'Medium' },
};

// ─── Date Helpers ────────────────────────────────────────────────
export function formatDMY(date: Date): string {
  const d = String(date.getDate()).padStart(2, '0');
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const y = date.getFullYear();
  return `${d}/${m}/${y}`;
}

export function parseDMY(str: string): Date | null {
  const parts = str.split('/');
  if (parts.length !== 3) return null;
  const [d, m, y] = parts.map(Number);
  if (!d || !m || !y || d < 1 || d > 31 || m < 1 || m > 12) return null;
  return new Date(y, m - 1, d);
}

export function isDateInputValid(str: string): boolean {
  return parseDMY(str) !== null;
}

export function formatApiDate(isoDate: string | null): string {
  if (!isoDate) return '—';
  const d = new Date(isoDate);
  if (isNaN(d.getTime())) return '—';
  return formatDMY(d);
}

export function addMonths(lastDone: string, freqMonths: number): string {
  const d = parseDMY(lastDone);
  if (!d) return '—';
  d.setMonth(d.getMonth() + freqMonths);
  return formatDMY(d);
}

export function addByUnit(last: string, freq: number, unit: string): string {
  const d = parseDMY(last);
  if (!d) return '—';
  switch (unit) {
    case 'day': d.setDate(d.getDate() + freq); break;
    case 'week': d.setDate(d.getDate() + freq * 7); break;
    case 'month': d.setMonth(d.getMonth() + freq); break;
    case 'year': d.setFullYear(d.getFullYear() + freq); break;
  }
  return formatDMY(d);
}

export function diffDaysFromToday(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  if (isNaN(target.getTime())) {
    const parsed = parseDMY(dateStr);
    if (!parsed) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    parsed.setHours(0, 0, 0, 0);
    return Math.round((parsed.getTime() - today.getTime()) / 86400000);
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

export function deriveStatus(lastDone: string | null, nextDue: string | null): string {
  if (!lastDone && !nextDue) return 'missing';
  if (!nextDue) return 'done';
  const days = diffDaysFromToday(nextDue);
  if (days === null) return 'missing';
  if (days < 0) return 'overdue';
  if (days <= 60) return 'upcoming';
  return 'done';
}

/** Convert freq + unit to approximate days for the API. */
export function freqToDays(freq: number, unit: string): number {
  switch (unit) {
    case 'day': return freq;
    case 'week': return freq * 7;
    case 'month': return freq * 30;
    case 'year': return freq * 365;
    default: return freq * 30;
  }
}

/** Convert days to best-fit freq + unit. */
export function daysToFreq(days: number): { freq: number; unit: string } {
  if (days >= 365 && days % 365 === 0) return { freq: days / 365, unit: 'year' };
  if (days >= 30 && days % 30 === 0) return { freq: days / 30, unit: 'month' };
  if (days >= 7 && days % 7 === 0) return { freq: days / 7, unit: 'week' };
  return { freq: days, unit: 'day' };
}

export function freqLabel(freq: number, unit: string): string {
  if (freq === 1 && unit === 'day') return 'Daily';
  if (freq === 1 && unit === 'week') return 'Weekly';
  if (freq === 1 && unit === 'month') return 'Monthly';
  if (freq === 1 && unit === 'year') return 'Yearly';
  return `Every ${freq} ${unit}s`;
}

export function ageFromDob(dob: string | null): string {
  if (!dob) return '—';
  const birth = new Date(dob);
  if (isNaN(birth.getTime())) return '—';
  const now = new Date();
  let years = now.getFullYear() - birth.getFullYear();
  let months = now.getMonth() - birth.getMonth();
  if (months < 0) { years--; months += 12; }
  if (years > 0) return `${years} yr${years > 1 ? 's' : ''}`;
  return `${months} month${months !== 1 ? 's' : ''}`;
}

// ─── Record Helpers ──────────────────────────────────────────────
export function filterByCircle(records: PreventiveRecord[], circle: string): PreventiveRecord[] {
  return records.filter(r => r.circle?.toLowerCase() === circle.toLowerCase());
}

export function filterByKeywords(records: PreventiveRecord[], keywords: string[]): PreventiveRecord[] {
  return records.filter(r =>
    keywords.some(kw => r.item_name.toLowerCase().includes(kw.toLowerCase()))
  );
}

export function countOverdue(records: PreventiveRecord[]): number {
  return records.filter(r => r.status === 'overdue').length;
}

export function getStatusForRecord(record: PreventiveRecord): string {
  if (record.status === 'cancelled') return 'cancelled';
  return record.status || deriveStatus(record.last_done_date, record.next_due_date);
}


export const PAYMENT_METHODS = [
  { id: 'upi', label: 'UPI', icon: '📱', sub: 'Pay via any UPI app' },
  { id: 'card', label: 'Card', icon: '💳', sub: 'Credit / Debit card' },
  { id: 'net', label: 'Net Banking', icon: '🏦', sub: 'All major banks' },
  { id: 'cod', label: 'Cash on Delivery', icon: '💵', sub: 'Pay when delivered' },
];


export const WA_REMINDER_COLORS: Record<string, string> = { upcoming: '#FF9500', due: '#D44800', overdue: '#FF3B30' };
export const WA_REMINDER_BG: Record<string, string> = { upcoming: '#FFF6ED', due: '#FFF3EE', overdue: '#FFF0F0' };
export const WA_REMINDER_LABELS: Record<string, string> = { upcoming: '1 WEEK BEFORE', due: 'DUE TODAY', overdue: 'OVERDUE' };

export const REMINDER_EXPLAINER = [
  ['1 week before', 'UPCOMING reminder with option to pre-order medicine, book home vet, or reorder meds.'],
  ['Due date', 'Due today message sent at 9am with one-tap order or log action.'],
  ['No action taken', 'Overdue follow-up sent every 7 days until the action is logged or completed.'],
  ['Action taken', 'Reminder series stops automatically. Next cycle scheduled based on due date.'],
  ['Condition meds', 'Separate refill reminder series for each chronic medication — never miss a dose.'],
];

export const NET_BANKS = ['HDFC Bank', 'ICICI Bank', 'SBI', 'Axis Bank', 'Kotak Bank', 'Yes Bank'];

export const FREQ_MODAL_UNITS = ['day', 'week', 'month', 'year'];
export const FREQ_MODAL_OPTIONS: Record<string, number[]> = { day: [1, 2, 3], week: [1, 2, 3, 4, 6], month: [1, 2, 3, 6], year: [1] };
export const VAX_FREQ_OPTS = [6, 9, 12, 18, 24];
export const VAX_FREQ_LABELS: Record<number, string> = { 6: 'Every 6 months', 9: 'Every 9 months', 12: 'Yearly', 18: 'Every 18 months', 24: 'Every 2 years' };

export const DASHBOARD_TABS: [string, string][] = [
  ['overview', 'Overview'],
  ['medical', 'Health'],
  ['grooming', 'Hygiene'],
  ['nutrition', 'Nutrition'],
  ['conditions', 'Conditions'],
];

