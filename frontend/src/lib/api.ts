/**
 * PetCircle — Backend API Client
 *
 * All backend API calls go through this module.
 * Base URL is set via NEXT_PUBLIC_API_URL environment variable.
 */

import { DASHBOARD_CACHE_PREFIX } from "@/lib/branding";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Dashboard Types (match backend response shapes) ---

export interface PetProfile {
  name: string;
  species: string;
  breed: string;
  gender: string;
  dob: string | null;
  weight: number | null;
  weight_flagged: boolean;
  neutered: boolean;
  photo_url: string | null;
}

export interface OwnerInfo {
  full_name: string | null;
  pincode: string | null;
  mobile_display: string | null;
  delivery_address: string | null;
  payment_method_pref: "cod" | "upi" | "card" | null;
  saved_upi_id: string | null;
}

export interface PreventiveRecord {
  item_name: string;
  category: string;
  circle: string;
  last_done_date: string | null;
  next_due_date: string | null;
  status: string;
  recurrence_days: number;
  custom_recurrence_days: number | null;
  medicine_dependent?: boolean;
  medicine_name?: string | null;
  created_at?: string | null;
  is_core?: boolean;
}

export interface WeightEntry {
  id: string;
  weight: number;
  recorded_at: string | null;
  note: string | null;
}

export interface WeightHistoryResponse {
  entries: WeightEntry[];
  ideal_range: { min: number; max: number };
}

export interface ReminderItem {
  item_name: string;
  next_due_date: string;
  status: string;
  sent_at: string | null;
  recurrence_days: number;
}

export interface DocumentItem {
  id: string;
  document_name: string | null;
  document_category: string | null;
  doctor_name: string | null;
  hospital_name: string | null;
  mime_type: string;
  extraction_status: string;
  rejection_reason: string | null;
  uploaded_at: string | null;
  event_date: string | null;
}

export interface DiagnosticResultItem {
  test_type: "blood" | "urine" | "fecal" | "xray";
  parameter_name: string;
  value_numeric: number | null;
  value_text: string | null;
  unit: string | null;
  reference_range: string | null;
  status_flag: string | null;
  observed_at: string | null;
  document_id: string | null;
  created_at: string | null;
}

export interface ConditionMedicationItem {
  id: string;
  name: string;
  dose: string | null;
  frequency: string | null;
  route: string | null;
  status: string;
  started_at: string | null;
  refill_due_date: string | null;
  price: string | null;
  notes: string | null;
}

export interface ConditionMonitoringItem {
  id: string;
  name: string;
  frequency: string | null;
  next_due_date: string | null;
  last_done_date: string | null;
}

export interface ConditionItem {
  id: string;
  name: string;
  diagnosis: string | null;
  condition_type: string;
  diagnosed_at: string | null;
  notes: string | null;
  icon: string | null;
  managed_by: string | null;
  source: string;
  is_active: boolean;
  episode_count?: number;
  medications: ConditionMedicationItem[];
  monitoring: ConditionMonitoringItem[];
  created_at: string | null;
}

export interface ConditionRecommendation {
  icon: string;
  title: string;
  reason: string;
  priority: string;
  cart_id: string | null;
}

export interface LastVetVisit {
  vet_name: string | null;
  clinic_name: string | null;
  address: string | null;
  managing_condition: string | null;
  managing_since: string | null;
  last_visit_date: string | null;
  next_due_date: string | null;
  notes: string | null;
  status: string | null;
}

export interface ContactItem {
  id: string;
  role: string;
  name: string;
  clinic_name: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  source: string;
  source_document_name: string | null;
  source_document_category: string | null;
  created_at: string | null;
}

export interface HealthScoreBreakdown {
  category: string;
  key: string;
  weight: number;
  score: number;
  done: number | null;
  total: number | null;
}

export interface HealthScoreDragger {
  category: string;
  score: number;
  weight: number;
}

export interface HealthScore {
  score: number;
  label: string;
  breakdown: HealthScoreBreakdown[];
  draggers: HealthScoreDragger[];
}

export interface MonthlyCompletion {
  month: string;
  items_completed: number;
}

export interface ItemTimelineEntry {
  item_name: string;
  category: string;
  last_done_date: string;
  status: string;
}

export interface StatusSummary {
  total: number;
  up_to_date: number;
  upcoming: number;
  overdue: number;
  incomplete: number;
  cancelled: number;
}

