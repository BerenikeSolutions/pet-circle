/**
 * PetCircle — Health Dashboard PDF Generator
 *
 * Generates a structured health report PDF from DashboardData.
 * Document appendix is organized into 5 standard sections:
 *   🩸 Blood Reports | 💧 Urine Reports | 🔍 Imaging | 💊 Prescription | 🔬 PCR & Parasite Panel
 *
 * Filename format: {pet-name}-complete-analysis-{YYYY-MM-DD}.pdf
 */

import { jsPDF } from 'jspdf';
import type {
  DashboardData,
  DocumentItem,
  ConditionItem,
  PreventiveRecord,
  DiagnosticResultItem,
} from '@/lib/api';

// ─── Brand colours ─────────────────────────────────────────────────────────
const BRAND       = '#D44800';
const BRAND_LIGHT = '#FFF0EA';
const GREY_DARK   = '#1A1A1A';
const GREY_MID    = '#555555';
const GREY_LIGHT  = '#888888';
const GREY_LINE   = '#E0E0E0';
const GREEN       = '#22C55E';
const RED         = '#EF4444';
const AMBER       = '#F59E0B';
const BLUE        = '#3B82F6';
const WHITE       = '#FFFFFF';

// ─── Document category → section mapping ───────────────────────────────────
// Canonical category → PDF appendix section definition.
// The `canonical` values MUST match DOCUMENT_CATEGORIES in backend constants.py.
const DOC_SECTIONS = [
  {
    key: 'blood',
    canonical: 'Blood Report',
    label: 'BLOOD REPORTS',
    emoji: '🩸',
    fallback: (cat: string) =>
      /blood|cbc|haematology|haemogram|biochem|complete blood/i.test(cat),
  },
  {
    key: 'urine',
    canonical: 'Urine Report',
    label: 'URINE REPORTS',
    emoji: '💧',
    fallback: (cat: string) => /urine|urinalysis|urine culture|urine test/i.test(cat),
  },
  {
    key: 'imaging',
    canonical: 'Imaging',
    label: 'IMAGING — ULTRASOUND & X-RAY',
    emoji: '🔍',
    fallback: (cat: string) =>
      /imaging|ultrasound|usg|x.?ray|xray|radiology|scan/i.test(cat),
  },
  {
    key: 'prescription',
    canonical: 'Prescription',
    label: 'PRESCRIPTION',
    emoji: '💊',
    fallback: (cat: string) => /prescription|rx|medication|treatment/i.test(cat),
  },
  {
    key: 'pcr',
    canonical: 'PCR & Parasite Panel',
    label: 'PCR & PARASITE PANEL',
    emoji: '🔬',
    fallback: (cat: string) =>
      /pcr|parasite|parasite panel|tick|anaplasma|ehrlichia|babesia|hepatozoon/i.test(cat),
  },
] as const;

function classifyDoc(doc: DocumentItem): (typeof DOC_SECTIONS)[number] | null {
  const cat = (doc.document_category || '').trim();
  // Prefer exact canonical match from backend
  for (const section of DOC_SECTIONS) {
    if (cat.toLowerCase() === section.canonical.toLowerCase()) return section;
  }
  // Fallback: keyword match on category + document name
  const text = `${cat} ${doc.document_name || ''}`.toLowerCase();
  for (const section of DOC_SECTIONS) {
    if (section.fallback(text)) return section;
  }
  return null;
}

