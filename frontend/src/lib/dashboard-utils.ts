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
export const VACCINE_KW = [
  "vaccine",
  "rabies",
  "dhpp",
  "core vaccine",
  "feline core",
  "bordetella",
  "kennel cough",
  "nobivac",
  "coronavirus",
  "ccov",
  "leptospirosis",
  "canine influenza",
  "felv",
  "fiv",
  "puppy booster",
];
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

const MONTH_NAMES: Record<string, number> = {
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
  july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
  jan: 1, feb: 2, mar: 3, apr: 4, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};

export function parseDMY(str: string): Date | null {
  const s = str.trim();
  if (!s) return null;

  // DD/MM/YYYY or DD-MM-YYYY
  const slashDash = s.match(/^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$/);
  if (slashDash) {
    const [, dd, mm, yy] = slashDash.map(Number);
    if (dd >= 1 && dd <= 31 && mm >= 1 && mm <= 12) return new Date(yy, mm - 1, dd);
  }

  // "12 March 2024" or "12 Mar 2024"
  const named = s.match(/^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$/);
  if (named) {
    const d = Number(named[1]);
    const m = MONTH_NAMES[named[2].toLowerCase()];
    const y = Number(named[3]);
    if (d >= 1 && d <= 31 && m) return new Date(y, m - 1, d);
  }

  // ISO: YYYY-MM-DD
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) {
    const [, yy, mm, dd] = iso.map(Number);
    if (dd >= 1 && dd <= 31 && mm >= 1 && mm <= 12) return new Date(yy, mm - 1, dd);
  }

  return null;
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

const CARE_PLAN_DUE_SOON_DAYS = 7;