export interface DiagnosticTrendEntry {
  month: string;
  count: number;
}

export interface VaccineMonthlyEntry {
  month: string;
  count: number;
}

export interface VaccineTimelineEntry {
  vaccine_name: string;
  last_done_date: string;
  next_due_date: string | null;
}

export interface HealthTrendsData {
  monthly_completions: MonthlyCompletion[];
  item_timeline: ItemTimelineEntry[];
  status_summary: StatusSummary;
  diagnostic_trends: DiagnosticTrendEntry[];
  vaccine_metrics: {
    monthly_vaccinations: VaccineMonthlyEntry[];
    vaccine_timeline: VaccineTimelineEntry[];
  };
}

export interface VetSummary {
  name: string;
  last_visit: string | null;
}

export interface LifeStageInsight {
  text: string;
  color: "orange" | "green" | "neutral";
}

export interface LifeStageData {
  stage: "puppy" | "junior" | "adult" | "senior";
  age_months: number;
  breed_size: "mini_toy" | "small" | "medium" | "large" | "extra_large";
  stage_boundaries?: {
    junior_start: number;
    adult_start: number;
    senior_start: number;
  };
  insights: LifeStageInsight[];
}

/** @deprecated Use LifeStageInsight */
export type LifeStageTrait = LifeStageInsight;

export interface HealthConditionSummary {
  id: string;
  icon: string;
  title: string;
  severity: string;
  trend_label: string;
  insight: string;
}

export interface HealthConditionV2 {
  id: string;
  name: string;
  type: "chronic" | "recurrent" | "acute";
  status: "needs_attention" | "active" | "monitoring" | "managed" | "resolved";
  severity: "red" | "yellow" | "green";
  trend_label: string;
  insight: string;
  display_line: string;
  recurrence_watch?: boolean;
  soft_resolution?: boolean;
}

export interface HealthConditionsV2 {
  headline_state: "needs_attention" | "active" | "monitoring" | "managed" | "resolved" | "clean";
  conditions: HealthConditionV2[];
  summary: string;
  meta: {
    total_conditions: number;
    red_count: number;
    yellow_count: number;
    green_count: number;
  };
}

export interface CarePlanItem {
  name: string;
  test_type: string;
  product_id?: string | null;
  icon?: string | null;
  price?: number;
  freq: string;
  next_due: string | null;
  status_tag: string;
  classification: string;
  reason: string | null;
  orderable: boolean;
  cta_label?: string;
  signal_level?: string | null;
  info_prompt?: string | null;
  diet_item_id?: string | null;
  /** Raw micronutrient name (e.g. "glucosamine"). Present on supplement items
   *  generated from missing-micronutrient analysis. Used to fetch matching
   *  products via /products/resolve-by-micronutrient instead of diet_item_id. */
  micronutrient?: string | null;
}

export interface CarePlanSection {
  icon: string;
  title: string;
  items: CarePlanItem[];
}

export interface CarePlanV2 {
  continue: CarePlanSection[];
  attend: CarePlanSection[];
  add: CarePlanSection[];
}

export interface DietMacroSummary {
  name: string;
  pct_of_need: number;
  color: string;
  note: string;
}

export interface MissingMicronutrient {
  icon: string;
  name: string;
  reason: string;
}

export interface DietSummary {
  macros: DietMacroSummary[];
  missing_micros: MissingMicronutrient[];
}

export interface RecognitionBullet {
  icon: string;
  label: string;
}

export interface Recognition {
  report_count: number;
  bullets: RecognitionBullet[];
}

export interface AskVetChartPoint {
  date: string;
  value: number;
  marker: string;
  status: string;
}

export interface AskVetChartData {
  points: AskVetChartPoint[];
}

export interface AskVetTimelineNode {
  label: string;
  date: string | null;
  icon: string;
  finding?: string;
  special_type?: "untreated" | "due" | null;
}

export interface AskVetCondition {
  id: string;
  icon: string;
  label: string;
  condition_tag: string;
  headline: string;
  trend: string;
  questions: string[];
  chart_data: AskVetChartData | null;
  timeline_data: AskVetTimelineNode[];
}

export interface AskVetData {
  conditions: AskVetCondition[];
}

