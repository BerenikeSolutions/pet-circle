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

// ─── Mock Data Factories ─────────────────────────────────────────
export function buildMockWeightHistory(currentWeight: number | null, dob: string | null): Array<{ date: string; weight: number }> {
  if (!currentWeight) return [];
  const entries: Array<{ date: string; weight: number }> = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now);
    d.setMonth(d.getMonth() - i);
    const variation = (Math.random() - 0.5) * 2;
    const w = Math.max(1, currentWeight + variation - (i * 0.3));
    entries.push({ date: formatDMY(d), weight: Math.round(w * 10) / 10 });
  }
  entries.push({ date: formatDMY(now), weight: currentWeight });
  return entries;
}

export const MOCK_NUTRITION_DATA = {
  calories: { current: 1150, target: 1350, unit: 'kcal/day' },
  macros: [
    { name: 'Protein', icon: '🥩', actual: 28, target: 30, unit: '%', status: 'low', note: 'Slightly below optimal.' },
    { name: 'Fat', icon: '🧈', actual: 14, target: 14, unit: '%', status: 'ok', note: 'Within healthy range.' },
    { name: 'Carbohydrates', icon: '🌾', actual: 46, target: 40, unit: '%', status: 'high', note: 'Slightly elevated.' },
    { name: 'Fibre', icon: '🥦', actual: 3, target: 4, unit: '%', status: 'low', note: 'Could be improved.' },
    { name: 'Moisture', icon: '💧', actual: 10, target: 10, unit: '%', status: 'ok', note: 'Normal for dry kibble.' },
  ],
  vitamins: [
    { name: 'Vitamin E', status: 'Low', supplement: 'Vit E 400 IU', price: '₹349/mo', priority: 'high' },
    { name: 'Vitamin D', status: 'Low', supplement: 'Calcitriol 0.25mcg', price: '₹299/mo', priority: 'medium' },
    { name: 'Vitamin B12', status: 'Adequate', supplement: null, price: null, priority: 'ok' },
    { name: 'Vitamin C', status: 'Adequate', supplement: null, price: null, priority: 'ok' },
  ],
  minerals: [
    { name: 'Glucosamine', icon: '🦴', status: 'Missing', priority: 'urgent', reason: 'Essential for cartilage repair.', supplement: 'Cosequin DS Chewable', price: '₹799/mo' },
    { name: 'Calcium', icon: '🥛', status: 'Adequate', priority: 'ok', reason: 'Supplement in use.', supplement: null, price: null },
    { name: 'Zinc', icon: '⚡', status: 'Adequate', priority: 'ok', reason: 'Sufficient zinc from food.', supplement: null, price: null },
    { name: 'Iron', icon: '🔩', status: 'Adequate', priority: 'ok', reason: 'Adequate from kibble.', supplement: null, price: null },
  ],
  others: [
    { name: 'Omega-3', icon: '🐟', status: 'Adequate', priority: 'ok', reason: 'Supplement in use.', supplement: null, price: null },
    { name: 'Probiotics', icon: '🦠', status: 'Low', priority: 'medium', reason: 'Goldens are digestive-sensitive.', supplement: 'FortiFlora Probiotic', price: '₹649/mo' },
  ],
  improve: [
    { dot: '#FF3B30', text: 'Glucosamine missing → critical for hip joint support' },
    { dot: '#FF9500', text: 'Vitamin E & D low → immunity & bone density' },
    { dot: '#FF9500', text: 'Protein slightly low → muscle recovery & energy' },
    { dot: '#FF9500', text: 'Calories below target → increase daily portions' },
    { dot: '#FFCC00', text: 'Probiotics low → gut health & coat quality' },
  ],
};

export const MOCK_DAILY_HYGIENE = [
  { id: 'coat-brush', icon: '🪮', name: 'Coat Brushing', note: 'Prevents matting & reduces shedding.', lastDone: 'Today', status: 'done' },
  { id: 'teeth-brush', icon: '🦷', name: 'Teeth Brushing', note: 'Daily brushing prevents plaque.', lastDone: '2 days ago', status: 'overdue' },
  { id: 'ear-clean', icon: '👂', name: 'Ear Cleaning', note: 'Floppy ears trap moisture.', lastDone: '10/01/2024', status: 'upcoming' },
  { id: 'eye-wipe', icon: '👁️', name: 'Eye Wipe', note: 'Prevents tear stain buildup.', lastDone: '01/02/2024', status: 'upcoming' },
];