// ─── Helpers ───────────────────────────────────────────────────────────────
function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function slugify(name: string): string {
  return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function hexToRgb(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

function setFill(doc: jsPDF, hex: string) {
  doc.setFillColor(...hexToRgb(hex));
}
function setDraw(doc: jsPDF, hex: string) {
  doc.setDrawColor(...hexToRgb(hex));
}
function setTextColor(doc: jsPDF, hex: string) {
  doc.setTextColor(...hexToRgb(hex));
}

// ─── Page management ───────────────────────────────────────────────────────
const PAGE_W    = 210; // A4 mm
const PAGE_H    = 297;
const MARGIN    = 18;
const CONTENT_W = PAGE_W - MARGIN * 2;

class PdfBuilder {
  private doc: jsPDF;
  private y: number;
  private pageNum: number;
  private totalPages = 0; // filled after

  constructor() {
    this.doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });
    this.y = MARGIN;
    this.pageNum = 1;
  }

  get pdf(): jsPDF { return this.doc; }
  get curY(): number { return this.y; }

  newPage() {
    this.doc.addPage();
    this.pageNum++;
    this.y = MARGIN;
  }

  /** Ensure there are `need` mm left on current page, otherwise add a new page */
  ensureSpace(need: number) {
    if (this.y + need > PAGE_H - MARGIN) this.newPage();
  }

  move(mm: number) { this.y += mm; }

  /** Horizontal rule */
  hr(color = GREY_LINE, thickness = 0.3) {
    setDraw(this.doc, color);
    this.doc.setLineWidth(thickness);
    this.doc.line(MARGIN, this.y, PAGE_W - MARGIN, this.y);
    this.y += 3;
  }

  /** Section heading — brand coloured bar left + bold text */
  sectionHeading(text: string) {
    this.ensureSpace(12);
    setFill(this.doc, BRAND);
    this.doc.rect(MARGIN, this.y, 3, 6, 'F');
    setTextColor(this.doc, BRAND);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setFontSize(9);
    this.doc.text(text.toUpperCase(), MARGIN + 5, this.y + 4.5);
    this.y += 10;
  }

  /** Sub-heading inside a section */
  subHeading(text: string, color = GREY_DARK) {
    this.ensureSpace(8);
    setTextColor(this.doc, color);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setFontSize(8.5);
    this.doc.text(text, MARGIN, this.y);
    this.y += 5.5;
  }

  /** Body text, auto-wrapped */
  bodyText(text: string, indent = 0, color = GREY_MID, size = 8) {
    this.ensureSpace(6);
    setTextColor(this.doc, color);
    this.doc.setFont('helvetica', 'normal');
    this.doc.setFontSize(size);
    const lines = this.doc.splitTextToSize(text, CONTENT_W - indent);
    for (const line of lines) {
      this.ensureSpace(5);
      this.doc.text(line, MARGIN + indent, this.y);
      this.y += 4.5;
    }
  }

  /** Bullet row */
  bullet(label: string, value = '', indent = 0) {
    this.ensureSpace(6);
    const x = MARGIN + indent;
    setTextColor(this.doc, GREY_MID);
    this.doc.setFont('helvetica', 'normal');
    this.doc.setFontSize(8);
    this.doc.text('•', x, this.y);
    this.doc.setFont('helvetica', 'bold');
    setTextColor(this.doc, GREY_DARK);
    this.doc.text(label, x + 3.5, this.y);
    if (value) {
      const labelW = this.doc.getTextWidth(label);
      setTextColor(this.doc, GREY_MID);
      this.doc.setFont('helvetica', 'normal');
      const val = this.doc.splitTextToSize(value, CONTENT_W - indent - labelW - 6);
      this.doc.text(val[0], x + 3.5 + labelW + 1.5, this.y);
      if (val.length > 1) {
        this.y += 4.5;
        for (let i = 1; i < val.length; i++) {
          this.ensureSpace(5);
          this.doc.text(val[i], x + 7, this.y);
          this.y += 4.5;
        }
        return;
      }
    }
    this.y += 4.5;
  }

  /** Small status pill */
  pill(text: string, bg: string, textColor = WHITE, x?: number, y?: number) {
    const px = x ?? MARGIN;
    const py = y ?? this.y;
    const w = this.doc.getTextWidth(text) + 4;
    const h = 4.5;
    setFill(this.doc, bg);
    this.doc.roundedRect(px, py - 3.2, w, h, 1, 1, 'F');
    setTextColor(this.doc, textColor);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setFontSize(6.5);
    this.doc.text(text, px + 2, py);
    return w;
  }

  /** Key-value pair in two columns */
  kvRow(key: string, value: string, indent = 0) {
    this.ensureSpace(5.5);
    const x = MARGIN + indent;
    setTextColor(this.doc, GREY_LIGHT);
    this.doc.setFont('helvetica', 'normal');
    this.doc.setFontSize(7.5);
    this.doc.text(key, x, this.y);
    setTextColor(this.doc, GREY_DARK);
    this.doc.setFont('helvetica', 'bold');
    const val = this.doc.splitTextToSize(value, CONTENT_W - 40);
    this.doc.text(val[0], x + 38, this.y);
    this.y += 4.5;
  }

  /** Document row in appendix */
  docRow(name: string, date: string, source: string, isLatest: boolean) {
    this.ensureSpace(12);
    const x = MARGIN + 4;

    // dot indicator
    setFill(this.doc, isLatest ? GREEN : GREY_LINE);
    this.doc.circle(x - 1, this.y - 1, 1.2, 'F');

    setTextColor(this.doc, GREY_DARK);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setFontSize(8);
    const nameLines = this.doc.splitTextToSize(name, CONTENT_W - 30);
    this.doc.text(nameLines[0], x + 2, this.y);

    // badge
    const badge = isLatest ? 'Latest' : 'Previous';
    const bw = this.pill(badge, isLatest ? GREEN : GREY_LIGHT, WHITE, PAGE_W - MARGIN - 20, this.y);
    void bw;

    this.y += 4.5;
    setTextColor(this.doc, GREY_LIGHT);
    this.doc.setFont('helvetica', 'normal');
    this.doc.setFontSize(7);
    this.doc.text(`${date}  ·  ${source}`, x + 2, this.y);
    this.y += 5.5;
  }

  /** Page footer */
  drawFooter(petName: string) {
    const totalPages = this.doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      this.doc.setPage(i);
      setTextColor(this.doc, GREY_LIGHT);
      this.doc.setFont('helvetica', 'normal');
      this.doc.setFontSize(6.5);
      this.doc.text(
        `${petName} Health Dashboard  ·  Page ${i} of ${totalPages}  ·  Generated ${new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`,
        MARGIN,
        PAGE_H - 8,
      );
      setDraw(this.doc, GREY_LINE);
      this.doc.setLineWidth(0.2);
      this.doc.line(MARGIN, PAGE_H - 11, PAGE_W - MARGIN, PAGE_H - 11);
    }
  }
}