export interface BloodPanelRow {
  marker: string;
  range: string;
  value: string;
  status: string;
}

export interface BloodPanelData {
  label: string;
  date: string | null;
  headline: string;
  rows: BloodPanelRow[];
}

export interface WeightSignalPoint {
  date: string;
  value: number;
  alert?: boolean;
}

export interface WeightSignalData {
  points: WeightSignalPoint[];
  headline: string;
  recommendation: string;
  bcs?: string;
}

export interface MetabolicStat {
  value: string;
  label: string;
  unit?: string;
}

export interface MetabolicData {
  headline: string;
  sub: string;
  stats: MetabolicStat[];
}

export interface SignalsData {
  blood_panel: BloodPanelData | null;
  weight: WeightSignalData | null;
  metabolic: MetabolicData | null;
}

export interface CadenceFooter {
  text: string;
  color: string;
  bg: string;
}

export interface VaccineRound {
  id: string;
  label: string;
  vaccines: string;
  done: boolean;
  date: string | null;
}

export interface VaccineCadence {
  headline: string;
  rounds: VaccineRound[];
  gaps: string[];
  footer: CadenceFooter;
}

export interface FleaTickDose {
  num: number;
  label: string;
  gap: string | null;
  status: string;
  gap_alert: boolean;
  date: string | null;
}

export interface FleaTickCadence {
  headline: string;
  doses: FleaTickDose[];
  footer: CadenceFooter;
}

export interface DewormingNode {
  label: string;
  state: string;
  date: string | null;
}

export interface DewormingCadence {
  headline: string;
  nodes: DewormingNode[];
  footer?: CadenceFooter;
}

export interface CadenceData {
  vaccines: VaccineCadence | null;
  flea_tick: FleaTickCadence | null;
  deworming: DewormingCadence | null;
}

export interface HealthTrendsV2 {
  ask_vet: AskVetData | null;
  signals: SignalsData | null;
  cadence: CadenceData | null;
}

export interface VetVisitMedication {
  name: string;
  dose: string | null;
  duration: string | null;
}

export interface VetVisitTest {
  name: string;
  frequency: string | null;
}

export interface VetVisit {
  id: string;
  title: string;
  date: string | null;
  tag: string;
  tag_color: string;
  tag_bg: string;
  key_finding?: string;
  rx: string;
  medications: VetVisitMedication[];
  tests: VetVisitTest[];
  notes: string | null;
}

export interface RecordResult {
  parameter: string;
  value: string;
  unit: string | null;
  range: string | null;
  flag: string | null;
}

export interface RecordItem {
  id: string;
  icon: string;
  type: string;
  title: string;
  date: string | null;
  tag: string;
  tag_color: string;
  tag_bg: string;
  key_finding?: string;
  results?: RecordResult[];
  notes?: string | null;
}

export interface FailedDocument {
  id: string;
  title: string;
  uploaded_at: string | null;
  status?: "failed" | "rejected";
  rejection_reason?: string | null;
}

export interface RecordsV2 {
  vet_visits: VetVisit[];
  records: RecordItem[];
  failed_documents: FailedDocument[];
}

export interface DashboardData {
  pet: PetProfile;
  owner: OwnerInfo;
  preventive_records: PreventiveRecord[];
  reminders: ReminderItem[];
  documents: DocumentItem[];
  diagnostic_results: DiagnosticResultItem[];
  conditions: ConditionItem[];
  contacts: ContactItem[];
  health_score: HealthScore | null;
  vet_summary?: VetSummary | null;
  life_stage?: LifeStageData | null;
  health_conditions_summary?: HealthConditionSummary[];
  health_conditions_v2?: HealthConditionsV2 | null;
  nutrition_analysis?: NutritionAnalysis | null;
  care_plan_v2?: CarePlanV2;
  diet_summary?: DietSummary;
  recognition?: Recognition;
  is_first_visit?: boolean;
}

// --- Admin Types ---

export interface AdminUser {
  id: string;
  mobile_number: string;
  full_name: string | null;
  pincode: string | null;
  email: string | null;
  consent_given: boolean;
  onboarding_state: string;
  is_deleted: boolean;
  created_at: string;
}

export interface AdminPet {
  id: string;
  user_id: string;
  name: string;
  species: string;
  breed: string;
  gender: string;
  dob: string | null;
  weight: number | null;
  neutered: boolean;
  is_deleted: boolean;
  created_at: string;
}

