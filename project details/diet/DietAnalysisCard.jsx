/**
 * DietAnalysisCard — PetCircle OS
 *
 * Drop-in replacement for the Diet Analysis card in DashboardView.
 *
 * Props:
 *   pet  — the full pet object (same as used in DashboardView)
 *
 * pet.nutrition shape expected (aligned to agent prompt output):
 * {
 *   calories_per_day: number,        // e.g. 1420
 *   calorie_target: number,          // e.g. 1650
 *   calorie_gap_pct: number,         // e.g. -15 (negative = under, positive = over)
 *   food_label: string,              // e.g. "Rice, veg, egg whites · home cooked"
 *   show_warning: boolean,
 *   warning_message: string,         // omitted if show_warning is false
 *   prescription_context: string,    // omitted if not applicable
 *   protein_pct: float,              // % of daily need met
 *   fat_pct: float,
 *   carbs_pct: float,
 *   fibre_pct: float,
 *   micronutrient_gaps: [
 *     { name: 'calcium',   status: 'missing', severity_score: 0.9, prescribed: false },
 *     { name: 'omega_3',   status: 'low',     severity_score: 0.75 },
 *   ],
 *   top_improvements: [
 *     { title: 'Protein too low', detail: 'Add whole eggs or chicken to meet daily need.', severity: 'high' },
 *   ]
 * }
 */

import React from 'react';

// ── Constants ─────────────────────────────────────────────────────────────────

const nutrColor = { green: '#34C759', amber: '#FF9F1C', red: '#FF3B30' };

// Amber pill background — hardcoded to avoid dependency on --ta CSS variable
const AMBER_PILL_BG  = '#FFF3E0';
const AMBER_PILL_TXT = '#b85c00';
const RED_PILL_BG    = '#FFD6D6';
const RED_PILL_TXT   = '#c0392b';

// Map severity_score (0–1) to pill colours
const pillStyle = (score) => ({
  background: score >= 0.75 ? RED_PILL_BG  : AMBER_PILL_BG,
  color:      score >= 0.75 ? RED_PILL_TXT : AMBER_PILL_TXT,
});

// Map top_improvements severity to dot colour
const improvementColor = (severity) => {
  if (severity === 'high')       return nutrColor.red;
  if (severity === 'medium')     return nutrColor.amber;
  if (severity === 'prescribed') return '#8A8A8E';
  return nutrColor.amber;
};

// Map nutrient name → display label + icon
const microMeta = {
  omega_3:     { icon: '🐟', label: 'Omega-3' },
  omega_6:     { icon: '🌿', label: 'Omega-6' },
  vitamin_e:   { icon: '🫐', label: 'Vitamin E' },
  vitamin_d3:  { icon: '☀️', label: 'Vitamin D3' },
  glucosamine: { icon: '🦴', label: 'Glucosamine' },
  calcium:     { icon: '🦴', label: 'Calcium' },
  phosphorus:  { icon: '⚡', label: 'Phosphorus' },
  iron:        { icon: '🩸', label: 'Iron' },
  zinc:        { icon: '💊', label: 'Zinc' },
  taurine:     { icon: '❤️', label: 'Taurine' },
  fibre:       { icon: '🌾', label: 'Fibre' },
};

// Derive macro donut array from flat prompt fields
// pct = % of daily need met (not % of diet composition)
const deriveMacros = (n) => {
  const entries = [
    { label: 'Protein', pct: Math.round(n.protein_pct) },
    { label: 'Fat',     pct: Math.round(n.fat_pct) },
    { label: 'Carbs',   pct: Math.round(n.carbs_pct) },
    { label: 'Fibre',   pct: Math.round(n.fibre_pct) },
  ];
  return entries
    .filter(m => m.pct != null && !isNaN(m.pct))
    .map(m => {
      let status = 'green';
      let note   = 'On track';
      if (m.pct < 70)       { status = 'red';   note = 'Too low'; }
      else if (m.pct < 85)  { status = 'amber'; note = 'Low'; }
      else if (m.pct > 130) { status = 'red';   note = 'Too high'; }
      else if (m.pct > 115) { status = 'amber'; note = 'Slightly over'; }
      return { ...m, status, note };
    });
};