export const MOCK_PERIODIC_HYGIENE = [
  { id: 'bath-nail', icon: '🛁', name: 'Bath, brush & nail trim', note: 'Monthly baths manage shedding.', lastDone: '10/01/2024', status: 'overdue' },
  { id: 'anal-gland', icon: '🐾', name: 'Anal gland cleaning', note: 'Prevents impaction.', lastDone: 'Not recorded', status: 'upcoming' },
];

export const MOCK_CART_ITEMS = [
  { id: 'c1', icon: '🏠', name: 'Home Vet Visit', sub: 'Vaccination — DHPPiL + Rabies boosters', price: 499, tag: 'OVERDUE', tagColor: '#FF3B30', inCart: true },
  { id: 'c2', icon: '🪱', name: 'Bayer Drontal Plus', sub: 'Deworming — overdue since Apr 2024', price: 189, tag: 'OVERDUE', tagColor: '#FF3B30', inCart: true },
  { id: 'c3', icon: '🫙', name: 'Zesty Paws Omega-3', sub: 'Joint supplement — hip dysplasia refill', price: 349, tag: 'CRITICAL REFILL', tagColor: '#FF3B30', inCart: true },
  { id: 'c4', icon: '🦴', name: 'Nutramax Cosequin DS', sub: 'Joint supplement — glucosamine missing', price: 799, tag: 'MISSING', tagColor: '#FF3B30', inCart: true },
  { id: 'c5', icon: '🐛', name: 'Boehringer NexGard', sub: 'Flea & tick protection — no record found', price: 420, tag: 'NO RECORD', tagColor: '#FF9500', inCart: true },
  { id: 'c6', icon: '🌿', name: 'Vit E 400 IU Softgel', sub: 'Antioxidant — breed gap for Goldens', price: 349, tag: 'HIGH PRIORITY', tagColor: '#FF9500', inCart: false },
  { id: 'c7', icon: '🛁', name: 'Full Grooming Session', sub: 'Bath, brush & nail trim', price: 799, tag: 'OVERDUE', tagColor: '#FF9500', inCart: false },
  { id: 'c8', icon: '✂️', name: 'Home Grooming — Nail Trim', sub: 'Nail care — affects gait & joints', price: 299, tag: 'OVERDUE', tagColor: '#FF9500', inCart: false },
  { id: 'c9', icon: '💉', name: 'Kennel Cough Vaccine', sub: 'Vaccination — recommended for park/boarding', price: 349, tag: 'NOT GIVEN', tagColor: '#FF9500', inCart: false },
  { id: 'c10', icon: '💉', name: 'CCoV (Covid) Vaccine', sub: 'Vaccination — optional, no record found', price: 349, tag: 'NOT GIVEN', tagColor: '#FF9500', inCart: false },
  { id: 'c11', icon: '🦠', name: 'Purina FortiFlora Probiotic', sub: 'Gut health — breed recommendation', price: 649, tag: 'BREED REC', tagColor: '#007AFF', inCart: false },
  { id: 'c12', icon: '☀️', name: 'Sun Pharma Calcitriol', sub: 'Vitamin D — bone density, hip support', price: 299, tag: 'LOW', tagColor: '#B8860B', inCart: false },
  { id: 'c13', icon: '🥣', name: 'Royal Canin GR Adult', sub: 'Main food — breed-specific kibble reorder', price: 2499, tag: 'REORDER', tagColor: '#34C759', inCart: false },
  { id: 'c14', icon: '🩺', name: 'Home Vet — Wellness Exam', sub: 'Annual checkup — due Mar 2025', price: 799, tag: 'UPCOMING', tagColor: '#007AFF', inCart: false },
];