export interface AdminReminder {
  id: string;
  pet_name: string;
  item_name: string;
  next_due_date: string;
  record_status: string;
  reminder_status: string;
  sent_at: string | null;
  created_at: string;
}

export interface AdminDocument {
  id: string;
  pet_id: string;
  pet_name: string;
  document_name: string;
  extraction_status: string;
  created_at: string;
}

export interface AdminMessage {
  id: string;
  mobile_number: string;
  direction: string;
  message_type: string;
  payload: string;
  created_at: string;
}

export interface AdminOrder {
  id: string;
  user_id: string;
  user_name: string;
  user_phone: string;
  pet_id: string | null;
  pet_name: string | null;
  category: string;
  items_description: string;
  status: string;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  users: { total: number; active: number; onboarding_complete: number; deleted: number };
  pets: { total: number; active: number; dogs: number; cats: number };
  documents: { total: number; success: number; pending: number; failed: number };
  preventive_records: { overdue: number; upcoming: number; up_to_date: number; cancelled: number };
  reminders: { total: number; pending: number; sent: number; completed: number; snoozed: number };
  conflicts: { pending: number };
  orders: { total: number; pending: number; confirmed: number; completed: number; cancelled: number };
  messages_24h: number;
}

// --- Nutrition Types ---

export interface BackendDietItem {
  id: string;
  type: 'packaged' | 'homemade' | 'supplement';
  icon: string;
  label: string;
  detail: string | null;
}

export interface NutritionAnalysis {
  // Legacy nested fields (kept for backward compat)
  calories: { actual: number; target: number; status: string };
  macros: Array<{ name: string; icon: string; actual: number; target: number; unit: string; status: string; note: string }>;
  vitamins: Array<{ name: string; status: string; supplement: string | null; price: string | null; priority: string }>;
  minerals: Array<{ name: string; icon: string; status: string; priority: string; reason: string; actual: number; target: number; supplement: string | null; price: string | null }>;
  others: Array<{ name: string; icon: string; status: string; actual: number; target: number; supplement: string | null; price: string | null; priority: string }>;
  improvements: Array<{ dot: string; text: string }>;
  overall_label: string;
  recommendation: string;
  analysis_context: string;
  gap_count: number;
  // Flat fields for DietAnalysisCard
  has_diet_items?: boolean;
  calories_per_day?: number | null;
  calorie_target?: number | null;
  calorie_gap_pct?: number | null;
  food_label?: string | null;
  show_warning?: boolean;
  warning_message?: string | null;
  prescription_context?: string | null;
  protein_pct?: number | null;
  fat_pct?: number | null;
  carbs_pct?: number | null;
  fibre_pct?: number | null;
  micronutrient_gaps?: Array<{ name: string; status: string; severity_score: number }> | null;
  top_improvements?: Array<{ title: string; detail: string; severity: string }> | null;
}

export interface NudgeItem {
  id: string;
  category: string;
  priority: string;
  icon: string | null;
  title: string;
  message: string;
  mandatory: boolean;
  orderable: boolean;
  price: string | null;
  order_type: string | null;
  cart_item_id: string | null;
  dismissed: boolean;
  acted_on: boolean;
  source: string;
  trigger_type: string;
  created_at: string | null;
}

// --- Dashboard Cache (localStorage) ---
// On success: cache the response so the dashboard can show last-known data
// if the backend is temporarily unavailable. Cache is per-token.

const CACHE_PREFIX = DASHBOARD_CACHE_PREFIX;
const DASHBOARD_CACHE_MAX_AGE_MS = 10 * 60 * 1000;