// ── Donut SVG ─────────────────────────────────────────────────────────────────
const Donut = ({ pct, status, size = 64 }) => {
  const sw = 7, r = (size - sw * 2) / 2, circ = 2 * Math.PI * r;
  const fill = circ * (Math.min(pct, 100) / 100), cx = size / 2;
  const color = nutrColor[status] || '#8A8A8A';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="#E8E4DF" strokeWidth={sw} />
      <circle cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth={sw}
        strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`} />
      <text x={cx} y={cx - 3} textAnchor="middle" fontFamily="DM Sans,sans-serif"
        fontSize="11" fontWeight="700" fill="#1A1A1A">{pct}%</text>
      <text x={cx} y={cx + 9} textAnchor="middle" fontFamily="DM Sans,sans-serif"
        fontSize="9" fill="#8A8A8A">of need</text>
    </svg>
  );
};

// ── Calorie tag ───────────────────────────────────────────────────────────────
const CalTag = ({ calorie_gap_pct }) => {
  if (calorie_gap_pct == null) return null;
  const pct  = Math.abs(calorie_gap_pct);
  const over = calorie_gap_pct > 0;
  if (pct < 2) return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 20,
      background: '#F0FFF4', color: '#1e8c3a' }}>On target</span>
  );
  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 20,
      background: over ? '#FFE0B2' : '#FFF0F0',
      color: over ? '#b85c00' : '#c0392b', flexShrink: 0 }}>
      {pct}% {over ? 'over' : 'under'}
    </span>
  );
};

// ── Main component ────────────────────────────────────────────────────────────
const DietAnalysisCard = ({ pet }) => {
  const n = pet?.nutrition;
  if (!n) return null;

  const macros       = deriveMacros(n);
  const gaps         = (n.micronutrient_gaps || []).filter(g => g.status !== 'sufficient');
  const improvements = (n.top_improvements   || []).slice(0, 3);

  if (!macros.length && !gaps.length) return null;

  return (
    <div className="card">
      <div className="sec-lbl">Diet Analysis</div>

      {/* ── Calorie line ── */}
      {n.calories_per_day && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: '#FFF6ED', borderRadius: 10, padding: '10px 12px', marginBottom: 6,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)', minWidth: 0,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8 }}>
            ~{n.calories_per_day.toLocaleString()} kcal / day
            {n.food_label && (
              <span style={{ color: 'var(--t3)', fontWeight: 400, fontSize: 12, marginLeft: 4 }}>
                · {n.food_label}
              </span>
            )}
          </div>
          <CalTag calorie_gap_pct={n.calorie_gap_pct} />
        </div>
      )}

      {/* ── Prescription context ── */}
      {n.prescription_context && (
        <div style={{ fontSize: 11, color: '#0055cc', background: '#EBF3FF',
          borderRadius: 8, padding: '5px 10px', marginBottom: 8 }}>
          Vet prescribed: {n.prescription_context}
        </div>
      )}

      {/* ── Warning / disclaimer ── */}
      {n.show_warning && n.warning_message && (
        <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 14, padding: '0 2px' }}>
          ⚠ <strong style={{ color: 'var(--t2)' }}>Estimated</strong> — {n.warning_message}
        </div>
      )}

      {/* ── Macro donuts ── */}
      {macros.length > 0 && (
        <div style={{
          display: 'grid', gridTemplateColumns: `repeat(${macros.length}, 1fr)`, gap: 6,
          textAlign: 'center', marginBottom: 14,
          marginTop: n.show_warning || n.calories_per_day ? 8 : 0,
        }}>
          {macros.map(m => (
            <div key={m.label} style={{ display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: 3 }}>
              <Donut pct={m.pct} status={m.status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t1)' }}>{m.label}</div>
              <div style={{ fontSize: 9, fontWeight: 600, color: nutrColor[m.status] || '#8A8A8A' }}>
                {m.note}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Missing micronutrients ── */}
      {gaps.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12, marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--t3)',
            textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
            Missing micronutrients
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {gaps.map(g => {
              const meta = microMeta[g.name] || { icon: '💊', label: g.name };
              const ps   = pillStyle(g.severity_score);
              return (
                <span key={g.name} style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 20,
                  background: ps.background, color: ps.color,
                }}>
                  {meta.icon} {meta.label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Top improvements ── */}
      {improvements.map((imp, i) => (
        <div key={i} style={{
          display: 'flex', gap: 10, padding: '9px 0',
          borderTop: '1px solid var(--border)', alignItems: 'flex-start',
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0, marginTop: 5,
            background: improvementColor(imp.severity),
          }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', marginBottom: 2 }}>
              {imp.title}
              {imp.severity === 'prescribed' && (
                <span style={{ fontSize: 10, fontWeight: 500, color: '#8A8A8E', marginLeft: 6 }}>
                  · Vet prescribed
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.45 }}>
              {imp.detail}
            </div>
          </div>
        </div>
      ))}

    </div>
  );
};

export default DietAnalysisCard;