export const PAYMENT_METHODS = [
  { id: 'upi', label: 'UPI', icon: '📱', sub: 'Pay via any UPI app' },
  { id: 'card', label: 'Card', icon: '💳', sub: 'Credit / Debit card' },
  { id: 'net', label: 'Net Banking', icon: '🏦', sub: 'All major banks' },
  { id: 'cod', label: 'Cash on Delivery', icon: '💵', sub: 'Pay when delivered' },
];

export const MOCK_WA_REMINDERS = [
  { id: 'r1', type: 'deworming', daysOut: 7, status: 'upcoming', icon: '🪱', title: "Bruno's deworming is due in 1 week", body: "Hi Priya 🐾 Bruno's deworming is due on 01 Apr...", actions: [{ label: '🛒 Order Medicine — ₹189', color: '#25D366' }, { label: '📍 Find Vet Nearby', color: '#075E54' }] },
  { id: 'r2', type: 'vaccine', daysOut: 7, status: 'upcoming', icon: '💉', title: "Bruno's Rabies booster due in 1 week", body: "Hi Priya 🐾 Bruno's Rabies booster is due 20 Jun 2025...", actions: [{ label: '🏠 Book Home Vet — ₹499', color: '#25D366' }, { label: '📍 Find Clinic Nearby', color: '#075E54' }] },
  { id: 'r3', type: 'supplement', daysOut: 7, status: 'upcoming', icon: '💊', title: 'Meloxicam refill due in 1 week', body: "Hi Priya 🐾 Bruno's Meloxicam refill is due 01 Apr...", actions: [{ label: '🔄 Reorder Meloxicam — ₹280', color: '#25D366' }, { label: '⏭ Remind Later', color: '#8E8E93' }] },
  { id: 'r4', type: 'deworming', daysOut: 0, status: 'due', icon: '🪱', title: "Bruno's deworming is due TODAY", body: "Priya, today is the day for Bruno's deworming 🐾...", actions: [{ label: '🛒 Order Now — ₹189', color: '#FF9500' }, { label: '✅ Already Done — Log It', color: '#34C759' }] },
  { id: 'r5', type: 'deworming', daysOut: -7, status: 'overdue', icon: '🚨', title: "🚨 Bruno's deworming is 1 week overdue", body: "Priya, Bruno's deworming was due Apr 1 and is now a week overdue...", actions: [{ label: '🛒 Order Now — ₹189', color: '#FF3B30' }, { label: '✅ Already Done — Log It', color: '#34C759' }] },
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

export const NUDGE_CART_MAP: Record<number, string> = { 1: 'c2', 2: 'c1', 3: 'c3', 4: 'c4', 5: 'c5', 6: 'c6', 7: 'c7', 8: 'c8', 9: 'c11', 10: 'c9' };
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

export const MOCK_DOC_SECTIONS = [
  { id: 'vaccination', icon: '💉', label: 'Vaccination Card', color: '#34C759', bg: '#F0FFF4', files: [
    { name: 'vaccine_card.jpg', parsed: 'Rabies · 20 Jun 2023', note: 'Next due: 20 Jun 2024', status: 'Parsed ✓' },
    { name: 'vaccine_card.jpg', parsed: '9-in-1 (DHPPiL+) · 12 Jun 2023', note: 'Next due: 12 Jun 2024', status: 'Parsed ✓' },
  ]},
  { id: 'prescriptions', icon: '📋', label: 'Prescriptions', color: '#007AFF', bg: '#F0F6FF', files: [
    { name: 'hip_xray_report.jpg', parsed: 'Meloxicam 1mg — once daily', note: 'Hip dysplasia management', status: 'Parsed ✓' },
    { name: 'hip_xray_report.jpg', parsed: 'Omega-3 Supplement — 1 capsule daily', note: 'Joint inflammation support', status: 'Parsed ✓' },
  ]},
  { id: 'reports', icon: '🔬', label: 'Reports', color: '#FF9500', bg: '#FFF6ED', files: [
    { name: 'hip_xray_report.jpg', parsed: 'Hip X-Ray — Mild dysplasia confirmed', note: 'Dr. Meera Nair · 10 Sep 2023', status: 'Parsed ✓' },
    { name: 'deworming_record.jpg', parsed: 'Deworming record · Last done 01 Jan 2024', note: 'Next due: 01 Apr 2024', status: 'Parsed ✓' },
  ]},
];