export function getCachedDashboard(token: string): { data: DashboardData; cachedAt: string } | null {
  try {
    const raw = localStorage.getItem(`${CACHE_PREFIX}${token}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const cachedAt = Date.parse(parsed?.cachedAt || "");
    if (!Number.isFinite(cachedAt)) return null;
    if (Date.now() - cachedAt > DASHBOARD_CACHE_MAX_AGE_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

function cacheDashboard(token: string, data: DashboardData): void {
  try {
    localStorage.setItem(
      `${CACHE_PREFIX}${token}`,
      JSON.stringify({ data, cachedAt: new Date().toISOString() })
    );
  } catch {
    // localStorage full or unavailable — ignore silently.
  }
}

// --- Dashboard API ---

/** Result from fetchDashboard — includes staleness info when serving cached data. */
export interface DashboardResult {
  data: DashboardData;
  /** True when data is served from cache because the API is unreachable. */
  stale: boolean;
  /** ISO timestamp of when the cached data was last fetched, if stale. */
  cachedAt?: string;
}

export async function fetchDashboard(token: string): Promise<DashboardResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      // 404 means token is invalid/expired — don't serve stale cache for this.
      // Parse the detail message from the backend for specific error context.
      if (res.status === 404) {
        const body = await res.json().catch(() => null);
        const detail = body?.detail || "Dashboard not found or link has expired.";
        throw new FetchError(detail, 404);
      }
      // 503 = backend temporarily unavailable — fall back to cache below.
      if (res.status === 503) {
        throw new FetchError("Server temporarily unavailable.", 503);
      }
      throw new FetchError(`Request failed: ${res.status}`, res.status);
    }
    const data: DashboardData = await res.json();
    // Cache the fresh response for offline/failure fallback.
    cacheDashboard(token, data);
    return { data, stale: false };
  } catch (e: any) {
    // For 404 (invalid token), never fall back to cache.
    if (e instanceof FetchError && e.status === 404) {
      throw e;
    }

    // For network errors, timeouts, 5xx — try serving cached data.
    const cached = getCachedDashboard(token);
    if (cached) {
      return { data: cached.data, stale: true, cachedAt: cached.cachedAt };
    }

    // No cache available — rethrow the original error.
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch dashboard directly from backend without local cache fallback.
 * Use this after writes when UI must reconcile with authoritative server state.
 */
export async function fetchDashboardFresh(token: string): Promise<DashboardData> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}`, {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      if (res.status === 404) {
        const body = await res.json().catch(() => null);
        const detail = body?.detail || "Dashboard not found or link has expired.";
        throw new FetchError(detail, 404);
      }
      throw new FetchError(`Request failed: ${res.status}`, res.status);
    }

    const data: DashboardData = await res.json();
    cacheDashboard(token, data);
    return data;
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Error with HTTP status code so we can distinguish 404 from 5xx. */
class FetchError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "FetchError";
    this.status = status;
  }
}

export async function updateWeight(
  token: string,
  weight: number
): Promise<{ status: string; old_weight: number | null; new_weight: number }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/weight`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weight }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updatePreventiveDate(
  token: string,
  item_name: string,
  last_done_date: string
): Promise<{
  status: string;
  item_name: string;
  new_last_done_date: string;
  new_next_due_date: string;
  record_status: string;
}> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/preventive`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_name, last_done_date }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updatePreventiveFrequency(
  token: string,
  item_name: string,
  recurrence_days: number
): Promise<{
  status: string;
  item_name: string;
  recurrence_days: number;
  next_due_date: string | null;
  record_status: string;
}> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/preventive-frequency`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_name, recurrence_days }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateMedicineName(
  token: string,
  item_name: string,
  medicine_name: string
): Promise<{
  status: string;
  item_name: string;
  medicine_name: string;
  recurrence_days: number;
  next_due_date: string | null;
  record_status: string;
}> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/preventive-medicine`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_name, medicine_name }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getPreventiveMedicineOptions(
  token: string,
  item_name: string
): Promise<{ item_name: string; options: string[] }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  try {
    const q = new URLSearchParams({ item_name });
    const res = await fetch(`${API_BASE}/dashboard/${token}/preventive-medicine-options?${q.toString()}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getWeightHistory(
  token: string
): Promise<WeightHistoryResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/weight-history`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addWeightEntry(
  token: string,
  weight: number,
  recorded_at: string,
  note?: string
): Promise<WeightEntry> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/weight-history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weight, recorded_at, note: note ?? null }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function retryExtraction(
  token: string,
  documentId: string
): Promise<{ status: string; document_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);
  try {
    const res = await fetch(
      `${API_BASE}/dashboard/${token}/retry-extraction/${documentId}`,
      {
        method: "POST",
        signal: controller.signal,
      }
    );
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Extraction timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadDocument(
  token: string,
  file: File
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(
      `${API_BASE}/dashboard/${token}/upload-document`,
      {
        method: "POST",
        body: formData,
        signal: controller.signal,
      }
    );
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Upload timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteDocument(
  token: string,
  documentId: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/dashboard/${token}/document/${documentId}`,
    { method: "DELETE" }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to delete document: ${res.status}`);
  }
}

export async function fetchLegacyHealthTrends(token: string): Promise<HealthTrendsData> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/trends`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchHealthTrends(token: string): Promise<HealthTrendsV2> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/health-trends-v2`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchRecords(token: string): Promise<RecordsV2> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/records-v2`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getDashboardDocumentUrl(token: string, documentId: string): string {
  return `${API_BASE}/dashboard/${token}/document/${documentId}`;
}

export async function retryAllFailedDocuments(token: string): Promise<{ retried: number; results: { id: string; status: string }[] }> {
  const res = await fetch(`${API_BASE}/dashboard/${token}/retry-all-failed`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// --- Diet Items & Nutrition API ---

export async function getDietItems(token: string): Promise<BackendDietItem[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/diet-items`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addDietItem(
  token: string,
  body: { type: string; label: string; detail?: string; icon?: string }
): Promise<BackendDietItem> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/diet-items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateDietItem(
  token: string,
  itemId: string,
  body: { label: string; detail?: string | null }
): Promise<BackendDietItem> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/diet-items/${itemId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteDietItem(
  token: string,
  itemId: string
): Promise<{ status: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/diet-items/${itemId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getNutritionAnalysis(token: string): Promise<NutritionAnalysis> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // Longer timeout — AI calls involved
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/nutrition-analysis`, {
      next: { revalidate: 300 }, // 5-min client cache — analysis is AI-generated and slow
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getNutritionImportance(token: string): Promise<{ note: string }> {
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/nutrition-importance`, {
      next: { revalidate: 300 }, // 5-min client cache — AI-generated, rarely changes
    });
    if (!res.ok) return { note: "" };
    return res.json();
  } catch {
    return { note: "" };
  }
}

// --- Nudge API ---

export async function getNudges(token: string): Promise<NudgeItem[]> {
  const res = await fetch(`${API_BASE}/dashboard/${token}/nudges`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function dismissNudge(token: string, nudgeId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/dashboard/${token}/nudges/${nudgeId}/dismiss`, {
    method: "PATCH",
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Request failed: ${res.status}`);
  }
}

// --- Hygiene Preferences API ---

export interface HygienePreference {
  id: string;
  item_id: string;
  name: string;
  icon: string;
  category: 'daily' | 'periodic';
  is_default: boolean;
  freq: number;
  unit: string;
  reminder: boolean;
  last_done: string | null;
  tip: string | null;
}

export async function getHygienePreferences(token: string): Promise<HygienePreference[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/hygiene-preferences`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addHygieneItem(
  token: string,
  body: { name: string; icon?: string; category: string; freq?: number; unit?: string }
): Promise<HygienePreference> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/hygiene-preferences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateHygienePreference(
  token: string,
  itemId: string,
  body: { freq: number; unit: string; reminder: boolean; last_done?: string }
): Promise<HygienePreference> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/hygiene-preferences/${itemId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateHygieneDate(
  token: string,
  itemId: string,
  lastDone: string
): Promise<{ id: string; item_id: string; last_done: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/hygiene-preferences/${itemId}/date`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_done: lastDone }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteHygieneItem(
  token: string,
  itemId: string
): Promise<{ status: string; item_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/hygiene-preferences/${itemId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- Condition CRUD ---

export async function addCondition(
  token: string,
  body: {
    name: string;
    diagnosis?: string;
    condition_type?: string;
    diagnosed_at?: string;
    notes?: string;
    icon?: string;
    managed_by?: string;
    medications?: { name: string; dose?: string; frequency?: string; route?: string }[];
    monitoring?: { name: string; frequency?: string }[];
  }
): Promise<{ status: string; condition_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/conditions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteCondition(
  token: string,
  conditionId: string
): Promise<{ status: string; condition_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/conditions/${conditionId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- Condition Timeline & Management ---

export interface TimelinePill {
  t: string;
  c: string;
  bg: string;
}

export interface TimelineEvent {
  date: string;
  type: string;
  icon: string;
  title: string;
  detail: string | null;
  tag: string;
  // Enriched fields for zayn-style two-column timeline card
  label_color?: string;
  border?: string;
  sublabel?: string;
  source_text?: string;
  pills?: TimelinePill[];
}

export interface VetQuestion {
  priority: 'urgent' | 'high' | 'medium';
  icon: string;
  q: string;
  context: string;
}

export async function getConditionTimeline(
  token: string
): Promise<{ events: TimelineEvent[]; total?: number }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/condition-timeline`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getConditionRecommendations(
  token: string
): Promise<{ recommendations: ConditionRecommendation[] }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/condition-recommendations`, {
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getLastVetVisit(
  token: string
): Promise<LastVetVisit> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/last-vet-visit`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateCondition(
  token: string,
  conditionId: string,
  body: {
    name?: string;
    diagnosis?: string;
    condition_type?: string;
    diagnosed_at?: string;
    notes?: string;
    icon?: string;
    managed_by?: string;
  }
): Promise<{ status: string; condition_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/conditions/${conditionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addConditionMedication(
  token: string,
  conditionId: string,
  body: { name: string; dose?: string; frequency?: string; route?: string }
): Promise<{ status: string; medication_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/conditions/${conditionId}/medications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteConditionMedication(
  token: string,
  medicationId: string
): Promise<{ status: string; medication_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/medications/${medicationId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addConditionMonitoring(
  token: string,
  conditionId: string,
  body: { name: string; frequency?: string }
): Promise<{ status: string; monitoring_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/conditions/${conditionId}/monitoring`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteConditionMonitoring(
  token: string,
  monitoringId: string
): Promise<{ status: string; monitoring_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/monitoring/${monitoringId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Log a monitoring item's last done date (used by the "Log" button in the checkup plan). */
export async function updateMonitoringDate(
  token: string,
  monitoringId: string,
  lastDoneDate: string,
): Promise<{ status: string; monitoring_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/monitoring/${monitoringId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_done_date: lastDoneDate }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- AI Insights ---

/** Fetch GPT-generated health summary (cached 7 days). */
export async function getHealthSummary(
  token: string,
): Promise<{ summary: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/health-summary`, {
      next: { revalidate: 300 }, // 5-min client cache — AI-generated, 7-day server cache
      signal: controller.signal,
    });
    if (!res.ok) return { summary: "" };
    return res.json();
  } catch {
    return { summary: "" };
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Fetch GPT-generated vet consultation questions (cached 7 days). */
export async function getVetQuestions(token: string): Promise<VetQuestion[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/vet-questions`, {
      next: { revalidate: 300 }, // 5-min client cache — AI-generated, 7-day server cache
      signal: controller.signal,
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Force-regenerate vet questions and update the DB cache. */
export async function regenerateVetQuestions(token: string): Promise<VetQuestion[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/vet-questions/regenerate`, {
      method: "POST",
      signal: controller.signal,
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- Contact CRUD ---

export async function addContact(
  token: string,
  body: {
    role?: string;
    name: string;
    clinic_name?: string;
    phone?: string;
    email?: string;
    address?: string;
  }
): Promise<{ status: string; contact_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/contacts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateContact(
  token: string,
  contactId: string,
  body: {
    role?: string;
    name?: string;
    clinic_name?: string;
    phone?: string;
    email?: string;
    address?: string;
  }
): Promise<{ status: string; contact_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/contacts/${contactId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function deleteContact(
  token: string,
  contactId: string
): Promise<{ status: string; contact_id: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/contacts/${contactId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- Cart & Orders API ---

export interface CartItemData {
  id: string;
  product_id: string;
  icon: string | null;
  name: string;
  sub: string | null;
  price: number;
  tag: string | null;
  tag_color: string | null;
  in_cart: boolean;
  quantity: number;
}

export interface CartResponse {
  items: CartItemData[];
  summary: { count: number; subtotal: number };
}

export interface CartRecommendation {
  product_id: string;
  icon: string;
  name: string;
  sub: string;
  price: number;
  tag: string | null;
  tag_color: string | null;
  reason: string;
  priority: string;
  category: string;
}

export interface PlaceOrderResponse {
  order_id: string;
  items: Array<{ product_id: string; name: string; icon: string | null; price: number; quantity: number; total: number }>;
  subtotal: number;
  discount: number;
  delivery: number;
  total: number;
  payment_method: string;
  status: string;
}

export async function getCart(token: string): Promise<CartResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function toggleCartItem(token: string, productId: string): Promise<CartItemData> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/toggle/${productId}`, {
      method: "POST",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function updateCartQuantity(
  token: string, productId: string, quantity: number
): Promise<CartItemData> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/${productId}/quantity`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function addToCart(
  token: string,
  body: { product_id: string; name: string; price: number; icon?: string; sub?: string; tag?: string; tag_color?: string }
): Promise<CartItemData> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function removeFromCart(token: string, productId: string): Promise<{ status: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/${productId}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getCartRecommendations(token: string): Promise<CartRecommendation[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/recommendations`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function applyCoupon(token: string, code: string): Promise<{ valid: boolean; discount_percent: number; code: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/cart/apply-coupon`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function placeOrder(
  token: string,
  body: { payment_method: string; address?: { name: string; line: string; tag: string }; coupon?: string }
): Promise<PlaceOrderResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/place-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface CreatePaymentResponse {
  razorpay_order_id: string;
  amount: number;        // paise (INR * 100)
  currency: string;
  key_id: string;
  order_db_id: string;
  subtotal: number;
  discount: number;
  delivery: number;
  total: number;
}

export interface VerifyPaymentResponse {
  order_id: string;
  items: Array<{ product_id: string; name: string; icon: string | null; price: number; quantity: number; total: number }>;
  subtotal: number;
  discount: number;
  delivery: number;
  total: number;
  payment_method: string;
  payment_status: string;
  status: string;
}

export async function createPayment(
  token: string,
  body: { payment_method: string; address?: { name: string; line: string; tag: string }; coupon?: string; coupon_discount_percent?: number }
): Promise<CreatePaymentResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/create-payment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function verifyPayment(
  token: string,
  body: { order_db_id: string; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }
): Promise<VerifyPaymentResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}/verify-payment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Authenticate to the admin dashboard with a password.
 * On success, returns the admin API key for subsequent requests.
 * Throws on invalid password or network error.
 */
export async function adminLogin(password: string): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${API_BASE}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
      signal: controller.signal,
    });
    if (res.status === 403) {
      throw new Error("Invalid password.");
    }
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    const data = await res.json();
    return data.admin_key;
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

// --- Admin API ---

async function adminFetch<T>(path: string, adminKey: string): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "X-ADMIN-KEY": adminKey },
      cache: "no-store",
      signal: controller.signal,
    });
    if (res.status === 403) throw new Error("Invalid admin key.");
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function adminMutate<T>(
  path: string,
  adminKey: string,
  method: "PATCH" | "POST",
  body?: unknown
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        "X-ADMIN-KEY": adminKey,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (res.status === 403) throw new Error("Invalid admin key.");
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const adminApi = {
  getStats: (key: string) => adminFetch<AdminStats>("/admin/stats", key),
  getUsers: (key: string) => adminFetch<AdminUser[]>("/admin/users", key),
  getPets: (key: string) => adminFetch<AdminPet[]>("/admin/pets", key),
  getReminders: (key: string) =>
    adminFetch<AdminReminder[]>("/admin/reminders", key),
  getDocuments: (key: string) =>
    adminFetch<AdminDocument[]>("/admin/documents", key),
  getMessages: (key: string, direction?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (direction) params.set("direction", direction);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString();
    return adminFetch<AdminMessage[]>(
      `/admin/messages${qs ? `?${qs}` : ""}`,
      key
    );
  },
  getOrders: (key: string, status?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    const qs = params.toString();
    return adminFetch<AdminOrder[]>(
      `/admin/orders${qs ? `?${qs}` : ""}`,
      key
    );
  },
  updateOrderStatus: (
    key: string,
    orderId: string,
    status: string,
    adminNotes?: string
  ) =>
    adminMutate(
      `/admin/orders/${orderId}/status`,
      key,
      "PATCH",
      { status, admin_notes: adminNotes ?? null }
    ),
  softDeleteUser: (key: string, userId: string) =>
    adminMutate(`/admin/soft-delete-user/${userId}`, key, "PATCH"),
  revokeToken: (key: string, petId: string) =>
    adminMutate(`/admin/revoke-token/${petId}`, key, "PATCH"),
  triggerReminder: (key: string, petId: string) =>
    adminMutate(`/admin/trigger-reminder/${petId}`, key, "POST"),
};