export function deriveStatus(lastDone: string | null, nextDue: string | null): string {
  if (!lastDone && !nextDue) return 'missing';
  if (!nextDue) return 'done';
  const days = diffDaysFromToday(nextDue);
  if (days === null) return 'missing';
  if (days < 0) return 'overdue';
  if (days <= CARE_PLAN_DUE_SOON_DAYS) return 'upcoming';
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

// ─── Location Helpers ────────────────────────────────────────────

/** Map Indian pincode prefix (3 digits) to city name. */
const PINCODE_CITY_MAP: Record<string, string> = {
  '110': 'Delhi', '111': 'Delhi',
  '201': 'Noida', '202': 'Ghaziabad',
  '122': 'Gurugram', '123': 'Gurugram', '121': 'Faridabad',
  '400': 'Mumbai', '401': 'Mumbai', '402': 'Mumbai',
  '410': 'Navi Mumbai',
  '411': 'Pune', '412': 'Pune', '413': 'Pune', '414': 'Pune',
  '403': 'Goa',
  '560': 'Bengaluru', '561': 'Bengaluru', '562': 'Bengaluru',
  '600': 'Chennai', '601': 'Chennai', '602': 'Chennai', '603': 'Chennai',
  '500': 'Hyderabad', '501': 'Hyderabad', '502': 'Hyderabad', '503': 'Hyderabad',
  '700': 'Kolkata', '711': 'Howrah', '712': 'Hooghly',
  '380': 'Ahmedabad', '382': 'Ahmedabad', '383': 'Ahmedabad',
  '395': 'Surat', '394': 'Surat', '396': 'Surat',
  '641': 'Coimbatore', '642': 'Coimbatore',
  '302': 'Jaipur', '303': 'Jaipur',
  '226': 'Lucknow', '227': 'Lucknow',
  '208': 'Kanpur', '209': 'Kanpur',
  '440': 'Nagpur', '441': 'Nagpur',
  '452': 'Indore', '453': 'Indore',
  '462': 'Bhopal', '463': 'Bhopal',
  '800': 'Patna', '801': 'Patna',
  '682': 'Kochi', '683': 'Kochi', '684': 'Kochi',
  '160': 'Chandigarh',
  '530': 'Visakhapatnam', '531': 'Visakhapatnam',
  '520': 'Vijayawada', '521': 'Vijayawada',
  '625': 'Madurai',
  '620': 'Tiruchirappalli', '621': 'Tiruchirappalli',
  '628': 'Tirunelveli',
  '575': 'Mangalore', '576': 'Mangalore',
  '570': 'Mysuru', '571': 'Mysuru',
  '695': 'Thiruvananthapuram',
  '673': 'Kozhikode',
  '143': 'Amritsar',
  '141': 'Ludhiana', '142': 'Ludhiana',
  '221': 'Varanasi',
  '211': 'Prayagraj',
  '282': 'Agra',
  '248': 'Dehradun',
  '144': 'Jalandhar',
  '324': 'Kota',
  '342': 'Jodhpur',
  '313': 'Udaipur',
  '450': 'Bhopal',
  '492': 'Raipur',
  '360': 'Rajkot',
  '390': 'Vadodara', '391': 'Vadodara',
  '365': 'Bhavnagar',
  '361': 'Jamnagar',
};

/** Derive city name from a 6-digit Indian pincode. Returns null if unknown. */
export function pincodeToCity(pincode: string | null | undefined): string | null {
  if (!pincode || pincode.length < 3) return null;
  const prefix = pincode.slice(0, 3);
  return PINCODE_CITY_MAP[prefix] || null;
}

// ─── Pet Age Helpers ─────────────────────────────────────────────

/** Returns age of pet in days from DOB string. Returns null if DOB is missing/invalid. */
export function ageInDaysFromDob(dob: string | null): number | null {
  if (!dob) return null;
  const birth = new Date(dob);
  if (isNaN(birth.getTime())) return null;
  return Math.floor((Date.now() - birth.getTime()) / 86400000);
}

/**
 * Puppy vaccine names and the minimum dog age (in days) at which they become relevant.
 * Dogs older than 365 days (1 year) should not see any of these.
 */
const PUPPY_VAX_MIN_AGE_DAYS: Record<string, number> = {
  'dhppi 1st dose': 42,   // 6 weeks
  'dhppi 2nd dose': 63,   // 9 weeks
  'dhppi 3rd dose': 84,   // 12 weeks
  'puppy booster':  90,   // show from 3 months as an upcoming item
};

/**
 * Filter vaccines by the dog's age.
 * - For non-dogs: no filtering.
 * - For dogs ≥ 1 year: hide all puppy-dose vaccines.
 * - For dogs < 1 year: show only doses the dog is old enough to receive.
 */
export function filterVaccinesByAge(vaccines: PreventiveRecord[], dob: string | null, species: string): PreventiveRecord[] {
  if (species?.toLowerCase() !== 'dog') return vaccines;
  const ageDays = ageInDaysFromDob(dob);
  if (ageDays === null) return vaccines;
  return vaccines.filter(v => {
    const name = v.item_name.toLowerCase();
    const minAge = PUPPY_VAX_MIN_AGE_DAYS[name];
    if (minAge === undefined) return true;   // not a puppy-specific vaccine — always show
    if (ageDays >= 365) return false;         // dog is over 1 year — hide all puppy doses
    return ageDays >= minAge;                 // show only if dog is old enough for this dose
  });
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
  if (!record.last_done_date) return 'missing';
  return record.status || deriveStatus(record.last_done_date, record.next_due_date);
}


/** Extract the first price from strings like "₹1,499 / ₹4,599" → 1499 */
export function parseFirstPrice(priceStr: string | null | undefined): number {
  if (!priceStr) return 0;
  const m = priceStr.replace(/\s/g, '').match(/[\d,]+/);
  return m ? parseInt(m[0].replace(/,/g, ''), 10) || 0 : 0;
}

export const FREE_DELIVERY_THRESHOLD = 500;
export const DELIVERY_FEE = 49;

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

export function formatFrequency(days: number): string {
  if (days >= 360) return 'Yearly';
  if (days >= 175 && days <= 195) return 'Every 6 months';
  if (days >= 85 && days <= 95) return 'Every 3 months';
  if (days >= 28 && days <= 32) return 'Monthly';
  if (days === 14) return 'Every 2 weeks';
  if (days === 7) return 'Weekly';
  return `Every ${days} days`;
}

export const DASHBOARD_TABS: [string, string][] = [
  ['overview', 'Overview'],
  ['medical', 'Health'],
  ['grooming', 'Hygiene'],
  ['nutrition', 'Nutrition'],
  ['conditions', 'Conditions'],
];

