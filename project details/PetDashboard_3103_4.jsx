import React, { useState, useEffect, useRef } from 'react';

const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;700&family=DM+Sans:wght@400;500;600;700&display=swap');
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; -webkit-font-smoothing: antialiased; }
    :root {
      --orange: #FF6B35; --amber: #FF9F1C; --black: #1A1A1A;
      --green: #34C759;  --red: #FF3B30;
      --bg: #F7F4F0; --white: #FFFFFF; --warm: #FDFAF7; --border: #E8E4DF;
      --tg: #F0FFF4; --tr: #FFF0F0; --ta: #FFF6ED; --to: #FFF3EE;
      --t1: #1A1A1A; --t2: #4A4A4A; --t3: #8A8A8A;
      --radius: 16px; --rs: 10px;
    }
    body { font-family: 'DM Sans', -apple-system, sans-serif; background: var(--bg); color: var(--t1); min-height: 100vh; padding-bottom: 80px; }
    .app { max-width: 430px; margin: 0 auto; padding: 16px; padding-bottom: 0; }
    .card { background: var(--white); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; margin-bottom: 12px; }
    .sec-lbl { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--t3); margin-bottom: 6px; }
    .banner { background: linear-gradient(135deg, #E8412A, #FF6B35, #FF8C5A); border-radius: var(--radius); padding: 20px; margin-bottom: 12px; }
    .bn-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .brand { font-family: 'Fraunces', serif; font-size: 18px; font-weight: 700; color: #fff; }
    .bell { background: rgba(255,255,255,.18); border: none; border-radius: 50%; width: 36px; height: 36px; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }
    .profile { display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }
    .avatar { width: 56px; height: 56px; background: rgba(255,255,255,.18); border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 28px; flex-shrink: 0; box-shadow: 0 4px 14px rgba(0,0,0,.2); }
    .dog-name { font-family: 'Fraunces', serif; font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 2px; letter-spacing: -0.5px; }
    .dog-sub { font-size: 12px; color: rgba(255,255,255,.8); margin-bottom: 8px; }
    .pills { display: flex; gap: 6px; flex-wrap: wrap; }
    .pill { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 20px; background: rgba(255,255,255,.22); color: #fff; }
    .vet-row { display: flex; align-items: center; gap: 6px; background: rgba(255,255,255,.15); border-radius: 10px; padding: 8px 12px; font-size: 12px; }
    .vet-l { color: rgba(255,255,255,.65); } .vet-v { color: #fff; font-weight: 600; } .vet-sep { color: rgba(255,255,255,.4); margin: 0 2px; }
    .stage-bar { height: 8px; background: #EDEBE8; border-radius: 6px; position: relative; border: 1px solid var(--border); }
    .stage-marker { position: absolute; top: 50%; transform: translate(-50%,-50%); width: 18px; height: 18px; border-radius: 50%; background: var(--orange); border: 3px solid white; box-shadow: 0 0 0 2px var(--orange); }
    .stage-caption { text-align: center; font-size: 12px; color: var(--orange); font-weight: 600; margin-top: 8px; }
    .sec-source { font-size: 12px; color: var(--orange); font-weight: 500; display: flex; align-items: center; gap: 5px; margin-top: -6px; margin-bottom: 12px; }
    .sec-source::before { content: '✦'; font-size: 8px; opacity: 0.7; }
    .s-tag { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap; }
    .s-tag-g { background: var(--tg); color: #1e8c3a; }
    .s-tag-y { background: var(--ta); color: #b85c00; }
    .s-tag-r { background: var(--tr); color: #c0392b; }
    .trait-pill { display: inline-flex; align-items: center; justify-content: center; gap: 4px; padding: 7px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
    .trait-g { background: var(--tg); color: #1e8c3a; }
    .trait-r { background: var(--tr); color: #c0392b; }
    .trait-y { background: var(--ta); color: #b85c00; }
    .trait-p { background: #F0EDE9; color: var(--t2); border: 1px solid var(--border); }
    .care-sec { margin-bottom: 14px; }
    .care-sec:last-child { margin-bottom: 0; }
    .care-hdr { font-size: 11px; font-weight: 700; color: var(--t2); padding-bottom: 6px; border-bottom: 1px solid var(--border); margin-bottom: 4px; }
    .care-item { display: flex; align-items: flex-start; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--border); }
    .care-item:last-child { border-bottom: none; padding-bottom: 0; }
    .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
    .dot-g { background: var(--green); } .dot-y { background: var(--amber); } .dot-r { background: var(--red); }
    .care-name { font-size: 13px; font-weight: 600; color: var(--t1); line-height: 1.3; margin-bottom: 2px; }
    .care-meta { font-size: 11px; color: var(--t3); line-height: 1.4; }
    .order-btn { font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 10px; background: var(--orange); color: #fff; border: none; cursor: pointer; font-family: inherit; }
    .nav-card { background: var(--warm); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
    .nav-arr { width: 32px; height: 32px; background: var(--to); color: var(--orange); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
    .vh { display: flex; align-items: center; gap: 12px; padding: 14px 16px; background: var(--white); border-bottom: 1px solid var(--border); margin: -16px -16px 16px; position: sticky; top: 0; z-index: 50; }
    .back-btn { width: 36px; height: 36px; border-radius: 50%; border: 1.5px solid var(--border); background: var(--white); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; font-family: inherit; }
    .vh-title { font-size: 17px; font-weight: 700; }
    .floater { position: fixed; bottom: 28px; right: 20px; border: none; border-radius: 28px; cursor: pointer; display: flex; align-items: center; z-index: 100; font-family: inherit; transition: opacity .25s, transform .25s; font-weight: 700; }
    .fl-cart { background: var(--orange); color: #fff; padding: 0 18px; height: 48px; gap: 8px; font-size: 13px; box-shadow: 0 4px 18px rgba(255,107,53,.4); }
    .fl-home { background: var(--black); color: #fff; width: 48px; height: 48px; justify-content: center; font-size: 20px; box-shadow: 0 4px 18px rgba(26,26,26,.28); }
    .floater.hidden { opacity: 0; pointer-events: none; transform: translateY(8px); }
    .cart-row { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--border); }
    .cart-icon { width: 44px; height: 44px; background: var(--to); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
    .qty { display: flex; align-items: center; gap: 8px; }
    .qty-btn { width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--border); background: var(--white); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-family: inherit; }
    .field { margin-bottom: 14px; }
    .f-lbl { font-size: 12px; font-weight: 600; color: var(--t3); margin-bottom: 5px; display: block; }
    .f-input { width: 100%; padding: 10px 12px; border: 1.5px solid var(--border); border-radius: var(--rs); font-size: 14px; font-family: inherit; background: var(--white); outline: none; }
    .f-input:focus { border-color: var(--orange); }
    .btn { width: 100%; padding: 14px; border: none; border-radius: var(--rs); font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit; margin-top: 6px; }
    .btn-or { background: var(--orange); color: #fff; }
    .btn-out { background: var(--white); color: var(--t1); border: 1.5px solid var(--border); }
    .rem-row { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border); }
    .rem-row:last-child { border-bottom: none; }
    .edit-btn { font-size: 11px; font-weight: 600; color: var(--orange); background: var(--to); border: none; border-radius: 8px; padding: 3px 8px; cursor: pointer; white-space: nowrap; font-family: inherit; }
    .save-btn { font-size: 11px; font-weight: 600; color: #fff; background: var(--orange); border: none; border-radius: 8px; padding: 3px 8px; cursor: pointer; white-space: nowrap; font-family: inherit; }
    .e-input { width: 100%; font-size: 12px; border: 1.5px solid var(--orange); border-radius: 6px; padding: 3px 6px; font-family: inherit; outline: none; margin-top: 3px; }
    .tr-header { background: var(--white); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 50; padding: 12px 16px 0; margin: -16px -16px 0; }
    .tr-top { display: flex; align-items: center; justify-content: space-between; padding-bottom: 10px; }
    .nscroll { overflow-x: auto; scrollbar-width: none; }
    .nscroll::-webkit-scrollbar { display: none; }
    .npills { display: flex; gap: 8px; padding-bottom: 10px; }
    .npill { flex-shrink: 0; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1.5px solid var(--border); background: var(--white); color: var(--t2); cursor: pointer; font-family: inherit; transition: all .15s; }
    .npill.active { background: var(--black); color: #fff; border-color: var(--black); }
    .tr-content { padding-top: 16px; }
    .tr-section { scroll-margin-top: 130px; margin-bottom: 8px; }
    .donut-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; text-align: center; }
  `}</style>
);

const PET_DATA = {
  name: 'Zayn', breed: 'Labrador Retriever', sex: 'Male', ageLabel: '4 yrs', ageMonths: 48,
  location: 'Mumbai', avatar: '🐕',
  vet: { name: 'Dr. Priya Sharma', lastVisit: '06 May 2025' },
  weight: '30 kg', stats: { conditions: 3, reports: 14 },
  recognition: { routine: [
    { icon: '🩺', label: '3 active conditions being managed' },
    { icon: '💉', label: '4 preventive care items on schedule' },
    { icon: '🥣', label: 'Royal Canin Adult Kibble · 3 cups/day · No supplements' },
  ]},
  vetDiscuss: [
    { id: 'uti-vet', icon: '🦠', label: 'RECURRENT UTI – E. COLI', labelColor: '#FF3B30',
      headline: '3 episodes in 2 years. Never fully eradicated.', subHighlight: 'Post-antibiotic culture still pending', subColor: '#FF6B35',
      points: ['Submit post-antibiotic urine culture to confirm E. coli clearance','Consider culture sensitivity test to rule out antibiotic resistance','3 episodes across 2 years — discuss long-term management plan'] },
    { id: 'anaplasma-vet', icon: '🧬', label: 'TICK FEVER – ANAPLASMA PLATYS', labelColor: '#9B59B6',
      headline: 'Detected Nov 2023. Never treated. Driving 2 years of low platelets.', subHighlight: 'PCR retest overdue 2+ years', subColor: '#FF3B30',
      points: ['Q-PCR retest essential — microscopy is insufficient to confirm clearance','Discuss treatment protocol — Anaplasma platys was never treated','Cyclic platelet dips (4 of 5 readings below 200K) linked to this infection'] },
  ],
  watchouts: [
    { id: 'uti', icon: '🦠', title: 'Recurrent UTI – E. coli', subtitle: '2 episodes in 10 months · Culture +ve E. coli · Repeat culture pending', severity: 'red', trendLabel:'Active · Since Feb 2025', insight: 'Recurring because no post-antibiotic culture was done — E. coli likely never fully cleared.' },
    { id: 'platelets', icon: '🩸', title: 'Tick Fever – Anaplasma', subtitle: 'Platelets 90k–120k cyclic dips · SNAP 4Dx +ve · PCR confirmation advised', severity: 'red', trendLabel:'Recurring · Monitor closely', insight: 'Tick protection gaps of 15–16 weeks allowed Anaplasma to persist — never treated, still driving low platelets.' },
    { id: 'shedding', icon: '🐾', title: 'Shedding Signal', subtitle: 'Coat dullness last 8 weeks · Diet low in Omega-3', severity: 'yellow', trendLabel:'Ongoing · Since Mar 2024', insight: 'Royal Canin kibble has negligible EPA/DHA — direct dietary gap, not a disease signal.' },
    { id: 'weight', icon: '⚖️', title: 'Weight Watch', subtitle: '+1.2 kg over 4 months · BCS trending 6/9', severity: 'yellow', trendLabel:'Trending up · 3 months', insight: '3 cups/day exceeds maintenance for a 33 kg Lab by ~5% — compounds joint risk after age 5.' },
  ],
  carePlan: [
    { section: '💉 Vaccines & Preventive Care', bucket: 'continue', hdrColor: null, items: [
      { id: 'dhppi', name: 'DHPPi (Nobivac)', freq: 'Annual', lastDone: '06 May 2025', nextDue: '06 May 2026', status: 'green', statusLabel: 'On Track', orderable: false },
      { id: 'rabies', name: 'Rabies (Nobivac RL)', freq: 'Annual', lastDone: '06 May 2025', nextDue: '06 May 2026', status: 'green', statusLabel: 'On Track', orderable: false },
      { id: 'kennel', name: 'Kennel Cough (Nobivac KC)', freq: 'Annual', lastDone: '06 May 2025', nextDue: '06 May 2026', status: 'green', statusLabel: 'On Track', orderable: false },
      { id: 'ccov', name: 'Canine Coronavirus (CCoV)', freq: 'Annual', lastDone: '06 May 2025', nextDue: '06 May 2026', status: 'green', statusLabel: 'On Track', orderable: false },
      { id: 'deworm', name: 'Deworming', freq: 'Every 3 months', lastDone: '06 May 2025', nextDue: '06 Aug 2025', status: 'green', statusLabel: 'On Track', orderable: false },
      { id: 'fleatick', name: 'Flea & Tick Protection', freq: 'Monthly', lastDone: '06 May 2025', nextDue: '06 Jun 2025', status: 'yellow', statusLabel: 'Due Soon', orderable: false },
    ]},
    { section: '🧪 Recurrent UTI – E. coli', bucket: 'attend', hdrColor: '#FF3B30', items: [
      { id: 'culture', name: 'Post-antibiotic Urine Culture', freq: 'One-time', lastDone: '—', nextDue: 'Apr 2026', status: 'red', statusLabel: 'Urgent', orderable: false },
    ]},
    { section: '🧬 Tick Fever – Anaplasma', bucket: 'attend', hdrColor: '#FF3B30', items: [
      { id: 'pcr', name: 'Anaplasma platys – PCR Retest', freq: 'One-time', lastDone: '—', nextDue: 'Apr 2026', status: 'red', statusLabel: 'Urgent', orderable: false },
    ]},
    { section: '🐟 Omega-3 & Coat Health', bucket: 'add', hdrColor: '#FF9F1C', items: [
      { id: 'probiotic', name: 'Start Probiotic', freq: 'Daily', lastDone: '—', nextDue: 'Apr 2026', status: 'yellow', statusLabel: 'Recommended', orderable: true, sku: 'PC-PRO-001', price: 649, icon: '🧫', reason: 'Supports gut health & immune response — relevant given recurrent UTI' },
      { id: 'oil', name: 'Sunflower Oil (Kibble Add-on)', freq: 'Daily', lastDone: '—', nextDue: 'Apr 2026', status: 'yellow', statusLabel: 'Recommended', orderable: true, sku: 'PC-OIL-002', price: 299, icon: '🫙', reason: 'Adds Omega-6 to address coat dullness from kibble-only diet' },
    ]},
    { section: '⚖️ Weight & Joint Management', bucket: 'add', hdrColor: '#FF9F1C', items: [
      { id: 'joint', name: 'Joint Support Supplement', freq: 'Daily', lastDone: '—', nextDue: 'Apr 2026', status: 'yellow', statusLabel: 'Recommended', orderable: true, sku: 'PC-JNT-003', price: 599, icon: '🦴', reason: 'Labs at 4yr begin joint stress — early supplementation prevents mobility issues at 6+' },
    ]},
  ],
  diet: { mainFood: 'Royal Canin Adult Kibble', frequency: '3 cups/day', supplements: [], extras: ['Carrots', 'Pumpkin seeds'] },
  nutrition: {
    macros: [
      { label: 'Calories', pct: 105, status: 'amber', note: 'Slightly over' },
      { label: 'Protein', pct: 109, status: 'green', note: 'On track' },
      { label: 'Omega-3', pct: 15, status: 'red', note: 'Critical gap' },
      { label: 'Fat', pct: 118, status: 'amber', note: 'Slightly over' },
    ],
    missingMicros: [
      { icon: '🐟', name: 'Vitamin E', reason: 'Kibble and carrots provide very little. Labs with coat issues need extra Vitamin E as antioxidant — deficiency worsens shedding and dry coat.' },
      { icon: '🦴', name: 'Zinc', reason: 'Pumpkin seeds contain zinc but phytic acid blocks absorption. Labs are predisposed to zinc-responsive dermatosis — low zinc accelerates coat thinning.' },
      { icon: '☀️', name: 'Vitamin D3', reason: 'Indoor Labs in Mumbai get minimal sun synthesis. RC Adult D3 is at the lower AAFCO limit — insufficient for a dog with active immune challenges.' },
    ],
  },
  healthSignals: {
    plateletChart: {
      label: 'BLOOD · PLATELET TREND', labelColor: '#FF3B30', icon: '🩸',
      headline: 'Below normal in 4 of 5 tests since Nov 2023.',
      meta: 'Latest: 160K · Normal ≥200K · Pattern matches Anaplasma platys',
      normalLine: 200, normalLabel: '200K normal',
      points: [
        { label: "Nov'23", val: 178, status: 'low' },
        { label: "Jan'25", val: 156, status: 'low' },
        { label: 'Feb 12', val: 252, status: 'normal' },
        { label: 'Feb 22', val: 222, status: 'normal' },
        { label: "Sep'25", val: 160, status: 'low' },
      ],
    },
    bloodPanel: {
      label: 'BLOOD PANEL · 10 SEP 2025', labelColor: '#FF3B30', icon: '🩸',
      headline: 'All markers normal except platelets.',
      rows: [
        { marker: 'Platelets', range: '≥200K/cmm', value: '160K', status: 'Low' },
        { marker: 'Haemoglobin', range: '12–18 g/dl', value: '16.3', status: 'Normal' },
        { marker: 'WBC', range: '6–17 ×10³', value: '8.8', status: 'Normal' },
        { marker: 'Neutrophils', range: '60–77%', value: '64%', status: 'Normal' },
        { marker: 'ALT', range: '17–78 U/L', value: '41', status: 'Normal' },
        { marker: 'Creatinine', range: '0.4–1.4 mg/dl', value: '1.10', status: 'Normal' },
        { marker: 'Glucose', range: '75–128 mg/dl', value: '90', status: 'Normal' },
        { marker: 'Bilirubin', range: '0–0.4 mg/dl', value: '0.2', status: 'Normal' },
      ],
    },
    pusCells: {
      label: 'URINARY · PUS CELLS / HPF', labelColor: '#2196F3', icon: '💧',
      headline: 'Peaked Dec 2023. One clean read Feb 2025. Still persisting.',
      meta: 'Target: nil', metaHighlight: 'Oct 2025: still 2–3 HPF',
      bars: [
        { label: "Dec'23", val: 8, display: '7–8', status: 'red' },
        { label: "Nov'24", val: 2, display: '1–2', status: 'amber' },
        { label: 'Feb 1', val: 4, display: '3–4', status: 'amber' },
        { label: 'Feb 12', val: 2, display: '1–2', status: 'amber' },
        { label: 'Feb 26', val: 0, display: 'nil', status: 'green' },
        { label: "Sep'25", val: 2, display: '2–3', status: 'amber' },
        { label: "Oct'25", val: 2, display: '2–3', status: 'amber' },
      ],
    },
    urinaryStatus: {
      label: 'URINARY · STATUS', labelColor: '#2196F3', icon: '💧',
      headline: 'Post-antibiotic culture still pending.',
      detail: 'Ep.3 (Sep 2025) treated with Augmentin — pus cells still present Oct 2025. Culture sensitivity testing needed to rule out resistance.',
      detail2: '3 E. Coli episodes across 2 years.',
      footer: '⚠ Submit post-antibiotic urine culture',
    },
    metabolic: {
      label: 'METABOLIC · ORGAN HEALTH', labelColor: '#1e8c3a', icon: '🏥',
      headline: 'Liver and kidneys consistently healthy.',
      sub: 'All markers within range across every test · Imaging clear',
      stats: [
        { value: '41', label: 'ALT (U/L)' },
        { value: '1.10', label: 'Creatinine (mg/dl)' },
        { value: '90', label: 'Glucose (mg/dl)' },
        { value: '0.2', label: 'Bilirubin (mg/dl)' },
      ],
    },
  },
  cadenceCharts: [
    { id: 'vaccines', icon: '💉', label: 'VACCINATIONS · CADENCE', labelColor: '#1e8c3a',
      headline: 'All 4 vaccines current. Annual cadence maintained.', sub: '3 rounds completed across 3 years',
      rounds: [
        { id: 'R1', label: "Mar '23", vaccines: 'DHPPi · RL · R', done: true },
        { id: 'R2', label: "Apr '24", vaccines: 'Vanguard · Rabisin', done: true },
        { id: 'R3', label: "May '25", vaccines: 'DHPPi · RL · KC · CCoV', done: true },
        { id: 'R4', label: "May '26", vaccines: '', done: false },
      ],
      gaps: ['~13 months', '~13 months', '~12 mo'],
      footer: { text: '✓ Next due May 2026', color: '#1e8c3a', bg: '#F0FFF4' },
    },
    { id: 'fleatick', icon: '🦟', label: 'TICK & FLEA PREVENTION · CADENCE', labelColor: '#FF6B35',
      headline: '10 doses given. Two critical gaps in 2024–25.', sub: 'Target: every 4 weeks', subHighlight: 'Longest gap: 16 weeks',
      doses: [
        { num: 1, label: "Dec'23", gap: null, status: 'green' },
        { num: 2, label: 'Jan', gap: '7w', status: 'amber' },
        { num: 3, label: 'Mar', gap: '9w', status: 'amber' },
        { num: 4, label: 'Jun', gap: '11w', status: 'amber' },
        { num: 5, label: 'Aug', gap: '7w', status: 'amber' },
        { num: 6, label: 'Nov', gap: '15w', status: 'red', gapAlert: true },
        { num: 7, label: "Mar'25", gap: '16w', status: 'red', gapAlert: true },
        { num: 8, label: 'May', gap: '10w', status: 'amber' },
        { num: 9, label: 'Jul', gap: '10w', status: 'amber' },
        { num: 10, label: 'Oct', gap: '13w', status: 'amber', gapAmber: true },
        { num: '?', label: 'Next', gap: null, status: 'upcoming' },
      ],
      footer: { text: '⚠ Gaps coincide with Anaplasma reactivation', color: '#b85c00', bg: '#FFF6ED' },
    },
    { id: 'deworming', icon: '🪱', label: 'DEWORMING · CADENCE', labelColor: '#9B59B6',
      headline: 'Only 1 dose in 2+ years. Significantly overdue.', subHighlight: 'All doses from Jan 2024 onwards missed',
      dewormDoses: [
        { label: "Oct '23", done: true, now: false },
        { label: "Jan '24", done: false, now: false },
        { label: 'Apr', done: false, now: false },
        { label: 'Jul', done: false, now: false },
        { label: 'Oct', done: false, now: false },
        { label: "Jan '25", done: false, now: false },
        { label: 'Apr', done: false, now: false },
        { label: 'Now', done: false, now: true },
      ],
      footer: { text: '🚨 Administer immediately', color: '#c0392b', bg: '#FFF0F0' },
    },
  ],
  insights: [
    { icon: '🔗', title: 'Tick gaps → Anaplasma → low platelets', stat: '15–16 wk gaps · Nov 24, Mar 25', detail: '15–16 week gaps (Nov 2024, Mar 2025) coincide exactly with the lowest platelet readings.', sub: '4 of 5 readings below 200K. One normal reading (252K) followed improved tick coverage. PCR confirmation essential before concluding clearance.' },
    { icon: '🔄', title: 'UTI recurring — no culture closure', stat: '3 episodes · 2 yrs · E. coli', detail: '3 E. coli episodes across 2 years with no post-antibiotic culture after any episode.', sub: 'Pus cells still present Oct 2025. Likely driving antibiotic resistance and relapse.' },
    { icon: '🐟', title: 'Omega-3 deficiency driving coat & shedding', stat: 'Omega-3 at 15% of need · 8 wks coat dullness', detail: 'Royal Canin kibble has almost no EPA/DHA. Labs cannot convert ALA from pumpkin seeds efficiently.', sub: 'Coat dullness ongoing 8 weeks. Direct dietary gap — not a disease signal.' },
    { icon: '⚖️', title: 'Calorie surplus driving weight creep', stat: '+1.2 kg · 4 months · BCS 6/9', detail: '3 cups/day exceeds maintenance for a 33 kg Lab by ~5%.', sub: '+1.2 kg over 4 months, BCS trending 6/9. Compounds joint risk after age 5.' },
    { icon: '✅', title: 'Core organs holding despite chronic infection', stat: 'ALT 41 · Creatinine 1.10 · Imaging clear', detail: 'All liver and kidney markers normal across every test despite 2 years of chronic infection.', sub: 'ALT, creatinine, glucose, bilirubin all within range. Imaging clear.' },
  ],
};

const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;
const dotClass = { green: 'dot-g', yellow: 'dot-y', red: 'dot-r' };
const nutrColor = { green: '#34C759', amber: '#FF9F1C', red: '#FF3B30' };

const ViewHeader = ({ title, onBack }) => (
  <div className="vh">
    <button className="back-btn" onClick={onBack}>←</button>
    <span className="vh-title">{title}</span>
  </div>
);

const Donut = ({ pct, status, size = 80 }) => {
  const sw = 7, r = (size - sw * 2) / 2, circ = 2 * Math.PI * r;
  const fill = circ * (Math.min(pct, 100) / 100), cx = size / 2;
  const color = nutrColor[status] || '#8A8A8A';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="#E8E4DF" strokeWidth={sw} />
      <circle cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth={sw}
        strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round" transform={`rotate(-90 ${cx} ${cx})`} />
      <text x={cx} y={cx - 3} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontSize="11" fontWeight="700" fill="#1A1A1A">{pct}%</text>
      <text x={cx} y={cx + 9} textAnchor="middle" fontFamily="DM Sans,sans-serif" fontSize="9" fill="#8A8A8A">of need</text>
    </svg>
  );
};

const STAGES = [
  { label: 'Puppy', sub: '0–1 yr', maxMonths: 12 },
  { label: 'Junior', sub: '1–2 yr', maxMonths: 24 },
  { label: 'Adult', sub: '2–7 yr', maxMonths: 84 },
  { label: 'Senior', sub: '7+ yr', maxMonths: 999 },
];

const LifeStageCard = ({ pet }) => {
  const STAGE_WIDTHS = [10, 12, 45, 33];
  const STAGE_STARTS = STAGE_WIDTHS.reduce((acc, w, i) => { acc.push(i === 0 ? 0 : acc[i-1] + STAGE_WIDTHS[i-1]); return acc; }, []);
  const adultStart = STAGE_STARTS[2], adultWidth = STAGE_WIDTHS[2];
  const posInAdult = (pet.ageMonths - 24) / (84 - 24);
  const markerPct = adultStart + posInAdult * adultWidth;
  const traits = [
    { label: 'Peak strength', cls: 'trait-g' },
    { label: 'High stamina', cls: 'trait-g' },
    { label: 'Food-motivated', cls: 'trait-r' },
    { label: 'Joint watch', cls: 'trait-y' },
    { label: 'Velcro dog', cls: 'trait-p' },
  ];
  return (
    <div className="card" style={{ paddingBottom: 12 }}>
      <div className="sec-lbl">What to expect as {pet.name} turns 4</div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--t3)', marginBottom: 4 }}>
        {STAGES.map((s, i) => (
          <span key={s.label} style={{ width: `${STAGE_WIDTHS[i]}%`, textAlign: 'center', color: i === 2 ? 'var(--orange)' : 'var(--t3)', fontWeight: i === 2 ? 700 : 400 }}>
            {s.label}
          </span>
        ))}
      </div>

      <div className="stage-bar" style={{ marginBottom: 3 }}>
        {STAGES.map((s, i) => (
          <div key={s.label} style={{ position: 'absolute', left: `${STAGE_STARTS[i]}%`, width: `${STAGE_WIDTHS[i]}%`, top: 0, bottom: 0, background: i === 2 ? 'linear-gradient(90deg,#FF8C5A,#FF6B35)' : '#E0DDD9', opacity: i === 2 ? 1 : 0.5, borderRadius: i === 0 ? '6px 0 0 6px' : i === 3 ? '0 6px 6px 0' : 0 }} />
        ))}
        <div className="stage-marker" style={{ left: `${markerPct}%` }} />
      </div>

      <div className="stage-caption" style={{ fontSize: 11, marginTop: 4, marginBottom: 8 }}>
        {pet.name} is here · {pet.ageLabel}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
        {traits.map(t => (
          <span key={t.label} className={`trait-pill ${t.cls}`} style={{ fontSize: 10, padding: '3px 8px', whiteSpace: 'nowrap' }}>{t.label}</span>
        ))}
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, display: 'flex', gap: 8 }}>
        <div style={{ flex: 1, background: 'var(--ta)', borderRadius: 8, padding: '6px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#b85c00' }}>⚖️ Weight</div>
          <div style={{ fontSize: 10, color: 'var(--t2)', marginTop: 1 }}>BCS 6/9 · cut portion ~10%</div>
        </div>
        <div style={{ flex: 1, background: 'var(--ta)', borderRadius: 8, padding: '6px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#b85c00' }}>💊 Supplements</div>
          <div style={{ fontSize: 10, color: 'var(--t2)', marginTop: 1 }}>Omega-3, Vit E & Zinc needed</div>
        </div>
      </div>
    </div>
  );
};

const BUCKET_META = {
  continue: { label: '✅ Continue', bg: '#F0FFF4', border: '#C3E6CB', color: '#1e8c3a' },
  attend:   { label: '⚠️ Attend to', bg: '#FFF0F0', border: '#FFCDD2', color: '#c0392b' },
  add:      { label: '✦ Quick Fixes to Add', bg: '#FFF3EE', border: '#FFD5C2', color: '#FF6B35' },
};

const DashboardView = ({ pet, cart, onAddToCart, onGoToCart, onGoToTrends, onGoToReminders, onGoToRecords }) => {
  const [floaterUnlocked, setFloaterUnlocked] = useState(false);
  const [addedIds, setAddedIds] = useState({});
  const firstOrderRef = useRef(null);

  useEffect(() => {
    if (floaterUnlocked) return;
    const btn = document.querySelector('.order-btn');
    if (!btn) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setFloaterUnlocked(true); obs.disconnect(); } }, { threshold: 0.1 });
    obs.observe(btn);
    return () => obs.disconnect();
  }, [floaterUnlocked]);

  const handleAddToCart = (item) => {
    onAddToCart(item);
    setAddedIds(prev => ({ ...prev, [item.id]: true }));
    setTimeout(() => setAddedIds(prev => ({ ...prev, [item.id]: false })), 1800);
  };

  const cartCount = cart.reduce((sum, i) => sum + i.qty, 0);
  const cartTotal = cart.reduce((sum, i) => sum + i.price * i.qty, 0);
  const buckets = ['continue', 'attend', 'add'];
  const byBucket = (b) => pet.carePlan.filter(s => s.bucket === b);

  return (
    <>
      <div className="banner">
        <div className="bn-top">
          <span className="brand">PetCircle</span>
          <button className="bell" onClick={onGoToReminders} title="Care Reminders">🔔</button>
        </div>
        <div className="profile">
          <div className="avatar">{pet.avatar}</div>
          <div style={{ minWidth: 0 }}>
            <div className="dog-name">{pet.name}</div>
            <div className="dog-sub" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pet.breed} · {pet.sex} · {pet.ageLabel} · ⚖️ {pet.weight}</div>
          </div>
        </div>
        <div className="vet-row" style={{ flexWrap: 'nowrap', overflow: 'hidden' }}>
          <span style={{ flexShrink: 0 }}>🩺</span>
          <span className="vet-l" style={{ flexShrink: 0 }}>Vet</span>
          <span className="vet-v" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{pet.vet.name}</span>
          <span className="vet-sep" style={{ flexShrink: 0 }}>·</span>
          <span className="vet-l" style={{ flexShrink: 0, whiteSpace: 'nowrap' }}>Last visit</span>
          <span className="vet-v" style={{ flexShrink: 0, whiteSpace: 'nowrap' }}>{pet.vet.lastVisit}</span>
        </div>
      </div>

      <div className="card">
        <div className="sec-lbl">What We Found</div>
        <div style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 12, lineHeight: 1.5 }}>
          We reviewed <strong style={{ color: 'var(--t1)' }}>{pet.stats.reports} reports</strong> and WhatsApp chat and identified {pet.name}'s current care routine.{' '}
          <span onClick={onGoToRecords} style={{ color: 'var(--t3)', textDecoration: 'underline', textDecorationStyle: 'dashed', textUnderlineOffset: 3, cursor: 'pointer', fontSize: 12, fontWeight: 500 }}>View all reports →</span>
        </div>
        {pet.recognition.routine.map((r, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderTop: i === 0 ? '1px solid var(--border)' : 'none' }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>{r.icon}</span>
            <span style={{ fontSize: 13, color: 'var(--t1)', fontWeight: 500 }}>{r.label}</span>
          </div>
        ))}
      </div>

      <LifeStageCard pet={pet} />

      <div className="card">
        <div className="sec-lbl">Health Conditions</div>
        <div style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 10, lineHeight: 1.5 }}>2 conditions identified — managed but needs follow-up.</div>
        {pet.watchouts.filter(w => w.severity === 'red').map(w => (
          <div key={w.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--red)', flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)', flex: 1 }}>{w.title}</span>
              <span style={{ fontSize: 11, color: 'var(--t3)' }}>{w.trendLabel}</span>
            </div>
            {w.insight && <div style={{ fontSize: 12, color: 'var(--t2)', lineHeight: 1.45, paddingLeft: 15, borderLeft: '2px solid #FFCDD2' }}>{w.insight}</div>}
          </div>
        ))}
        <button onClick={onGoToTrends} style={{ marginTop: 12, width: '100%', padding: '10px', background: 'var(--tr)', border: '1px solid #FFCDD2', borderRadius: 'var(--rs)', fontSize: 13, fontWeight: 700, color: '#c0392b', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          🩺 Discuss with your vet →
        </button>
      </div>

      <div className="card">
        <div className="sec-lbl">Diet Analysis</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6, marginBottom: 12 }}>
          {pet.nutrition.macros.map(m => (
            <div key={m.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
              <Donut pct={m.pct} status={m.status} size={64} />
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t1)', textAlign: 'center' }}>{m.label}</div>
              <div style={{ fontSize: 9, color: nutrColor[m.status], fontWeight: 600, textAlign: 'center' }}>{m.note}</div>
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 6 }}>Missing micronutrients</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {pet.nutrition.missingMicros.map(m => (
              <span key={m.name} style={{ fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 20, background: 'var(--ta)', color: '#b85c00' }}>{m.icon} {m.name}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="sec-lbl">{pet.name}'s Care Plan</div>
        <div className="sec-source">Based on lifestage, health & diet analysis</div>
        {buckets.map((bucket, bi) => {
          const secs = byBucket(bucket);
          if (!secs.length) return null;
          const meta = BUCKET_META[bucket];
          return (
            <div key={bucket} style={{ marginBottom: bi < buckets.length - 1 ? 16 : 0 }}>
              <div style={{ background: meta.bg, border: `1px solid ${meta.border}`, borderRadius: 8, padding: '6px 12px', marginBottom: 8, fontSize: 12, fontWeight: 700, color: meta.color }}>{meta.label}</div>
              {secs.map(sec => (
                <div key={sec.section} className="care-sec" style={{ marginBottom: 8 }}>
                  <div className="care-hdr" style={sec.hdrColor ? { color: sec.hdrColor, borderBottomColor: sec.hdrColor + '44' } : {}}>{sec.section}</div>
                  {sec.items.map((item, idx) => {
                    const tagCls = { green: 's-tag-g', yellow: 's-tag-y', red: 's-tag-r' }[item.status];
                    const isAdded = addedIds[item.id];
                    const inCart = cart.find(c => c.id === item.id);
                    return (
                      <div key={item.id} className="care-item" ref={idx === 0 && sec.items[0].orderable ? firstOrderRef : null}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="care-name">{item.name}</div>
                          <div className="care-meta">{item.freq} · Next: {item.nextDue}</div>
                          {item.reason && <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.4, marginTop: 3, fontStyle: 'italic' }}>{item.reason}</div>}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 5, flexShrink: 0 }}>
                          <span className={`s-tag ${tagCls}`}>{item.statusLabel}</span>
                          {item.orderable && (
                            <button className="order-btn" onClick={() => handleAddToCart(item)} style={isAdded ? { background: '#34C759', transform: 'scale(1.04)', transition: 'all .2s' } : { transition: 'all .2s' }}>
                              {isAdded ? `✓ Added${inCart && inCart.qty > 1 ? ` (${inCart.qty})` : ''}` : inCart ? `Order Again (${inCart.qty} in cart)` : 'Order Now →'}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <div className="nav-card" onClick={onGoToRecords} style={{ background: 'var(--white)', borderColor: 'var(--border)' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 3 }}>Source Documents</div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>See {pet.name}'s Full Health Records</div>
          <div style={{ fontSize: 12, color: 'var(--t3)', marginTop: 3 }}>{pet.stats.reports} reports · vet visits · lab results</div>
        </div>
        <div className="nav-arr">→</div>
      </div>

      <button className={`floater fl-cart ${!floaterUnlocked ? 'hidden' : ''}`} onClick={onGoToCart}>
        🛒 {cartCount > 0 ? `${cartCount} item${cartCount !== 1 ? 's' : ''} · ₹${cartTotal.toLocaleString()}` : 'Cart'}
      </button>
    </>
  );
};

const FREQ_OPTIONS = [
  { label: 'Weekly', days: 7 }, { label: 'Every 2 weeks', days: 14 },
  { label: 'Monthly', days: 30 }, { label: 'Every 3 months', days: 90 },
  { label: 'Every 6 months', days: 180 }, { label: 'Annual', days: 365 },
  { label: 'One-time', days: null },
];

const computeNextDue = (lastDoneISO, freqLabel) => {
  const opt = FREQ_OPTIONS.find(f => f.label === freqLabel);
  if (!opt || !opt.days || !lastDoneISO) return '—';
  const d = new Date(lastDoneISO);
  if (isNaN(d)) return '—';
  d.setDate(d.getDate() + opt.days);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
};

const toISO = (displayDate) => {
  if (!displayDate || displayDate === '—') return '';
  const d = new Date(displayDate);
  if (isNaN(d)) return '';
  return d.toISOString().slice(0, 10);
};

const RemindersView = ({ pet, onBack }) => {
  const [items, setItems] = useState(() =>
    pet.carePlan.flatMap(s => s.items.filter(i => i.freq.toLowerCase() !== 'daily').map(i => ({ ...i, section: s.section })))
  );
  const [editingId, setEditingId] = useState(null);
  const [editVals, setEditVals] = useState({});
  const [confirmDel, setConfirmDel] = useState(null);
  const sections = [...new Set(items.map(i => i.section))];

  const startEdit = (item) => { setEditingId(item.id); setEditVals({ freq: item.freq, lastISO: toISO(item.lastDone) }); };
  const saveEdit = () => {
    const nextDue = computeNextDue(editVals.lastISO, editVals.freq);
    const lastDisplay = editVals.lastISO ? new Date(editVals.lastISO).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
    setItems(prev => prev.map(i => i.id === editingId ? { ...i, freq: editVals.freq, lastDone: lastDisplay, nextDue } : i));
    setEditingId(null);
  };
  const deleteItem = (id) => { setItems(prev => prev.filter(i => i.id !== id)); setConfirmDel(null); };

  return (
    <>
      <ViewHeader title="Care Reminders" onBack={onBack} />
      {items.length === 0 && <div className="card" style={{ textAlign: 'center', padding: '32px 0', color: 'var(--t3)', fontSize: 14 }}>No reminders set</div>}
      {sections.filter(sec => items.some(i => i.section === sec)).map(sec => {
        const secItems = items.filter(i => i.section === sec);
        return (
          <div key={sec} className="card">
            <div className="sec-lbl">{sec}</div>
            {secItems.map(item => (
              <div key={item.id} className="rem-row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 0 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div className={`dot ${dotClass[item.status]}`} style={{ marginTop: 6, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)', lineHeight: 1.3 }}>{item.name}</div>
                    {editingId !== item.id && (
                      <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 11, color: 'var(--t3)' }}>
                        <span>Freq: <strong style={{ color: 'var(--t2)' }}>{item.freq}</strong></span>
                        <span>Last: <strong style={{ color: 'var(--t2)' }}>{item.lastDone}</strong></span>
                        <span>Next: <strong style={{ color: item.status === 'red' ? 'var(--red)' : 'var(--t2)' }}>{item.nextDue}</strong></span>
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                    {editingId === item.id ? <button className="save-btn" onClick={saveEdit}>Save</button> : <button className="edit-btn" onClick={() => startEdit(item)}>Edit</button>}
                    {confirmDel !== item.id && editingId !== item.id && <button onClick={() => setConfirmDel(item.id)} style={{ fontSize: 11, fontWeight: 600, color: '#c0392b', background: 'var(--tr)', border: 'none', borderRadius: 8, padding: '3px 8px', cursor: 'pointer', fontFamily: 'inherit' }}>🗑</button>}
                  </div>
                </div>
                {confirmDel === item.id && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, background: 'var(--tr)', borderRadius: 8, padding: '8px 10px' }}>
                    <span style={{ fontSize: 12, color: '#c0392b', flex: 1 }}>Remove this reminder?</span>
                    <button onClick={() => deleteItem(item.id)} style={{ fontSize: 11, fontWeight: 700, background: '#c0392b', color: '#fff', border: 'none', borderRadius: 7, padding: '4px 10px', cursor: 'pointer', fontFamily: 'inherit' }}>Remove</button>
                    <button onClick={() => setConfirmDel(null)} style={{ fontSize: 11, fontWeight: 600, background: 'var(--white)', color: 'var(--t2)', border: '1px solid var(--border)', borderRadius: 7, padding: '4px 10px', cursor: 'pointer', fontFamily: 'inherit' }}>Cancel</button>
                  </div>
                )}
                {editingId === item.id && (
                  <div style={{ marginTop: 10, paddingLeft: 18 }}>
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 3, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Frequency</div>
                      <select value={editVals.freq} onChange={e => setEditVals(v => ({ ...v, freq: e.target.value }))} style={{ width: '100%', fontSize: 13, border: '1.5px solid var(--orange)', borderRadius: 6, padding: '5px 8px', fontFamily: 'inherit', background: 'var(--white)', outline: 'none', color: 'var(--t1)' }}>
                        {FREQ_OPTIONS.map(f => <option key={f.label} value={f.label}>{f.label}</option>)}
                      </select>
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 3, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Last Done</div>
                      <input type="date" className="e-input" value={editVals.lastISO} onChange={e => setEditVals(v => ({ ...v, lastISO: e.target.value }))} style={{ width: '100%' }} />
                    </div>
                    <div style={{ background: 'var(--ta)', borderRadius: 8, padding: '7px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--t3)', fontWeight: 600 }}>Next due (auto)</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#b85c00' }}>{computeNextDue(editVals.lastISO, editVals.freq)}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
      <button className="floater fl-home" onClick={onBack} style={{ bottom: 28 }}>🏠</button>
    </>
  );
};

const CartView = ({ pet, cart, onUpdateQty, onRemove, onBack, onNext }) => {
  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  const delivery = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  const total = subtotal + delivery;
  return (
    <>
      <ViewHeader title="Your Cart" onBack={onBack} />
      <div className="card">
        {cart.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--t3)', fontSize: 14 }}>Your cart is empty</div>
        ) : (
          cart.map(item => (
            <div key={item.id} className="cart-row">
              <div className="cart-icon">{item.icon || '📦'}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{item.name}</div>
                <div style={{ fontSize: 11, color: 'var(--t3)' }}>SKU: {item.sku} · {item.section}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--orange)', marginTop: 4 }}>₹{item.price}</div>
              </div>
              <div className="qty">
                <button className="qty-btn" onClick={() => item.qty > 1 ? onUpdateQty(item.id, item.qty - 1) : onRemove(item.id)}>−</button>
                <span style={{ fontSize: 15, fontWeight: 700, minWidth: 20, textAlign: 'center' }}>{item.qty}</span>
                <button className="qty-btn" onClick={() => onUpdateQty(item.id, item.qty + 1)}>+</button>
              </div>
            </div>
          ))
        )}
      </div>
      {cart.length > 0 && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8, color: 'var(--t2)' }}><span>Subtotal</span><span>₹{subtotal.toLocaleString()}</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 12, color: 'var(--t2)' }}>
            <span>Delivery</span>
            <span>{delivery === 0 ? <span style={{ color: 'var(--green)', fontWeight: 600 }}>Free</span> : `₹${delivery}`}</span>
          </div>
          {delivery > 0 && <div style={{ fontSize: 11, color: 'var(--amber)', background: 'var(--ta)', borderRadius: 8, padding: '6px 10px', marginBottom: 12 }}>Add ₹{FREE_THRESHOLD - subtotal} more for free delivery</div>}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 16, fontWeight: 700, borderTop: '1px solid var(--border)', paddingTop: 12 }}><span>Total</span><span>₹{total.toLocaleString()}</span></div>
          <button className="btn btn-or" onClick={onNext}>Proceed to Checkout</button>
        </div>
      )}
    </>
  );
};

const CheckoutView = ({ cart, onBack, onPlace }) => {
  const [form, setForm] = useState({ name: '', phone: '', address: '', pincode: '', payment: 'cod' });
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));
  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  const delivery = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  return (
    <>
      <ViewHeader title="Checkout" onBack={onBack} />
      <div className="card">
        <div className="sec-lbl">Delivery Details</div>
        <div className="field"><label className="f-lbl">Full Name</label><input className="f-input" placeholder="Name on door" value={form.name} onChange={set('name')} /></div>
        <div className="field"><label className="f-lbl">Phone</label><input className="f-input" type="tel" placeholder="+91 XXXXX XXXXX" value={form.phone} onChange={set('phone')} /></div>
        <div className="field"><label className="f-lbl">Address</label><input className="f-input" placeholder="Flat, building, street" value={form.address} onChange={set('address')} /></div>
        <div className="field"><label className="f-lbl">Pincode</label><input className="f-input" placeholder="400001" value={form.pincode} onChange={set('pincode')} /></div>
      </div>
      <div className="card">
        <div className="sec-lbl">Payment</div>
        {['cod', 'upi', 'card'].map(method => (
          <label key={method} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer', fontSize: 14, fontWeight: 500 }}>
            <input type="radio" name="payment" value={method} checked={form.payment === method} onChange={set('payment')} style={{ accentColor: 'var(--orange)' }} />
            {{ cod: '💵 Cash on Delivery', upi: '📱 UPI / QR', card: '💳 Credit / Debit Card' }[method]}
          </label>
        ))}
      </div>
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 16, fontWeight: 700 }}><span>Total</span><span>₹{(subtotal + delivery).toLocaleString()}</span></div>
        <button className="btn btn-or" onClick={onPlace}>Place Order</button>
      </div>
    </>
  );
};

const ConfirmView = ({ cart, onDone }) => {
  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  const delivery = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  return (
    <>
      <div style={{ textAlign: 'center', padding: '40px 24px 24px' }}>
        <div style={{ width: 80, height: 80, background: 'var(--tg)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, margin: '0 auto 16px' }}>✅</div>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Order Placed!</div>
        <div style={{ fontSize: 14, color: 'var(--t2)', lineHeight: 1.5 }}>Your items will be delivered in 2–4 business days.<br />You'll receive a confirmation on WhatsApp.</div>
      </div>
      <div className="card">
        <div className="sec-lbl">Order Summary</div>
        {cart.map(item => (
          <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontWeight: 600 }}>{item.name} × {item.qty}</span>
            <span>₹{(item.price * item.qty).toLocaleString()}</span>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 700, marginTop: 10 }}>
          <span>Total Paid</span>
          <span style={{ color: 'var(--orange)' }}>₹{(subtotal + delivery).toLocaleString()}</span>
        </div>
        <button className="btn btn-or" style={{ marginTop: 16 }} onClick={onDone}>Back to Dashboard</button>
      </div>
    </>
  );
};

const TREND_TABS = [
  { id: 'watchouts', label: 'Discuss with Vet' },
  { id: 'nutrition', label: 'Nutrition' },
  { id: 'cadence', label: 'Care Cadence' },
  { id: 'insights', label: 'Insights' },
];


const HealthTrendsView = ({ pet, onBack }) => {
  const [activeTab, setActiveTab] = useState('askvet');
  const sectionRefs = useRef({});

  const TABS = [
    { id: 'askvet',    label: 'Ask Your Vet' },
    { id: 'signals',   label: 'Signals'       },
    { id: 'preventive',label: 'Care Cadence'  },
  ];

  useEffect(() => {
    const observers = [];
    TABS.forEach(({ id }) => {
      const el = sectionRefs.current[id];
      if (!el) return;
      const obs = new IntersectionObserver(
        ([e]) => { if (e.isIntersecting) setActiveTab(id); },
        { rootMargin: '-40% 0px -55% 0px', threshold: 0 }
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach(o => o.disconnect());
  }, []);

  const scrollTo = (id) => {
    setActiveTab(id);
    sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Inline style helpers
  const card = { background: '#fff', borderRadius: 16, padding: '18px 16px', marginBottom: 10, border: '1px solid #E8E4DF' };
  const cardLabel = (color) => ({ fontSize: 10, fontWeight: 700, letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 5, color });
  const cardHeadline = { fontSize: 15, fontWeight: 700, color: '#1A1A1A', lineHeight: 1.35, marginBottom: 4 };
  const cardSub = { fontSize: 12, color: '#8A8A8A', fontWeight: 400, lineHeight: 1.5 };
  const sectionLabel = { fontSize: 10, fontWeight: 700, letterSpacing: '1.2px', color: '#8A8A8A', textTransform: 'uppercase', padding: '28px 0 10px', display: 'flex', alignItems: 'center', gap: 8 };

  return (
    <>
      {/* ── Sticky header ── */}
      <div style={{ background: 'var(--bg)', position: 'sticky', top: 0, zIndex: 50, margin: '-16px -16px 0', padding: '14px 16px 0', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 10 }}>
          <button className="back-btn" onClick={onBack}>←</button>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{pet.name}'s Health Trends 🐕</span>
          <div style={{ width: 36 }} />
        </div>
        {/* Nav pills */}
        <div style={{ overflowX: 'auto', scrollbarWidth: 'none', marginBottom: 0 }}>
          <div style={{ display: 'flex', gap: 8, paddingBottom: 10, minWidth: 'max-content' }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => scrollTo(t.id)}
                style={{
                  flexShrink: 0, padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', border: '1px solid', fontFamily: 'inherit', letterSpacing: '0.1px', transition: 'all 0.18s',
                  background: activeTab === t.id ? 'var(--orange)' : '#fff',
                  color: activeTab === t.id ? '#fff' : 'var(--t2)',
                  borderColor: activeTab === t.id ? 'var(--orange)' : 'var(--border)',
                }}
              >{t.label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* ══ SECTION 1 · ASK YOUR VET ══ */}
      <div ref={el => (sectionRefs.current['askvet'] = el)} style={{ scrollMarginTop: 130 }}>
        <div style={{ ...sectionLabel }}>Ask Your Vet <span style={{ flex: 1, height: 1, background: 'var(--border)', display: 'block' }} /></div>

        {/* Share banner */}
        <div style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 14, lineHeight: 1.55, padding: '10px 14px', background: 'var(--tr)', borderRadius: 10, border: '1px solid #FFCDD2' }}>
          🩺 Share this section with <strong style={{ color: 'var(--t1)' }}>Dr. Priya Sharma</strong> at your next visit.
        </div>

        {/* ── Condition 1: UTI ── */}
        <div style={card}>
          {/* Condition tag */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, borderRadius: 20, padding: '4px 11px', marginBottom: 12, background: 'var(--tr)' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)', flexShrink: 0 }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.3px', color: 'var(--red)' }}>UTI / Urinary Trend</span>
          </div>
          <div style={cardHeadline}>Pus cells still present post antibiotic</div>
          <div style={{ ...cardSub, marginBottom: 0 }}>Oct 2025: 2–3 HPF</div>

          {/* Ask your vet questions */}
          <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>Ask your vet</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {[
                'Should we do a culture sensitivity test?',
                'Is the E. coli fully cleared — can we do a post-antibiotic urine culture now?',
                '3 episodes in 2 years — what is the long-term management plan?',
              ].map((q, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 10, background: 'var(--ta)' }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--orange)', flexShrink: 0, marginTop: 1 }}>Ask:</span>
                  <span style={{ fontSize: 13, color: 'var(--t1)', lineHeight: 1.5, fontWeight: 500 }}>{q}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Pus cell bar chart */}
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>Pus cells / HPF · trend</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 10 }}>Target: nil &nbsp;·&nbsp; <span style={{ color: 'var(--amber)', fontWeight: 600 }}>Oct 2025: still 2–3 HPF</span></div>
            <svg viewBox="0 0 358 108" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block' }}>
              <line x1="0" y1="88" x2="358" y2="88" stroke="#E8E4DF" strokeWidth="1"/>
              <rect x="11" y="22" width="28" height="66" rx="3" fill="#FF3B30"/>
              <text x="25" y="17" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF3B30">7–8</text>
              <text x="25" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Dec'23</text>
              <rect x="62" y="74" width="28" height="14" rx="3" fill="#FF9500"/>
              <text x="76" y="69" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF9500">1–2</text>
              <text x="76" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Nov'24</text>
              <rect x="113" y="60" width="28" height="28" rx="3" fill="#FF9500"/>
              <text x="127" y="55" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF9500">3–4</text>
              <text x="127" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Feb 1</text>
              <rect x="164" y="74" width="28" height="14" rx="3" fill="#FF9500"/>
              <text x="178" y="69" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF9500">1–2</text>
              <text x="178" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Feb 12</text>
              <rect x="215" y="85" width="28" height="3" rx="1" fill="#34C759"/>
              <text x="229" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#34C759">nil</text>
              <text x="229" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Feb 26</text>
              <rect x="266" y="68" width="28" height="20" rx="3" fill="#FF9500"/>
              <text x="280" y="63" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF9500">2–3</text>
              <text x="280" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Sep'25</text>
              <rect x="318" y="68" width="28" height="20" rx="3" fill="#FF9500"/>
              <text x="332" y="63" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8.5" fontWeight="600" fill="#FF9500">2–3</text>
              <text x="332" y="102" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Oct'25</text>
            </svg>
          </div>

          {/* UTI episode swim lane */}
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8 }}>Episode timeline</div>
            <div style={{ position: 'relative' }}>
              <div style={{ height: 2, background: 'var(--border)', borderRadius: 2, position: 'absolute', top: 14, left: 14, right: 14, zIndex: 0 }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative', zIndex: 1, margin: '4px 0' }}>
                {[
                  { dot: '#FF3B30', emoji: '🦠', label: 'Ep.1', sub: "Dec'23 No culture" },
                  { dot: '#FF3B30', emoji: '🔴', label: 'Ep.2', sub: "Nov'24 +culture" },
                  { dot: '#34C759', emoji: '✅', label: 'Near clear', sub: 'Feb 26 nil pus' },
                  { dot: '#FF9500', emoji: '🔄', label: 'Ep.3', sub: "Sep'25 +culture" },
                  { dot: '#FF9500', emoji: '⚠️', label: 'Partial', sub: "Oct'25 persists" },
                ].map((ev, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: ev.dot, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>{ev.emoji}</div>
                    <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--t2)', textAlign: 'center' }}>{ev.label}</div>
                    <div style={{ fontSize: 8, color: 'var(--t3)', textAlign: 'center', maxWidth: 52, lineHeight: 1.3 }}>{ev.sub}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Condition 2: Anaplasma ── */}
        <div style={card}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, borderRadius: 20, padding: '4px 11px', marginBottom: 12, background: '#F5EEF8' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#9B59B6', flexShrink: 0 }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.3px', color: '#9B59B6' }}>Tick Fever / Anaplasma</span>
          </div>
          <div style={cardHeadline}>Detected Nov 2023. Never treated. Driving 2 years of low platelets.</div>
          <div style={{ ...cardSub, marginBottom: 0 }}><span style={{ color: 'var(--red)', fontWeight: 600 }}>PCR retest overdue 2+ years</span></div>

          {/* Ask your vet questions */}
          <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>Ask your vet</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {[
                'Anaplasma was found in 2023 but never treated — should we start treatment now?',
                'Can microscopy confirm clearance, or do we need a Q-PCR retest?',
                'Are the low platelets in 4 of 5 readings linked to untreated Anaplasma?',
              ].map((q, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 10, background: '#F5EEF8' }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: '#9B59B6', flexShrink: 0, marginTop: 1 }}>Ask:</span>
                  <span style={{ fontSize: 13, color: 'var(--t1)', lineHeight: 1.5, fontWeight: 500 }}>{q}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Platelet line chart */}
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>Blood · Platelet trend</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 8 }}>
              Latest: <span style={{ color: 'var(--red)', fontWeight: 600 }}>160K</span> &nbsp;·&nbsp; Normal ≥<span style={{ color: 'var(--green)', fontWeight: 600 }}>200K</span> &nbsp;·&nbsp; Pattern matches Anaplasma
            </div>
            <svg viewBox="0 0 358 92" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block' }}>
              <defs>
                <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FF3B30" stopOpacity="0.15"/>
                  <stop offset="100%" stopColor="#FF3B30" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <line x1="0" y1="22" x2="358" y2="22" stroke="#34C759" strokeWidth="1" strokeDasharray="4 3" opacity="0.5"/>
              <text x="290" y="18" fontFamily="Inter,sans-serif" fontSize="9" fill="#34C759" fontWeight="600">200K normal</text>
              <polygon points="20,57 222,63 228,10 232,19 338,62 338,80 20,80" fill="url(#pg)"/>
              <polyline points="20,57 222,63 228,10 232,19 338,62" fill="none" stroke="#FF3B30" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="20"  cy="57" r="4" fill="#FF3B30" stroke="white" strokeWidth="1.5"/>
              <circle cx="222" cy="63" r="4" fill="#FF3B30" stroke="white" strokeWidth="1.5"/>
              <circle cx="228" cy="10" r="4" fill="#34C759" stroke="white" strokeWidth="1.5"/>
              <circle cx="232" cy="19" r="4" fill="#34C759" stroke="white" strokeWidth="1.5"/>
              <circle cx="338" cy="62" r="4" fill="#FF3B30" stroke="white" strokeWidth="1.5"/>
              <text x="20"  y="51" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF3B30" fontWeight="600">178K</text>
              <text x="222" y="57" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF3B30" fontWeight="600">156K</text>
              <text x="228" y="6"  textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#34C759" fontWeight="600">252K</text>
              <text x="246" y="15" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#34C759" fontWeight="600">222K</text>
              <text x="338" y="56" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF3B30" fontWeight="600">160K</text>
              <text x="20"  y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Nov'23</text>
              <text x="222" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Jan'25</text>
              <text x="228" y="88" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="7" fill="#8A8A8A">Feb 12</text>
              <text x="246" y="88" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="7" fill="#8A8A8A">Feb 22</text>
              <text x="338" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Sep'25</text>
            </svg>
          </div>

          {/* Anaplasma detection timeline */}
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8 }}>Detection &amp; treatment timeline</div>
            <div style={{ position: 'relative' }}>
              <div style={{ height: 2, background: 'var(--border)', borderRadius: 2, position: 'absolute', top: 14, left: 14, right: 14, zIndex: 0 }} />
              <div style={{ display: 'flex', justifyContent: 'space-around', position: 'relative', zIndex: 1, margin: '4px 0' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                  <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#FF3B30', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>🔬</div>
                  <div style={{ fontSize: 9, fontWeight: 600, color: '#FF3B30', textAlign: 'center' }}>Detected</div>
                  <div style={{ fontSize: 8, color: 'var(--t3)', textAlign: 'center', maxWidth: 52, lineHeight: 1.3 }}>Q-PCR CT 22.1 Nov'23</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ fontSize: 9, color: '#FF3B30', fontWeight: 700, background: 'var(--tr)', padding: '3px 8px', borderRadius: 8, marginTop: 10, border: '1px solid #FFCDD2' }}>UNTREATED</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                  <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#FF9500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>🔍</div>
                  <div style={{ fontSize: 9, fontWeight: 600, color: '#FF9500', textAlign: 'center' }}>Microscopy</div>
                  <div style={{ fontSize: 8, color: 'var(--t3)', textAlign: 'center', maxWidth: 52, lineHeight: 1.3 }}>Feb 2025 -ve (not PCR)</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                  <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, border: '2px dashed #FF3B30', color: '#FF3B30' }}>?</div>
                  <div style={{ fontSize: 9, fontWeight: 600, color: '#FF3B30', textAlign: 'center' }}>Retest?</div>
                  <div style={{ fontSize: 8, color: 'var(--t3)', textAlign: 'center', maxWidth: 52, lineHeight: 1.3 }}>Not done</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ══ SECTION 2 · SIGNALS ══ */}
      <div ref={el => (sectionRefs.current['signals'] = el)} style={{ scrollMarginTop: 130 }}>
        <div style={{ ...sectionLabel }}>Health Signals <span style={{ flex: 1, height: 1, background: 'var(--border)', display: 'block' }} /></div>

        {/* Blood panel table */}
        <div style={card}>
          <div style={cardLabel('var(--red)')}>🩸 &nbsp;Blood Panel · 10 Sep 2025</div>
          <div style={{ ...cardHeadline, marginBottom: 14 }}>All markers normal except platelets.</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Marker','Range','Value','Status'].map((h, i) => (
                  <th key={h} style={{ fontSize: 10, fontWeight: 600, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.6px', padding: '0 0 8px', textAlign: i >= 2 ? 'right' : 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { marker: 'Platelets',   range: '≥200K/cmm',     value: '160K', status: 'Low'    },
                { marker: 'Haemoglobin', range: '12–18 g/dl',    value: '16.3', status: 'Normal' },
                { marker: 'WBC',         range: '6–17 ×10³',     value: '8.8',  status: 'Normal' },
                { marker: 'Neutrophils', range: '60–77%',         value: '64%',  status: 'Normal' },
                { marker: 'ALT',         range: '17–78 U/L',      value: '41',   status: 'Normal' },
                { marker: 'Creatinine',  range: '0.4–1.4 mg/dl', value: '1.10', status: 'Normal' },
                { marker: 'Glucose',     range: '75–128 mg/dl',  value: '90',   status: 'Normal' },
                { marker: 'Bilirubin',   range: '0–0.4 mg/dl',   value: '0.2',  status: 'Normal' },
              ].map((r, i, arr) => (
                <tr key={r.marker} style={{ borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <td style={{ padding: '10px 0', fontSize: 14, color: 'var(--t1)' }}>{r.marker}</td>
                  <td style={{ padding: '10px 0', fontSize: 11, color: 'var(--t3)' }}>{r.range}</td>
                  <td style={{ padding: '10px 0', fontSize: 15, fontWeight: 600, textAlign: 'right', color: r.status === 'Low' ? 'var(--red)' : 'var(--green)' }}>{r.value}</td>
                  <td style={{ padding: '10px 0 10px 8px', fontSize: 12, fontWeight: 600, textAlign: 'right', color: r.status === 'Low' ? 'var(--red)' : 'var(--green)' }}>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Weight trend */}
        <div style={card}>
          <div style={cardLabel('var(--amber)')}>⚖️ &nbsp;Weight Trend</div>
          <div style={cardHeadline}>+1.2 kg over 4 months. BCS trending 6/9.</div>
          <div style={{ ...cardSub, marginBottom: 14 }}><span style={{ color: '#9a5800', fontWeight: 600 }}>3 cups/day exceeds maintenance by ~5%</span></div>
          <svg viewBox="0 0 358 96" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block' }}>
            <defs>
              <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FF9F1C" stopOpacity="0.18"/>
                <stop offset="100%" stopColor="#FF9F1C" stopOpacity="0"/>
              </linearGradient>
            </defs>
            <polygon points="20,65 100,56 179,42 258,30 338,21 338,80 20,80" fill="url(#wg)"/>
            <polyline points="20,65 100,56 179,42 258,30 338,21" fill="none" stroke="#FF9F1C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="20"  cy="65" r="4" fill="#FF9F1C" stroke="white" strokeWidth="1.5"/>
            <circle cx="100" cy="56" r="4" fill="#FF9F1C" stroke="white" strokeWidth="1.5"/>
            <circle cx="179" cy="42" r="4" fill="#FF9F1C" stroke="white" strokeWidth="1.5"/>
            <circle cx="258" cy="30" r="4" fill="#FF9F1C" stroke="white" strokeWidth="1.5"/>
            <circle cx="338" cy="21" r="4" fill="#FF3B30" stroke="white" strokeWidth="1.5"/>
            <text x="20"  y="59" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF9F1C" fontWeight="600">29.0</text>
            <text x="100" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF9F1C" fontWeight="600">29.3</text>
            <text x="179" y="36" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF9F1C" fontWeight="600">29.8</text>
            <text x="258" y="24" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF9F1C" fontWeight="600">30.2</text>
            <text x="338" y="15" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF3B30" fontWeight="600">30.5kg</text>
            <text x="20"  y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Jun</text>
            <text x="100" y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Aug</text>
            <text x="179" y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Oct</text>
            <text x="258" y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Dec</text>
            <text x="338" y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">Now</text>
          </svg>
          <div style={{ marginTop: 10, padding: '9px 12px', background: 'var(--ta)', borderRadius: 10, fontSize: 12, color: '#9a5800', lineHeight: 1.5 }}>
            💡 Reduce to 2.5–2.75 cups/day · Increase walks to 45 min · Target: 29 kg in 3 months
          </div>
        </div>

        {/* Metabolic / organ health */}
        <div style={card}>
          <div style={cardLabel('var(--green)')}>⚗️ &nbsp;Metabolic · Organ Health</div>
          <div style={cardHeadline}>Liver and kidneys consistently healthy.</div>
          <div style={{ ...cardSub, marginBottom: 0 }}>All markers within range across every test · Imaging clear</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 14 }}>
            {[{ v: '41', l: 'ALT (U/L)' }, { v: '1.10', l: 'Creatinine (mg/dl)' }, { v: '90', l: 'Glucose (mg/dl)' }, { v: '0.2', l: 'Bilirubin (mg/dl)' }].map(s => (
              <div key={s.l} style={{ background: 'var(--tg)', border: '1px solid #C3E6CB', borderRadius: 10, padding: '12px 10px', textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>{s.v}</div>
                <div style={{ fontSize: 10, color: '#2e7d4a', fontWeight: 500, marginTop: 4 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ══ SECTION 3 · CARE CADENCE ══ */}
      <div ref={el => (sectionRefs.current['preventive'] = el)} style={{ scrollMarginTop: 130 }}>
        <div style={{ ...sectionLabel }}>Health Care Cadence <span style={{ flex: 1, height: 1, background: 'var(--border)', display: 'block' }} /></div>

        {/* Vaccinations */}
        <div style={card}>
          <div style={cardLabel('var(--green)')}>💉 &nbsp;Vaccinations · Cadence</div>
          <div style={cardHeadline}>All 4 vaccines current. Annual cadence maintained.</div>
          <div style={{ ...cardSub, marginBottom: 0 }}>3 rounds completed across 3 years</div>
          <svg viewBox="0 0 358 140" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block', marginTop: 12 }}>
            <line x1="20" y1="54" x2="338" y2="54" stroke="#E8E4DF" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="36" y1="28" x2="66" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <line x1="83" y1="28" x2="113" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <text x="74" y="23" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fill="#8A8A8A">~13 months</text>
            <line x1="145" y1="28" x2="173" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <line x1="194" y1="28" x2="222" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <text x="183" y="23" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fill="#8A8A8A">~13 months</text>
            <line x1="254" y1="28" x2="278" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <line x1="298" y1="28" x2="322" y2="28" stroke="#D0CBC4" strokeWidth="0.8" strokeDasharray="3 3"/>
            <text x="288" y="23" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fill="#8A8A8A">~12 months</text>
            <circle cx="20" cy="54" r="13" fill="#34C759" stroke="white" strokeWidth="2"/>
            <text x="20" y="59" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="700" fill="white">R1</text>
            <text x="20" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#1A1A1A">Mar '23</text>
            <text x="20" y="93" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#8A8A8A">DHPPi · RL · R</text>
            <circle cx="129" cy="54" r="13" fill="#34C759" stroke="white" strokeWidth="2"/>
            <text x="129" y="59" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="700" fill="white">R2</text>
            <text x="129" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#1A1A1A">Apr '24</text>
            <text x="129" y="93" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#8A8A8A">Vanguard · Rabisin</text>
            <circle cx="238" cy="54" r="13" fill="#34C759" stroke="white" strokeWidth="2"/>
            <text x="238" y="59" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="700" fill="white">R3</text>
            <text x="238" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#1A1A1A">May '25</text>
            <text x="238" y="93" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#8A8A8A">DHPPi · RL · KC · CCoV</text>
            <circle cx="338" cy="54" r="13" fill="none" stroke="#8A8A8A" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="338" y="59" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fill="#8A8A8A">R4</text>
            <text x="338" y="80" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#8A8A8A">May '26</text>
            <text x="338" y="93" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#34C759">Due</text>
            <circle cx="20" cy="118" r="6" fill="#34C759"/>
            <text x="32" y="122" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">Completed</text>
            <circle cx="130" cy="118" r="6" fill="none" stroke="#8A8A8A" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="142" y="122" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">Upcoming</text>
          </svg>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 600, padding: '5px 11px', borderRadius: 20, marginTop: 14, background: 'var(--tg)', color: '#1a7a35' }}>✓ Next due May 2026</div>
        </div>

        {/* Tick & Flea prevention */}
        <div style={card}>
          <div style={cardLabel('var(--amber)')}>🦟 &nbsp;Tick &amp; Flea Prevention · Cadence</div>
          <div style={cardHeadline}>10 doses given. Two critical gaps in 2024–25.</div>
          <div style={{ ...cardSub, marginBottom: 0 }}>Target: every 4 weeks · <span style={{ color: 'var(--red)', fontWeight: 600 }}>Longest gap: 16 weeks</span></div>
          <svg viewBox="0 0 358 152" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block', marginTop: 12 }}>
            <line x1="14" y1="68" x2="344" y2="68" stroke="#E8E4DF" strokeWidth="2.5" strokeLinecap="round"/>
            <text x="137" y="24" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#FF3B30">15w gap</text>
            <line x1="115" y1="28" x2="115" y2="54" stroke="#FF3B30" strokeWidth="0.8" strokeDasharray="2 2"/>
            <line x1="160" y1="28" x2="160" y2="54" stroke="#FF3B30" strokeWidth="0.8" strokeDasharray="2 2"/>
            <line x1="115" y1="28" x2="160" y2="28" stroke="#FF3B30" strokeWidth="0.8"/>
            <text x="183" y="14" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fontWeight="600" fill="#FF3B30">16w gap</text>
            <line x1="160" y1="18" x2="160" y2="54" stroke="#FF3B30" strokeWidth="0.8" strokeDasharray="2 2"/>
            <line x1="207" y1="18" x2="207" y2="54" stroke="#FF3B30" strokeWidth="0.8" strokeDasharray="2 2"/>
            <line x1="160" y1="18" x2="207" y2="18" stroke="#FF3B30" strokeWidth="0.8"/>
            <text x="24"  y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">7w</text>
            <text x="48"  y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">9w</text>
            <text x="78"  y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">11w</text>
            <text x="105" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">7w</text>
            <text x="222" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">10w</text>
            <text x="252" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#8A8A8A">10w</text>
            <text x="286" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#FF9500">13w</text>
            <text x="324" y="50" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill="#FF9500">13w</text>
            {[
              { cx: 14, n: 1, fill: '#34C759' }, { cx: 35, n: 2, fill: '#FF9500' }, { cx: 62, n: 3, fill: '#FF9500' },
              { cx: 94, n: 4, fill: '#FF9500' }, { cx: 115, n: 5, fill: '#FF9500' }, { cx: 160, n: 6, fill: '#FF3B30' },
              { cx: 207, n: 7, fill: '#FF3B30' }, { cx: 237, n: 8, fill: '#FF9500' }, { cx: 267, n: 9, fill: '#FF9500' },
              { cx: 305, n: 10, fill: '#FF9500' },
            ].map(d => (
              <g key={d.n}>
                <circle cx={d.cx} cy="68" r="10" fill={d.fill} stroke="white" strokeWidth="2"/>
                <text x={d.cx} y="72" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize={d.n===10?7:8} fontWeight="700" fill="white">{d.n}</text>
              </g>
            ))}
            <circle cx="344" cy="68" r="10" fill="none" stroke="#8A8A8A" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="344" y="72" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#8A8A8A">?</text>
            {[
              [14,'Dec\'23','#8A8A8A'],[35,'Jan','#8A8A8A'],[62,'Mar','#8A8A8A'],[94,'Jun','#8A8A8A'],
              [115,'Aug','#8A8A8A'],[160,'Nov','#FF3B30'],[207,'Mar\'25','#FF3B30'],[237,'May','#8A8A8A'],
              [267,'Jul','#8A8A8A'],[305,'Oct','#8A8A8A'],[344,'Next','#8A8A8A'],
            ].map(([x,lbl,color]) => (
              <text key={lbl} x={x} y="92" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="8" fill={color}>{lbl}</text>
            ))}
            <circle cx="14"  cy="118" r="6" fill="#34C759"/>
            <text x="26" y="122" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">≤6w on time</text>
            <circle cx="108" cy="118" r="6" fill="#FF9500"/>
            <text x="120" y="122" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">7–12w delayed</text>
            <circle cx="218" cy="118" r="6" fill="#FF3B30"/>
            <text x="230" y="122" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">&gt;12w critical</text>
            <circle cx="14"  cy="138" r="6" fill="none" stroke="#8A8A8A" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="26" y="142" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">upcoming</text>
          </svg>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 600, padding: '5px 11px', borderRadius: 20, marginTop: 14, background: 'var(--ta)', color: '#9a5800' }}>⚠ Gaps coincide with Anaplasma reactivation</div>
        </div>

        {/* Deworming */}
        <div style={card}>
          <div style={cardLabel('#9B59B6')}>🐛 &nbsp;Deworming · Cadence</div>
          <div style={cardHeadline}>Only 1 dose in 2+ years. Significantly overdue.</div>
          <div style={{ ...cardSub, marginBottom: 0 }}><span style={{ color: 'var(--red)', fontWeight: 600 }}>All doses from Jan 2024 onwards missed</span></div>
          <svg viewBox="0 0 358 108" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', display: 'block', marginTop: 12 }}>
            <line x1="18" y1="44" x2="342" y2="44" stroke="#E8E4DF" strokeWidth="2.5" strokeLinecap="round"/>
            <circle cx="18" cy="44" r="11" fill="#34C759" stroke="white" strokeWidth="2"/>
            <text x="18" y="49" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="12" fill="white">✓</text>
            <text x="18" y="68" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#1A1A1A" fontWeight="600">Oct '23</text>
            {[[64,"Jan '24"],[110,"Apr"],[156,"Jul"],[203,"Oct"],[249,"Jan '25"],[295,"Apr"]].map(([cx,lbl]) => (
              <g key={lbl}>
                <circle cx={cx} cy="44" r="10" fill="none" stroke="#FF3B30" strokeWidth="1.5" strokeDasharray="3 2"/>
                <text x={cx} y="49" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="11" fill="#FF3B30">×</text>
                <text x={cx} y="68" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#8A8A8A">{lbl}</text>
              </g>
            ))}
            <circle cx="342" cy="44" r="10" fill="none" stroke="#FF9500" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="342" y="49" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="10" fill="#FF9500">!</text>
            <text x="342" y="68" textAnchor="middle" fontFamily="Inter,sans-serif" fontSize="9" fill="#FF9500" fontWeight="600">Now</text>
            <circle cx="18"  cy="90" r="6" fill="#34C759"/>
            <text x="30" y="94" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">Done</text>
            <circle cx="84" cy="90" r="6" fill="none" stroke="#FF3B30" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="96" y="94" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">Missed (6 doses)</text>
            <circle cx="224" cy="90" r="6" fill="none" stroke="#FF9500" strokeWidth="1.5" strokeDasharray="3 2"/>
            <text x="236" y="94" fontFamily="Inter,sans-serif" fontSize="10" fill="#4A4A4A">Administer now</text>
          </svg>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 600, padding: '5px 11px', borderRadius: 20, marginTop: 14, background: 'var(--tr)', color: '#b52020' }}>🚨 Administer immediately</div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 24, fontSize: 11, color: 'var(--t3)' }}>
          Zayn · Health Trends v11 · Nov 2023 – Oct 2025
        </div>
      </div>

      <button className="floater fl-home" onClick={onBack}>🏠</button>
    </>
  );
};


const RECORDS = [
  { id: 'r1', icon: '🩸', type: 'Lab Report', title: 'Blood Panel – Sep 2025', date: '10 Sep 2025', tag: 'Platelets low', tagColor: '#FF3B30', tagBg: '#FFF0F0' },
  { id: 'r2', icon: '💧', type: 'Lab Report', title: 'Urine Culture – Oct 2025', date: '22 Oct 2025', tag: 'E. coli +ve', tagColor: '#FF3B30', tagBg: '#FFF0F0' },
  { id: 'r3', icon: '🩺', type: 'Vet Visit', title: 'Consultation – 06 May 2025', date: '06 May 2025', tag: 'Vaccines done', tagColor: '#1e8c3a', tagBg: '#F0FFF4' },
  { id: 'r4', icon: '🧬', type: 'Lab Report', title: 'SNAP 4Dx – Feb 2025', date: '12 Feb 2025', tag: 'Anaplasma +ve', tagColor: '#9B59B6', tagBg: '#F5EEF8' },
  { id: 'r5', icon: '💧', type: 'Lab Report', title: 'Urinalysis – Feb 2025', date: '26 Feb 2025', tag: 'Near clear', tagColor: '#1e8c3a', tagBg: '#F0FFF4' },
  { id: 'r6', icon: '🩸', type: 'Lab Report', title: 'CBC Panel – Jan 2025', date: '14 Jan 2025', tag: 'Platelets 156K', tagColor: '#FF6B35', tagBg: '#FFF3EE' },
  { id: 'r7', icon: '🩺', type: 'Vet Visit', title: 'UTI Follow-up – Nov 2024', date: '18 Nov 2024', tag: 'Augmentin prescribed', tagColor: '#FF6B35', tagBg: '#FFF3EE' },
  { id: 'r8', icon: '💧', type: 'Lab Report', title: 'Urine R/E – Nov 2024', date: '05 Nov 2024', tag: 'Pus cells 1–2', tagColor: '#FF9F1C', tagBg: '#FFF6ED' },
  { id: 'r9', icon: '🩸', type: 'Lab Report', title: 'Blood Panel – Feb 2025', date: '22 Feb 2025', tag: 'Platelets 222K', tagColor: '#1e8c3a', tagBg: '#F0FFF4' },
  { id: 'r10', icon: '🧬', type: 'Lab Report', title: 'Q-PCR – Nov 2023', date: '10 Nov 2023', tag: 'Anaplasma CT 22.1', tagColor: '#9B59B6', tagBg: '#F5EEF8' },
  { id: 'r11', icon: '💧', type: 'Lab Report', title: 'Urine Culture – Dec 2023', date: '12 Dec 2023', tag: 'Pus cells 7–8', tagColor: '#FF3B30', tagBg: '#FFF0F0' },
  { id: 'r12', icon: '🩺', type: 'Vet Visit', title: 'Annual Check-up – May 2024', date: '14 May 2024', tag: 'Routine', tagColor: '#8A8A8A', tagBg: '#F7F4F0' },
  { id: 'r13', icon: '🏥', type: 'Imaging', title: 'Abdominal USG – Mar 2024', date: '20 Mar 2024', tag: 'All clear', tagColor: '#1e8c3a', tagBg: '#F0FFF4' },
  { id: 'r14', icon: '💬', type: 'WhatsApp Chat', title: 'Owner Chat Log – Oct 2025', date: '28 Oct 2025', tag: 'Symptom history', tagColor: '#FF9F1C', tagBg: '#FFF6ED' },
];

const VET_VISITS = [
  {
    id: 'v1',
    title: 'Consultation – 06 May 2025',
    date: '06 May 2025',
    tag: 'Vaccines done',
    tagColor: '#1e8c3a',
    tagBg: '#F0FFF4',
    rx: 'Nobivac DHPPi · Nobivac RL · Nobivac KC · CCoV',
    medications: [
      { name: 'Nobivac DHPPi', dose: '1 vial SC', duration: 'Annual' },
      { name: 'Nobivac RL (Rabies + Lepto)', dose: '1 vial SC', duration: 'Annual' },
      { name: 'Nobivac KC (Kennel Cough)', dose: '1 vial intranasal', duration: 'Annual' },
      { name: 'Nobivac CCoV', dose: '1 vial SC', duration: 'Annual' },
    ],
    notes: 'All vaccinations current. Weight 30 kg. No concerns raised.',
  },
  {
    id: 'v2',
    title: 'UTI Follow-up – Nov 2024',
    date: '18 Nov 2024',
    tag: 'Augmentin prescribed',
    tagColor: '#FF6B35',
    tagBg: '#FFF3EE',
    rx: 'Augmentin 625 mg · Urine culture ordered',
    medications: [
      { name: 'Augmentin 625 mg (Amoxicillin + Clavulanate)', dose: '1 tablet twice daily', duration: '10 days' },
    ],
    notes: 'Pus cells 1–2 HPF. E. coli growth on culture. Post-antibiotic culture recommended but not submitted.',
  },
  {
    id: 'v3',
    title: 'Annual Check-up – May 2024',
    date: '14 May 2024',
    tag: 'Routine',
    tagColor: '#8A8A8A',
    tagBg: '#F7F4F0',
    rx: 'No medications prescribed',
    medications: [],
    notes: 'Routine annual exam. All vitals normal. Deworming discussed but not administered.',
  },
];

const VetVisitCard = ({ visit, defaultOpen }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card" style={{ marginBottom: 8, padding: 0, overflow: 'hidden' }}>
      {/* Header row — always visible */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', cursor: 'pointer' }}
      >
        <div style={{ width: 40, height: 40, borderRadius: 12, background: 'var(--to)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>🩺</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginBottom: 3, lineHeight: 1.3 }}>{visit.title}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: 'var(--t3)' }}>{visit.date}</span>
            <span style={{ fontSize: 10, color: 'var(--t3)' }}>·</span>
            <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 20, background: visit.tagBg, color: visit.tagColor }}>{visit.tag}</span>
          </div>
        </div>
        <span style={{ fontSize: 13, color: 'var(--t3)', flexShrink: 0, transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s', display: 'inline-block' }}>›</span>
      </div>

      {/* Expanded content */}
      {open && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '12px 14px', background: 'var(--warm)' }}>
          {/* Rx summary */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--t3)', marginBottom: 4 }}>Rx / Prescription</div>
            <div style={{ fontSize: 12, color: 'var(--t2)', background: 'var(--to)', borderRadius: 8, padding: '7px 10px', fontWeight: 500 }}>{visit.rx}</div>
          </div>

          {/* Medications table */}
          {visit.medications.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--t3)', marginBottom: 6 }}>Medications</div>
              {visit.medications.map((m, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '8px 0', borderBottom: i < visit.medications.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>{m.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--t3)' }}>{m.dose} · {m.duration}</div>
                </div>
              ))}
            </div>
          )}

          {/* Notes */}
          {visit.notes && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--t3)', marginBottom: 4 }}>Notes</div>
              <div style={{ fontSize: 12, color: 'var(--t2)', lineHeight: 1.5 }}>{visit.notes}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const RecordsView = ({ pet, onBack }) => {
  const types = ['Vet Visit', 'Lab Report', 'Imaging', 'WhatsApp Chat'];
  const [filter, setFilter] = useState('Vet Visit');
  const labAndOther = RECORDS.filter(r => r.type !== 'Vet Visit');
  const filtered = labAndOther.filter(r => r.type === filter);

  return (
    <>
      <div className="vh">
        <button className="back-btn" onClick={onBack}>←</button>
        <span className="vh-title">{pet.name}'s Health Records</span>
      </div>
      <div style={{ marginBottom: 12 }}>
        <div className="nscroll">
          <div className="npills" style={{ paddingBottom: 4 }}>
            {types.map(t => (
              <button key={t} className={`npill${filter === t ? ' active' : ''}`} onClick={() => setFilter(t)}>{t}</button>
            ))}
          </div>
        </div>
      </div>

      {filter === 'Vet Visit' ? (
        <>
          <div style={{ fontSize: 12, color: 'var(--t3)', marginBottom: 10, fontWeight: 500 }}>{VET_VISITS.length} visit{VET_VISITS.length !== 1 ? 's' : ''}</div>
          {VET_VISITS.map((visit, i) => (
            <VetVisitCard
              key={visit.id}
              visit={visit}
              defaultOpen={i === 0 || i === VET_VISITS.length - 1}
            />
          ))}
        </>
      ) : (
        <>
          <div style={{ fontSize: 12, color: 'var(--t3)', marginBottom: 10, fontWeight: 500 }}>{filtered.length} document{filtered.length !== 1 ? 's' : ''}</div>
          {filtered.map(r => (
            <div key={r.id} className="card" style={{ marginBottom: 8, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 12, background: 'var(--to)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>{r.icon}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginBottom: 3, lineHeight: 1.3 }}>{r.title}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: 'var(--t3)' }}>{r.date}</span>
                  <span style={{ fontSize: 10, color: 'var(--t3)' }}>·</span>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 20, background: r.tagBg, color: r.tagColor }}>{r.tag}</span>
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--t3)', fontWeight: 500, flexShrink: 0 }}>View →</div>
            </div>
          ))}
        </>
      )}

      <button className="floater fl-home" onClick={onBack}>🏠</button>
    </>
  );
};

const App = () => {
  const [view, setView] = useState('dashboard');
  const [cart, setCart] = useState([]);
  const pet = PET_DATA;

  const addToCart = (item) => {
    setCart(prev => {
      const exists = prev.find(c => c.id === item.id);
      if (exists) return prev.map(c => c.id === item.id ? { ...c, qty: c.qty + 1 } : c);
      return [...prev, { id: item.id, name: item.name, sku: item.sku, price: item.price, icon: item.icon || '📦', section: pet.carePlan.find(s => s.items.some(i => i.id === item.id))?.section || '', qty: 1 }];
    });
  };

  const updateQty = (id, qty) => setCart(prev => prev.map(c => c.id === id ? { ...c, qty } : c));
  const removeItem = (id) => setCart(prev => prev.filter(c => c.id !== id));

  return (
    <div className="app">
      <GlobalStyles />
      {view === 'dashboard' && <DashboardView pet={pet} cart={cart} onAddToCart={addToCart} onGoToCart={() => setView('cart')} onGoToTrends={() => setView('trends')} onGoToReminders={() => setView('reminders')} onGoToRecords={() => setView('records')} />}
      {view === 'reminders' && <RemindersView pet={pet} onBack={() => setView('dashboard')} />}
      {view === 'cart' && <CartView pet={pet} cart={cart} onUpdateQty={updateQty} onRemove={removeItem} onBack={() => setView('dashboard')} onNext={() => setView('checkout')} />}
      {view === 'checkout' && <CheckoutView cart={cart} onBack={() => setView('cart')} onPlace={() => setView('confirm')} />}
      {view === 'confirm' && <ConfirmView cart={cart} onDone={() => { setCart([]); setView('dashboard'); }} />}
      {view === 'trends' && <HealthTrendsView pet={pet} onBack={() => setView('dashboard')} />}
      {view === 'records' && <RecordsView pet={pet} onBack={() => setView('dashboard')} />}
    </div>
  );
};

export default App;