// ─── Main export ──────────────────────────────────────────────────────────
export function generateHealthPdf(data: DashboardData): void {
  const builder = new PdfBuilder();
  const doc = builder.pdf;
  const pet = data.pet ?? { name: 'Pet', species: '', breed: '', gender: '', dob: null, weight: null };
  const owner = data.owner ?? { full_name: null, pincode: null };

  // ── Cover Header ──────────────────────────────────────────────────────
  // Orange background bar
  setFill(doc, BRAND);
  doc.rect(0, 0, PAGE_W, 52, 'F');

  // Decorative circle
  setFill(doc, '#ffffff08');
  doc.circle(PAGE_W - 20, 15, 30, 'F');

  // Pet name
  setTextColor(doc, WHITE);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(22);
  doc.text(pet.name, MARGIN, 18);

  // Breed · Age · Species
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  const age = pet.dob
    ? (() => {
        const ms = Date.now() - new Date(pet.dob).getTime();
        const yrs = Math.floor(ms / (1000 * 60 * 60 * 24 * 365.25));
        const months = Math.floor(ms / (1000 * 60 * 60 * 24 * 30.44));
        return yrs >= 1 ? `${yrs} yr${yrs > 1 ? 's' : ''}` : `${months} mo`;
      })()
    : '';
  const genderIcon = pet.gender?.toLowerCase() === 'female' ? '♀' : pet.gender?.toLowerCase() === 'male' ? '♂' : '';
  doc.text(
    [pet.breed, age, pet.species].filter(Boolean).join('  ·  ') + (genderIcon ? `  ${genderIcon}` : ''),
    MARGIN, 26,
  );

  // Parent
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(255, 255, 255);
  doc.text(`Pet parent: ${owner.full_name || '—'}`, MARGIN, 33);

  // Stat chips
  const stats = [
    pet.weight ? `${pet.weight} kg` : null,
    data.preventive_records?.length ? `${data.preventive_records.length} Records` : null,
    data.documents?.length ? `${data.documents.length} Documents` : null,
  ].filter(Boolean) as string[];

  let chipX = MARGIN;
  for (const stat of stats) {
    const w = doc.getTextWidth(stat) + 8;
    setFill(doc, 'rgba(255,255,255,0.15)' as any);
    doc.setFillColor(255, 255, 255, 0.2);
    doc.roundedRect(chipX, 37, w, 6, 1.5, 1.5, 'F');
    setTextColor(doc, WHITE);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(7.5);
    doc.text(stat, chipX + 4, 41.3);
    chipX += w + 3;
  }

  // Health score circle (top-right)
  const score = data.health_score?.score ?? 0;
  const scoreLabel = data.health_score?.label ?? '';
  const cx = PAGE_W - MARGIN - 12;
  const cy = 20;
  const r = 13;

  // grey ring
  setDraw(doc, 'rgba(255,255,255,0.2)' as any);
  doc.setDrawColor(255, 255, 255, 0.2);
  doc.setLineWidth(2.5);
  doc.circle(cx, cy, r, 'S');

  // score arc (simplified — draw orange arc via segmented lines)
  const scoreColor = score >= 80 ? GREEN : score >= 60 ? AMBER : RED;
  setDraw(doc, scoreColor);
  doc.setLineWidth(2.5);
  // Draw arc as a series of small line segments
  const startAngle = -Math.PI / 2;
  const endAngle = startAngle + (score / 100) * 2 * Math.PI;
  const segments = 40;
  for (let i = 0; i < segments; i++) {
    const t1 = startAngle + (endAngle - startAngle) * (i / segments);
    const t2 = startAngle + (endAngle - startAngle) * ((i + 1) / segments);
    if (t2 > endAngle) break;
    const x1 = cx + r * Math.cos(t1);
    const y1 = cy + r * Math.sin(t1);
    const x2 = cx + r * Math.cos(t2);
    const y2 = cy + r * Math.sin(t2);
    doc.setLineWidth(2.5);
    doc.line(x1, y1, x2, y2);
  }

  // score number
  setTextColor(doc, WHITE);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.text(String(score), cx, cy + 2, { align: 'center' });
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.text('/ 100', cx, cy + 6.5, { align: 'center' });

  // score label + dragger label
  doc.setFontSize(6.5);
  doc.text(scoreLabel.toUpperCase(), cx, cy + 11, { align: 'center' });

  // ── Health Summary (below header) ─────────────────────────────────────
  builder['y'] = 58;

  // Generate a concise summary from conditions
  const conditions = (data.conditions || []).filter((c) => c.is_active);
  const watchConditions = conditions.filter(
    (c) => c.condition_type === 'chronic' || c.condition_type === 'monitoring',
  );
  const managedCount = conditions.length;

  let summary =
    managedCount === 0
      ? `${pet.name} is in good health with no active conditions on record. Preventive care is being tracked to keep them healthy.`
      : `${pet.name} has ${managedCount} active condition${managedCount > 1 ? 's' : ''} currently being managed. ` +
        (watchConditions.length > 0
          ? `Conditions requiring ongoing attention: ${watchConditions.map((c) => c.name).join(', ')}. `
          : '') +
        `Regular monitoring and preventive care are in place.`;

  const draggers = data.health_score?.draggers ?? [];
  if (draggers.length > 0 && score < 90) {
    summary += ` Health score is influenced by: ${draggers.map((d) => d.category).join(', ')}.`;
  }

  setFill(doc, BRAND_LIGHT);
  const summaryLines = doc.splitTextToSize(summary, CONTENT_W);
  const summaryH = summaryLines.length * 4.5 + 8;
  doc.roundedRect(MARGIN, builder.curY, CONTENT_W, summaryH, 2, 2, 'F');
  setTextColor(doc, GREY_DARK);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  let sy = builder.curY + 5;
  for (const line of summaryLines) {
    doc.text(line, MARGIN + 4, sy);
    sy += 4.5;
  }
  builder['y'] = sy + 4;

  // ── Active Conditions ─────────────────────────────────────────────────
  if (conditions.length > 0) {
    builder.sectionHeading('Active Conditions');

    for (const cond of conditions) {
      builder.ensureSpace(20);

      // condition card background
      setFill(doc, '#F9F9F9');
      const cardStartY = builder.curY;
      // we'll draw the rect after we know the height

      const icon = cond.icon || '●';
      setTextColor(doc, GREY_DARK);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.text(`${icon}  ${cond.name}`, MARGIN + 2, builder.curY + 5);

      // type badge
      const typeLabel = cond.condition_type?.replace(/_/g, ' ').toUpperCase() || 'CONDITION';
      const typeBg = cond.is_active ? BRAND : GREY_LIGHT;
      builder.pill(typeLabel, typeBg, WHITE, PAGE_W - MARGIN - 30, builder.curY + 5);

      builder.move(8);

      if (cond.diagnosis) {
        builder.kvRow('Diagnosis', cond.diagnosis);
      }
      if (cond.diagnosed_at) {
        builder.kvRow('Diagnosed', fmtDate(cond.diagnosed_at));
      }
      if (cond.managed_by) {
        builder.kvRow('Managed by', cond.managed_by);
      }
      if (cond.notes) {
        builder.bodyText(cond.notes, 4, GREY_MID, 7.5);
      }

      // medications
      const activeMeds = cond.medications.filter((m) => m.status === 'active');
      if (activeMeds.length > 0) {
        builder.ensureSpace(6);
        setTextColor(doc, GREY_MID);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(7.5);
        doc.text('Medications', MARGIN + 4, builder.curY);
        builder.move(4.5);

        for (const med of activeMeds) {
          const doseLine = [med.dose, med.frequency, med.route].filter(Boolean).join(' · ');
          builder.bullet(med.name, doseLine ? `  ${doseLine}` : '', 4);
          if (med.refill_due_date) {
            builder.bodyText(`Refill due: ${fmtDate(med.refill_due_date)}`, 12, AMBER, 7);
          }
        }
      }

      // monitoring
      if (cond.monitoring.length > 0) {
        builder.ensureSpace(6);
        setTextColor(doc, GREY_MID);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(7.5);
        doc.text('Monitoring', MARGIN + 4, builder.curY);
        builder.move(4.5);

        for (const mon of cond.monitoring) {
          const nextLine = mon.next_due_date ? `Next: ${fmtDate(mon.next_due_date)}` : '';
          const lastLine = mon.last_done_date ? `Last: ${fmtDate(mon.last_done_date)}` : '';
          builder.bullet(
            mon.name,
            [mon.frequency, nextLine, lastLine].filter(Boolean).join('  ·  '),
            4,
          );
        }
      }

      builder.move(3);
      // draw card outline retroactively
      setDraw(doc, GREY_LINE);
      doc.setLineWidth(0.3);
      doc.roundedRect(MARGIN, cardStartY, CONTENT_W, builder.curY - cardStartY, 2, 2, 'S');
      builder.move(4);
    }
  }

  // ── Preventive Care ─────────────────────────────────────────────────
  const records = data.preventive_records || [];

  const VACCINE_KW = ['vaccine', 'vaccination', 'dhppi', 'rabies', 'kennel cough', 'coronavirus', 'ccov', 'nobivac'];
  const DEWORMING_KW = ['deworm', 'deworming'];
  const FLEA_TICK_KW = ['flea', 'tick', 'tick & flea', 'anti-tick', 'antiparasitic'];

  const filterKW = (recs: PreventiveRecord[], kw: string[]) =>
    recs.filter((r) =>
      kw.some((k) => r.item_name.toLowerCase().includes(k) || r.category?.toLowerCase().includes(k)),
    );

  const vaccines = filterKW(records, VACCINE_KW);
  const deworming = filterKW(records, DEWORMING_KW);
  const fleaTick = filterKW(records, FLEA_TICK_KW);

  builder.sectionHeading('Preventive Care');

  const displayStatus = (rec: PreventiveRecord): string => {
    // Align with dashboard reminders/care-plan behavior for missing history.
    if (!rec.last_done_date && !rec.next_due_date) return 'overdue';
    return rec.status;
  };

  const statusColor = (s: string) =>
    s === 'overdue' ? RED : s === 'upcoming' ? AMBER : s === 'done' ? GREEN : GREY_LIGHT;
  const statusLabel = (s: string) =>
    s === 'overdue' ? 'OVERDUE' : s === 'upcoming' ? 'DUE SOON' : s === 'done' ? 'UP TO DATE' : 'NO RECORD';

  const renderPrevGroup = (title: string, group: PreventiveRecord[], alwaysShow = false) => {
    if (group.length === 0 && !alwaysShow) return;
    builder.subHeading(title, GREY_DARK);
    if (group.length === 0) {
      builder.bodyText('No record found', 4, GREY_LIGHT, 7.5);
      builder.move(2);
      return;
    }

    for (const rec of group) {
      builder.ensureSpace(10);
      const normalized = displayStatus(rec);
      const sc = statusColor(normalized);
      const sl = statusLabel(normalized);

      setTextColor(doc, GREY_DARK);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.text(rec.item_name, MARGIN + 4, builder.curY);

      builder.pill(sl, sc, WHITE, PAGE_W - MARGIN - 26, builder.curY);
      builder.move(4.5);

      const meta = [
        rec.last_done_date ? `Last: ${fmtDate(rec.last_done_date)}` : 'Last: No record',
        rec.next_due_date ? `Next: ${fmtDate(rec.next_due_date)}` : 'Next: —',
      ].join('   ·   ');
      builder.bodyText(meta, 4, GREY_LIGHT, 7.5);

      if (rec.medicine_name) {
        builder.bodyText(`Medicine: ${rec.medicine_name}`, 4, GREY_MID, 7.5);
      }
    }
    builder.move(2);
  };

  // Core groups always shown; "Other Records" only when records exist
  renderPrevGroup('Vaccinations', vaccines, true);
  renderPrevGroup('Deworming', deworming, true);
  renderPrevGroup('Tick & Flea Prevention', fleaTick, true);

  if (records.length > 0) {
    const covered = new Set([...vaccines, ...deworming, ...fleaTick]);
    const others = records.filter((r) => !covered.has(r));
    renderPrevGroup('Other Records', others);
  }

  // ── Diagnostic Test Results ───────────────────────────────────────────
  const diagnostics = data.diagnostic_results || [];
  builder.sectionHeading('Diagnostic Test Results');

  if (diagnostics.length === 0) {
    builder.bodyText('No record found', 0, GREY_LIGHT);
    builder.move(3);
  } else {
    const grouped: Record<string, DiagnosticResultItem[]> = {};
    for (const d of diagnostics) {
      const key = d.test_type || 'other';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(d);
    }

    const typeLabels: Record<string, string> = {
      blood: 'Blood Tests',
      urine: 'Urine Tests',
      fecal: 'Fecal Tests',
      xray: 'X-Ray / Imaging',
      other: 'Other Tests',
    };

    for (const [type, results] of Object.entries(grouped)) {
      builder.subHeading(typeLabels[type] || type, GREY_DARK);

      // Group by date
      const byDate: Record<string, DiagnosticResultItem[]> = {};
      for (const r of results) {
        const key = r.observed_at || 'Unknown date';
        if (!byDate[key]) byDate[key] = [];
        byDate[key].push(r);
      }

      for (const [dateKey, items] of Object.entries(byDate)) {
        builder.ensureSpace(8);
        setTextColor(doc, GREY_MID);
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(7.5);
        doc.text(fmtDate(dateKey), MARGIN + 4, builder.curY);
        builder.move(4.5);

        for (const item of items) {
          builder.ensureSpace(5.5);
          const flagColor =
            item.status_flag === 'HIGH' || item.status_flag === 'LOW' ? RED : GREY_DARK;

          const valueStr = item.value_numeric != null
            ? `${item.value_numeric}${item.unit ? ' ' + item.unit : ''}`
            : item.value_text || '—';

          const refStr = item.reference_range ? `  [Ref: ${item.reference_range}]` : '';
          const flagStr = item.status_flag ? `  ⚑ ${item.status_flag}` : '';

          setTextColor(doc, GREY_DARK);
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7.5);
          doc.text(`• ${item.parameter_name}`, MARGIN + 6, builder.curY);

          const paramW = doc.getTextWidth(`• ${item.parameter_name}`);
          setTextColor(doc, flagColor);
          doc.setFont('helvetica', 'bold');
          doc.text(valueStr + refStr + flagStr, MARGIN + 6 + paramW + 2, builder.curY);
          builder.move(4.5);
        }
        builder.move(2);
      }
    }
  }

  // ── Appendix — Documents ───────────────────────────────────────────
  const documents = data.documents || [];
  if (documents.length > 0) {
    builder.newPage();

    // Appendix header
    setFill(doc, BRAND);
    doc.rect(MARGIN, builder.curY, CONTENT_W, 10, 'F');
    setTextColor(doc, WHITE);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text('APPENDIX — LATEST REPORTS', MARGIN + 4, builder.curY + 7);
    builder.move(14);

    setTextColor(doc, GREY_MID);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.text(
      'Original lab reports for reference. Reports are from the most recent visits unless noted.',
      MARGIN,
      builder.curY,
    );
    builder.move(7);

    // Sort docs by event_date desc (latest first)
    const sorted = [...documents].sort((a, b) => {
      const da = new Date(a.event_date || a.uploaded_at || 0).getTime();
      const db = new Date(b.event_date || b.uploaded_at || 0).getTime();
      return db - da;
    });

    // Bucket into sections
    const bucketed: Record<string, DocumentItem[]> = {
      blood: [],
      urine: [],
      imaging: [],
      prescription: [],
      pcr: [],
      other: [],
    };

    for (const d of sorted) {
      const section = classifyDoc(d);
      if (section) {
        bucketed[section.key].push(d);
      } else {
        bucketed.other.push(d);
      }
    }

    const SECTION_DEFS = [
      ...DOC_SECTIONS,
      { key: 'other', label: 'OTHER REPORTS', emoji: '📋' },
    ] as const;

    for (const section of SECTION_DEFS) {
      const docs = bucketed[section.key as keyof typeof bucketed];
      if (!docs || docs.length === 0) continue;

      builder.ensureSpace(14);

      // Section header row
      setFill(doc, '#F5F5F5');
      doc.rect(MARGIN, builder.curY, CONTENT_W, 8, 'F');
      setTextColor(doc, GREY_DARK);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8.5);
      doc.text(`${section.emoji}  ${section.label}`, MARGIN + 3, builder.curY + 5.5);
      builder.move(11);

      // Track which is the "latest" (first in sorted list per section)
      docs.forEach((d, idx) => {
        const name = d.document_name || d.document_category || 'Unnamed Document';
        const dateStr = fmtDate(d.event_date || d.uploaded_at);
        const source = [d.doctor_name, d.hospital_name].filter(Boolean).join(' · ') || 'Self-initiated';
        builder.docRow(name, dateStr, source, idx === 0);
      });

      builder.move(3);
      builder.hr();
    }

    // Disclaimer
    builder.ensureSpace(14);
    builder.move(3);
    setFill(doc, '#FFF8F5');
    const disclaimer =
      'Note: This dashboard is generated from lab reports and pet parent records for health tracking purposes only. It is not a medical diagnosis. All clinical decisions should be made with a qualified veterinarian.';
    const dLines = doc.splitTextToSize(disclaimer, CONTENT_W - 8);
    const dH = dLines.length * 4.5 + 8;
    doc.roundedRect(MARGIN, builder.curY, CONTENT_W, dH, 2, 2, 'F');
    setFill(doc, BRAND);
    doc.rect(MARGIN, builder.curY, 2, dH, 'F');
    setTextColor(doc, GREY_MID);
    doc.setFont('helvetica', 'italic');
    doc.setFontSize(7.5);
    let dy = builder.curY + 5;
    for (const line of dLines) {
      doc.text(line, MARGIN + 5, dy);
      dy += 4.5;
    }
    builder.move(dH + 4);
  }

  // ── Footer on every page ─────────────────────────────────────────────
  builder.drawFooter(pet.name);

  // ── Save ─────────────────────────────────────────────────────────────
  const petSlug = slugify(pet.name || 'pet');
  const filename = `${petSlug}-complete-analysis-${todayISO()}.pdf`;
  doc.save(filename);
}
