import { useState, useEffect, useRef, useCallback, useMemo } from "react";

// ─── CONSTANTS & THEME ────────────────────────────────────────────────────────
// Extracted outside components so they are never recreated on render

const BRAND_PRIMARY = "#D44800";

const PRI_CFG = {
  urgent: { bg:"#FFF0F0", border:"#FF3B30", badge:"#FF3B30", label:"URGENT" },
  high:   { bg:"#FFF6ED", border:"#FF9500", badge:"#FF9500", label:"ACTION NEEDED" },
  medium: { bg:"#FFFBEA", border:"#FFCC00", badge:"#B8860B", label:"RECOMMENDED" },
};

const ST_CFG = {
  overdue:  { color:"#FF3B30", bg:"#FFF0F0", label:"Overdue"    },
  upcoming: { color:"#FF9500", bg:"#FFF6ED", label:"Due Soon"   },
  done:     { color:"#34C759", bg:"#F0FFF4", label:"Up to Date" },
  missing:  { color:"#8E8E93", bg:"#F2F2F7", label:"No Record"  },
  managed:  { color:"#007AFF", bg:"#F0F6FF", label:"Managed"    },
  urgent:   { color:"#FF3B30", bg:"#FFF0F0", label:"Refill Now" },
  ok:       { color:"#34C759", bg:"#F0FFF4", label:"Adequate"   },
  Low:      { color:"#FF9500", bg:"#FFF6ED", label:"Low"        },
  Missing:  { color:"#FF3B30", bg:"#FFF0F0", label:"Missing"    },
  Adequate: { color:"#34C759", bg:"#F0FFF4", label:"Adequate"   },
};

// Lookup tables replace repeated ternary chains throughout the file
const STATUS_COLOR = { overdue:"#FF3B30", missing:"#FF3B30", upcoming:"#FF9500", done:"#34C759" };
const STATUS_BG    = { overdue:"#FFF0F0", missing:"#FFF0F0", upcoming:"#FFF6ED", done:"#F0FFF4" };
const STATUS_LABEL = { overdue:"Overdue", missing:"No Record", upcoming:"Due Soon", done:"Up to date" };

const WA_REMINDER_COLORS = { upcoming:"#FF9500", due:"#D44800", overdue:"#FF3B30" };
const WA_REMINDER_BG     = { upcoming:"#FFF6ED", due:"#FFF3EE", overdue:"#FFF0F0" };
const WA_REMINDER_LABELS = { upcoming:"1 WEEK BEFORE", due:"DUE TODAY", overdue:"OVERDUE" };

// ─── DATA ─────────────────────────────────────────────────────────────────────

const mockPetData = {
  name:"Zayn", breed:"Labrador", dob:"Nov 2021",
  gender:"Male (neutered)", pincode:"400016", parent:"Ashita Arora",
  healthRecords: {
    vaccines: [
      { id:"dhppi",       name:"DHPPi (Nobivac DHPPi)",         mandatory:true,  freqMonths:12, lastGiven:"06/05/2025" },
      { id:"rabies",      name:"Rabies (Nobivac RL)",            mandatory:true,  freqMonths:12, lastGiven:"06/05/2025" },
      { id:"kennelcough", name:"Kennel Cough (Nobivac KC)",      mandatory:false, freqMonths:12, lastGiven:"06/05/2025" },
      { id:"ccov",        name:"Canine Coronavirus (CCoV)",      mandatory:false, freqMonths:12, lastGiven:"06/05/2025" },
    ],
    deworming: { lastDone:null, nextDue:null, status:"missing" },
    fleaTick:  { lastDone:null, nextDue:null, status:"missing" },
    checkups:  [{ name:"Annual Wellness Exam", lastDone:"10/09/2025", nextDue:"10/09/2026", status:"done" }],
    grooming: [
      { name:"Bath & Brush",    icon:"🛁", lastDone:"Not recorded", nextDue:"Overdue",     freq:"Monthly",     status:"missing", note:"Labradors shed heavily — monthly baths control shedding and skin health." },
      { name:"Nail Trimming",   icon:"✂️", lastDone:"Not recorded", nextDue:"Overdue",     freq:"Every 6 wks", status:"missing", note:"Overgrown nails alter gait and stress joints." },
      { name:"Dental Cleaning", icon:"🦷", lastDone:null,           nextDue:null,           freq:"Annually",    status:"missing", note:"Labradors are tartar-prone. Annual vet cleaning prevents gum disease." },
      { name:"Ear Cleaning",    icon:"👂", lastDone:"Not recorded", nextDue:"Recommended", freq:"Every 6 wks", status:"missing", note:"Floppy Labrador ears trap moisture — key to preventing ear infections." },
      { name:"Eye Wipe",        icon:"👁️", lastDone:"Not recorded", nextDue:"Recommended", freq:"Monthly",     status:"missing", note:"Prevents discharge buildup common in Labradors." },
    ],
    conditions: [
      {
        name:"Recurring UTI — E. coli (Not fully cleared)", icon:"🦠", diagnosedOn:"Dec 2023",
        managedBy:"Dr. Makarand Chavan, Dadar", status:"unknown",
        medications: [
          { name:"Augmentin Duo 375", dose:"1 tab twice daily × 5 days with food",  refillDue:"Completed", refillStatus:"done", price:"₹180", orderable:false },
          { name:"Cystone",           dose:"1 tab twice daily × 15 days with food", refillDue:"Completed", refillStatus:"done", price:"₹220", orderable:false },
          { name:"Dompan",            dose:"1 tab twice daily × 5 days with food",  refillDue:"Completed", refillStatus:"done", price:"₹120", orderable:false },
        ],
        monitoringChecks: [
          { name:"Repeat Urine Culture",         nextDue:"Oct 2025", status:"overdue", source:"vet",       sourceNote:"Prescribed by Dr. Chavan post-Augmentin to confirm E. coli clearance" },
          { name:"Urinalysis + Pus Cell Check",  nextDue:"Jan 2026", status:"overdue", source:"petcircle", sourceNote:"PetCircle recommendation — pus cells 2–3/hpf still present in Oct 2025, Zayn still symptomatic" },
        ],
        notes:"3 episodes: Dec 2023, Nov 2024, Sep 2025. Treatment completed Sep 2025 — 5-day Augmentin likely too short. Oct 2025 urine improved (no crystals, no blood) but pus cells unchanged and frequent urination persists. No post-antibiotic culture done. Status: not confirmed cleared.",
      },
      {
        name:"Anaplasma platys — Tick Bacteria (Never Treated)", icon:"🩸", diagnosedOn:"Nov 2023",
        managedBy:"Dr. Atul Patil · ChromoXpert, Navi Mumbai", status:"unknown",
        medications: [],
        monitoringChecks: [
          { name:"Q-PCR Retest — Anaplasma platys",  nextDue:"Overdue", status:"overdue", source:"petcircle", sourceNote:"PCR confirmed significant load (CT 22.1) in Nov 2023. Never treated. No repeat test in 2+ years. Cyclic thrombocytopenia consistent with untreated Anaplasma." },
          { name:"Manual Platelet Count (CBC)",       nextDue:"Overdue", status:"overdue", source:"petcircle", sourceNote:"PetCircle recommendation — platelets low in almost every test since 2023. Always request manual count — automated consistently under-reads Zayn's." },
          { name:"Start Monthly Tick Prevention",     nextDue:"Now",     status:"overdue", source:"petcircle", sourceNote:"Anaplasma platys is tick-transmitted. Monthly oral or spot-on tick prevention is the most impactful single step given Zayn's history." },
        ],
        notes:"Anaplasma platys confirmed by PCR (CT 22.1) — Nov 2023 at ChromoXpert. Hepatozoon canis also borderline (CT 34.0). Cyclic platelet pattern since Nov 2023: 178K → 156K → 252K (recovered) → 160K. Specific cause of recurring thrombocytopenia. Never treated. No PCR repeat in 2+ years.",
      },
    ],
    nutrition: {
      currentFood: { brand:"Not recorded", type:"Unknown", portionG:0, mealsPerDay:2 },
      supplements: [],
      homemade: [],
      breedGaps: [
        { nutrient:"Probiotics",  level:"Missing", reason:"UTI history and antibiotic course deplete gut flora. Probiotics critical for Labradors prone to digestive issues.", supplement:"FortiFlora Probiotic",   priority:"urgent", orderable:true,  price:"₹649/mo" },
        { nutrient:"Cranberry",   level:"Missing", reason:"Supports urinary tract health — reduces E. coli adhesion. Relevant given UTI history and ongoing urinary symptoms.", supplement:"Cran-Max / UTI Guard",   priority:"urgent", orderable:true,  price:"₹499/mo" },
        { nutrient:"Omega-3",     level:"Missing", reason:"Anti-inflammatory; supports bladder wall health and Labrador joint health. No supplement on record.",                supplement:"Salmon Oil / Omega-3",   priority:"high",   orderable:true,  price:"₹349/mo" },
        { nutrient:"Vitamin C",   level:"Low",     reason:"Acidifies urine, which may reduce crystal formation and UTI recurrence. Labradors benefit from antioxidant support.",supplement:"Vit C 500mg",            priority:"medium", orderable:true,  price:"₹199/mo" },
        { nutrient:"Zinc",        level:"Low",     reason:"Supports immune function and skin coat health in Labradors. No current supplement recorded.",                        supplement:"Zinc supplement",        priority:"medium", orderable:true,  price:"₹249/mo" },
        { nutrient:"Protein",     level:"Missing", reason:"Current diet not recorded — cannot assess protein adequacy. Please add diet information.",                           supplement:null,                     priority:"ok",     orderable:false, price:null },
      ],
    },
  },
};

const whatsappReminders = [
  { id:"r1", type:"anaplasma",  daysOut:-730, status:"overdue", icon:"🔬", title:"🚨 Anaplasma platys PCR retest — 2 years overdue",  body:"Hi Ashita 🐾 Zayn's Anaplasma platys was confirmed by PCR in Nov 2023 (significant load) and has never been treated or retested. This is the most likely cause of his recurring low platelets. Please request a PCR-based test specifically — microscopy won't find it.", actions:[{label:"🏠 Book Home Lab — PCR Panel",color:"#FF3B30"},{label:"📍 Find ChromoXpert / Lab",color:"#075E54"}] },
  { id:"r2", type:"culture",    daysOut:-150, status:"overdue", icon:"🧫", title:"🚨 Urine culture overdue — Zayn still symptomatic", body:"Hi Ashita 🐾 Dr. Chavan prescribed a repeat urine culture after Augmentin to confirm E. coli clearance. This is now 5+ months overdue. Zayn is still urinating indoors. A culture (not routine urinalysis) is needed to check if E. coli is still present.", actions:[{label:"🏠 Book Home Lab Visit",color:"#FF3B30"},{label:"📍 Find Lab Nearby",color:"#075E54"}] },
  { id:"r3", type:"platelets",  daysOut:-90,  status:"overdue", icon:"🩸", title:"Manual platelet count due for Zayn",                body:"Hi Ashita 🐾 Zayn's platelets have been low in almost every test since 2023. PetCircle recommends a CBC every 6 months — always request manual platelet count specifically. Automated counts consistently under-read Zayn's results.", actions:[{label:"🏠 Book Home Lab — CBC",color:"#FF9500"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
  { id:"r4", type:"tick",       daysOut:0,    status:"due",     icon:"🐛", title:"Monthly tick prevention due for Zayn",              body:"Hi Ashita 🐾 Tick prevention is due this month. Given Zayn's confirmed Anaplasma platys history, monthly tick prevention is the most important ongoing protective step. Don't skip.", actions:[{label:"🛒 Order NexGard — ₹420",color:"#FF9500"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
  { id:"r5", type:"deworming",  daysOut:0,    status:"due",     icon:"🪱", title:"No deworming record found for Zayn",                body:"Hi Ashita 🐾 Zayn has no deworming record on file. Labradors should be dewormed every 3 months. Given his immune history, parasite control is especially important.", actions:[{label:"🛒 Order Drontal Plus — ₹189",color:"#FF9500"},{label:"📍 Find Vet Nearby",color:"#075E54"}] },
];

const nudges = [
  { id:1,  cat:"condition",  pri:"urgent", icon:"🔬", title:"Q-PCR Retest — Anaplasma platys",    msg:"Anaplasma platys confirmed by PCR in Nov 2023 (CT 22.1) — never treated. Likely cause of recurring low platelets. PCR test specifically required — microscopy misses it.", mandatory:true,  orderable:true, price:"₹1499", orderType:"homeVet"   },
  { id:2,  cat:"condition",  pri:"urgent", icon:"🧫", title:"Urine Culture (not routine urine test)", msg:"Zayn is still symptomatic. A culture confirms whether E. coli is still present and whether resistance has shifted. Routine urinalysis alone won't answer this.", mandatory:true, orderable:true, price:"₹499", orderType:"homeVet"  },
  { id:3,  cat:"condition",  pri:"urgent", icon:"🐛", title:"Start Monthly Tick Prevention",       msg:"Anaplasma platys is tick-transmitted. Monthly oral or spot-on tick prevention is the single most impactful step given Zayn's 2-year history with this pathogen.", mandatory:true, orderable:true, price:"₹420", orderType:"medicine" },
  { id:4,  cat:"condition",  pri:"urgent", icon:"🩸", title:"Manual Platelet Count (CBC)",         msg:"Platelets low in almost every test since 2023. Always request manual count — automated consistently under-reads Zayn's platelets.", mandatory:true,  orderable:true, price:"₹599", orderType:"homeVet"  },
  { id:5,  cat:"nutrition",  pri:"urgent", icon:"🦠", title:"Probiotics Missing — Post-UTI",       msg:"Augmentin depletes gut flora significantly. Probiotic course strongly recommended post-antibiotic treatment.", mandatory:true,  orderable:true, price:"₹649", orderType:"supplement"},
  { id:6,  cat:"deworming",  pri:"high",   icon:"🪱", title:"No Deworming Record",                 msg:"No deworming on file for Zayn. Essential every 3 months — supports immunity alongside Anaplasma management.", mandatory:true, orderable:true, price:"₹189", orderType:"medicine" },
  { id:7,  cat:"nutrition",  pri:"high",   icon:"🫐", title:"Urinary Support Supplement Missing",  msg:"Cranberry/urinary supplement reduces E. coli adhesion to bladder wall — relevant given 3 UTI episodes.", mandatory:false, orderable:true, price:"₹499", orderType:"supplement"},
  { id:8,  cat:"nutrition",  pri:"high",   icon:"🐟", title:"Omega-3 Not on Record",               msg:"Supports bladder wall integrity and reduces inflammation. No supplement recorded.", mandatory:false, orderable:true, price:"₹349", orderType:"supplement"},
  { id:9,  cat:"grooming",   pri:"high",   icon:"🛁", title:"No Grooming Records Found",           msg:"No grooming history on file. Labradors need monthly baths and regular nail trims. Ear cleaning critical given UTI/tick history.", mandatory:false, orderable:true, price:"₹799", orderType:"grooming" },
  { id:10, cat:"nutrition",  pri:"medium", icon:"🍊", title:"Vitamin C — Urinary Support",         msg:"Vitamin C acidifies urine, reducing crystal formation. Relevant given Zayn's triple phosphate crystal history.", mandatory:false, orderable:true, price:"₹199", orderType:"supplement"},
];

// Moved outside CartStep — never changes
const cartItemsData = [
  { id:"c1",  icon:"🔬", name:"Q-PCR — Anaplasma platys",         sub:"Most critical unresolved question — PCR only, not microscopy",  price:1499, tag:"CRITICAL",     tagColor:"#FF3B30", inCart:true  },
  { id:"c2",  icon:"🧫", name:"Home Lab — Urine Culture",          sub:"E. coli clearance confirmation — still symptomatic",           price:499,  tag:"OVERDUE",      tagColor:"#FF3B30", inCart:true  },
  { id:"c3",  icon:"🩸", name:"Home Lab — CBC / Manual Platelet",  sub:"Always manual — automated under-reads Zayn's count",           price:599,  tag:"OVERDUE",      tagColor:"#FF3B30", inCart:true  },
  { id:"c4",  icon:"🐛", name:"Boehringer NexGard",                sub:"Monthly tick prevention — Anaplasma is tick-transmitted",      price:420,  tag:"URGENT",       tagColor:"#FF3B30", inCart:true  },
  { id:"c5",  icon:"🦠", name:"Purina FortiFlora Probiotic",       sub:"Post-antibiotic gut recovery — urgent",                        price:649,  tag:"URGENT",       tagColor:"#FF3B30", inCart:true  },
  { id:"c6",  icon:"🫐", name:"Cran-Max Urinary Support",          sub:"UTI prevention — 3 episodes, E. coli adhesion reduction",      price:499,  tag:"RECOMMENDED",  tagColor:"#FF9500", inCart:false },
  { id:"c7",  icon:"🪱", name:"Bayer Drontal Plus",                sub:"Deworming — no record on file",                                price:189,  tag:"NO RECORD",    tagColor:"#FF9500", inCart:false },
  { id:"c8",  icon:"🐟", name:"Salmon Oil Omega-3",                sub:"Bladder wall integrity + anti-inflammatory",                   price:349,  tag:"MISSING",      tagColor:"#FF9500", inCart:false },
  { id:"c9",  icon:"🛁", name:"Home Grooming Session",             sub:"Bath, brush & nail trim — no records",                         price:799,  tag:"NO RECORD",    tagColor:"#FF9500", inCart:false },
  { id:"c10", icon:"🍊", name:"Vitamin C 500mg",                   sub:"Urine acidifier — crystal prevention",                         price:199,  tag:"RECOMMENDED",  tagColor:"#B8860B", inCart:false },
  { id:"c11", icon:"🏠", name:"Home Vet — Specialist Follow-up",   sub:"Review Anaplasma + UTI status with vet",                       price:799,  tag:"FOLLOW-UP",    tagColor:"#007AFF", inCart:false },
];

// WhatsApp conversation — outside component, never recreated
const WHATSAPP_CONV = [
  { from:"bot",  text:"Hi Ashita! 🐾 Welcome to *PetCircle* — India's first preventive pet health platform. Let's build Zayn's complete health profile.", delay:600 },
  { from:"user", text:"Hi! Yes please 😊", delay:0 },
  { from:"bot",  text:"Perfect! Share a *photo of Zayn* and his *name*.", delay:800 },
  { from:"user", text:"📷 Zayn.jpg  |  His name is Zayn!", delay:0 },
  { from:"bot",  text:"What a handsome Lab! 😍 What's Zayn's *breed*, *date of birth*, and *gender*?", delay:700 },
  { from:"user", text:"Labrador, Nov 2021, male neutered", delay:0 },
  { from:"bot",  text:"Got it. And your *pincode*? Helps us find nearby vets and labs.", delay:700 },
  { from:"user", text:"400016", delay:0 },
  { from:"bot",  text:"Great! Upload Zayn's *vaccination cards, prescriptions, or health records*. Multiple photos welcome!", delay:800 },
  { from:"user", text:"📎 Zayn_Vaccination_Record_1.jpg\n📎 Zayn_Vaccination_Record_2.jpg\n📎 Prescription_Chavan_12_02_25.jpg\n📎 ZAYN_BLOOD_REPORT_sep25.pdf\n📎 zayn_urine_sep25.pdf\n📎 Zayn_UrineCulture_sep25.pdf\n📎 Zayn_usg_report_sep25.pdf\n📎 Zayn_x-ray_report_sep25.pdf\n📎 zayn_urine_Oct25.pdf", delay:0 },
  { from:"bot",  text:"🤖 *Analysing Zayn's records...*\n\nParsing records · Mapping lab values · Building care plan", delay:1200, isProcessing:true },
  { from:"bot",  text:"✅ Profile complete!\n\n• All 4 vaccines current (Jun 2025)\n• UTI — E. coli detected Sep 2025, treatment completed\n• *3 urgent follow-ups* overdue\n• Thrombocytopenia flagged (Plt 160)\n• No deworming or flea/tick records found\n\nOpening Zayn's Health Dashboard →", delay:2000 },
];

const PROCESSING_TASKS = [
  "Reading vaccination records...", "Parsing blood report (CBC)...", "Extracting urine analysis (Sep)...",
  "Parsing urine culture report...", "Reading Oct urinalysis...", "Extracting USG & X-ray reports...",
  "Parsing prescription (Dr. Chavan)...", "Identifying follow-up actions...", "Profile ready ✓",
];

const DASHBOARD_TABS = [["overview","Overview"],["medical","Health"],["grooming","Hygiene"],["nutrition","Nutrition"],["conditions","Conditions"]];

const DAILY_HYGIENE_ITEMS = [
  { id:"coat-brush",  icon:"🪮", name:"Coat Brushing",  note:"Labradors shed year-round — daily brushing significantly reduces loose fur and skin issues.",  lastDone:"Not recorded", status:"missing" },
  { id:"teeth-brush", icon:"🦷", name:"Teeth Brushing", note:"Daily brushing prevents tartar buildup and gum disease. Labs are prone to dental issues.",       lastDone:"Not recorded", status:"missing" },
  { id:"ear-clean",   icon:"👂", name:"Ear Cleaning",   note:"Floppy Labrador ears trap moisture and are prone to infection — clean every 6 weeks.",            lastDone:"Not recorded", status:"missing" },
  { id:"eye-wipe",    icon:"👁️", name:"Eye Wipe",       note:"Prevents discharge buildup around the eyes, common in Labradors.",                               lastDone:"Not recorded", status:"missing" },
];

const PERIODIC_HYGIENE_ITEMS = [
  { id:"bath-nail",  icon:"🛁", name:"Bath, brush & nail trim", note:"Monthly baths manage Labrador shedding and skin oils. Nail trims prevent joint stress and gait problems.", lastDone:"Not recorded", status:"missing" },
  { id:"anal-gland", icon:"🐾", name:"Anal gland cleaning",     note:"Prevents impaction and discomfort. Labradors are prone to anal gland issues.",                               lastDone:"Cleaned 10/09/2025 by Dr. Chavan", status:"done" },
];

const DOC_SECTIONS = [
  { id:"vaccination",   icon:"💉", label:"Vaccination Records",  color:"#34C759", bg:"#F0FFF4", files:[
    { name:"Zayn_Vaccination_Record_1.jpg", parsed:"DHPPi (Nobivac) · 06 May 2025",       note:"Next due: 06 May 2026", status:"Parsed ✓" },
    { name:"Zayn_Vaccination_Record_2.jpg", parsed:"Rabies (Nobivac RL) · 06 May 2025",   note:"Next due: 06 May 2026", status:"Parsed ✓" },
    { name:"Zayn_Vaccination_Record_2.jpg", parsed:"Kennel Cough (KC) · 06 May 2025",     note:"Next due: 06 May 2026", status:"Parsed ✓" },
    { name:"Zayn_Vaccination_Record_2.jpg", parsed:"Canine Coronavirus (CCoV) · 06 May 2025", note:"Next due: 06 May 2026", status:"Parsed ✓" },
  ]},
  { id:"prescriptions", icon:"📋", label:"Prescriptions",         color:"#007AFF", bg:"#F0F6FF", files:[
    { name:"Prescription_Chavan_12_02_25.jpg", parsed:"Blood tests ordered — CBC, LFT, KFT, Sugar (Feb 2025)", note:"Dr. Makarand Chavan · Dadar", status:"Parsed ✓" },
    { name:"Zayn_prescription_13sep25.docx",   parsed:"Augmentin Duo 375 + Cystone + Dompan (Sep 2025)",       note:"Post-UTI treatment × 5–15 days", status:"Parsed ✓" },
  ]},
  { id:"reports",       icon:"🔬", label:"Lab & Imaging Reports", color:"#FF9500", bg:"#FFF6ED", files:[
    { name:"ZAYN_BLOOD_REPORT_sep25.pdf",  parsed:"CBC — Thrombocytopenia (Plt 160, low). All other values normal.", note:"10 Sep 2025 · Fredna Vet Diagnostics", status:"Parsed ✓" },
    { name:"zayn_urine_sep25.pdf",         parsed:"Urinalysis — Alkaline, hazy, triple phosphates, trace occult blood, E. coli", note:"10 Sep 2025 · Unique Bio Diagnostics", status:"Parsed ✓" },
    { name:"Zayn_UrineCulture_sep25.pdf",  parsed:"E. coli isolated (<10³ CFU). Susceptible to Augmentin, Ciprofloxacin. Resistant to Ampicillin.", note:"10 Sep 2025 · Unique Bio Diagnostics", status:"Parsed ✓" },
    { name:"Zayn_usg_report_sep25.pdf",    parsed:"Abdominal USG — No abnormality. Kidneys, bladder, liver all normal.", note:"10 Sep 2025 · Fredna Vet Diagnostics", status:"Parsed ✓" },
    { name:"Zayn_x-ray_report_sep25.pdf",  parsed:"Chest & Abdomen X-ray — No significant abnormality detected.", note:"10 Sep 2025 · Fredna Vet Diagnostics", status:"Parsed ✓" },
    { name:"zayn_urine_Oct25.pdf",         parsed:"Oct urinalysis — Improved: acidic, no crystals, no occult blood, pus cells 2–3", note:"10 Oct 2025 · Unique Bio Diagnostics", status:"Parsed ✓" },
  ]},
];

const NUDGE_FILTERS = [
  { val:"all",       label:(n)=>`All (${n})`,  fn:(active)=>active },
  { val:"mandatory", label:()=>"🔴 Must Do",   fn:(active)=>active.filter(n=>n.mandatory) },
  { val:"nutrition", label:()=>"🥣 Nutrition", fn:(active)=>active.filter(n=>n.cat==="nutrition") },
  { val:"grooming",  label:()=>"🛁 Grooming",  fn:(active)=>active.filter(n=>n.cat==="grooming") },
];

const NUTRITION_MACROS = [
  { name:"Protein",       icon:"🥩", actual:0,  target:30, unit:"%", status:"low",  note:"Diet not recorded — cannot assess. Please add Zayn's current food." },
  { name:"Fat",           icon:"🧈", actual:0,  target:14, unit:"%", status:"low",  note:"Diet not recorded." },
  { name:"Carbohydrates", icon:"🌾", actual:0,  target:40, unit:"%", status:"low",  note:"Diet not recorded." },
  { name:"Fibre",         icon:"🥦", actual:0,  target:4,  unit:"%", status:"low",  note:"Diet not recorded." },
  { name:"Moisture",      icon:"💧", actual:0,  target:10, unit:"%", status:"low",  note:"Diet not recorded." },
];

const NUTRITION_VITAMINS = [
  { name:"Vitamin C",  status:"Low",      supplement:"Vit C 500mg",       price:"₹199/mo", priority:"medium" },
  { name:"Vitamin B12",status:"Missing",  supplement:null,                price:null,      priority:"ok" },
  { name:"Vitamin D",  status:"Missing",  supplement:null,                price:null,      priority:"ok" },
  { name:"Vitamin E",  status:"Missing",  supplement:null,                price:null,      priority:"ok" },
];

const NUTRITION_MINERALS = [
  { name:"Probiotics",  icon:"🦠", status:"Missing", priority:"urgent", reason:"Post-antibiotic course depletes gut flora — critical to restore. Supports UTI prevention and immunity.", supplement:"FortiFlora Probiotic", price:"₹649/mo" },
  { name:"Cranberry",   icon:"🫐", status:"Missing", priority:"urgent", reason:"Reduces E. coli adhesion to bladder wall. Directly relevant given Zayn's UTI history and ongoing urinary symptoms.", supplement:"Cran-Max / UTI Guard", price:"₹499/mo" },
  { name:"Omega-3",     icon:"🐟", status:"Missing", priority:"high",   reason:"Supports bladder wall integrity, reduces inflammation, and promotes joint health in Labs.", supplement:"Salmon Oil Omega-3",   price:"₹349/mo" },
  { name:"Zinc",        icon:"⚡", status:"Low",     priority:"medium", reason:"Supports immune function and skin/coat health in Labradors.", supplement:"Zinc supplement",        price:"₹249/mo" },
];

const NUTRITION_OTHERS = [
  { name:"Urinary Support", icon:"💧", status:"Missing", priority:"urgent", reason:"Zayn has a history of triple phosphate crystals and recurrent urinary issues. A urinary health supplement is strongly recommended.", supplement:"Cran-Max / UTI Guard", price:"₹499/mo" },
  { name:"Joint Support",   icon:"🦴", status:"Missing", priority:"medium", reason:"Labradors are prone to joint issues as they age. An early glucosamine/chondroitin supplement is advisable.", supplement:"Cosequin DS Chewable", price:"₹799/mo" },
];

const DIAGNOSTICS_ITEMS = [
  { icon:"🩸", name:"CBC — Complete Blood Count",    last:"10/09/2025", note:"Thrombocytopenia: Platelets 160 (ref: 200–800). All other values normal." },
  { icon:"🧪", name:"KFT + LFT + Electrolytes",      last:"10/09/2025", note:"All values within normal range. GGT slightly low (4, ref 5–14)." },
  { icon:"💧", name:"Urinalysis (Sep 2025)",          last:"10/09/2025", note:"Alkaline, triple phosphates, trace occult blood, E. coli confirmed on culture." },
  { icon:"🧫", name:"Urine Culture (Sep 2025)",       last:"10/09/2025", note:"E. coli isolated <10³ CFU. Susceptible to Augmentin. Treatment completed." },
  { icon:"🔊", name:"Abdominal USG",                  last:"10/09/2025", note:"No significant abnormality. Kidneys, bladder, liver all clear." },
  { icon:"📡", name:"Chest & Abdomen X-ray",          last:"10/09/2025", note:"No significant abnormality detected." },
  { icon:"💧", name:"Urinalysis (Oct 2025)",          last:"10/10/2025", note:"Improved: Acidic, no crystals, no occult blood. Pus cells 2–3/hpf persisting." },
  { icon:"🧫", name:"Repeat Urine Culture",           last:"—",          note:"Due Oct 2025 — OVERDUE. Not yet done." },
  { icon:"🩸", name:"CBC Platelet Recheck",           last:"—",          note:"PetCircle recommendation — monitor thrombocytopenia (Plt 160, Sep 2025)." },
];

const PAYMENT_METHODS = [
  { id:"upi",  label:"UPI",             icon:"📱", sub:"Pay via any UPI app" },
  { id:"card", label:"Card",            icon:"💳", sub:"Credit / Debit card" },
  { id:"net",  label:"Net Banking",     icon:"🏦", sub:"All major banks" },
  { id:"cod",  label:"Cash on Delivery",icon:"💵", sub:"Pay when delivered" },
];

const NUTRITION_IMPROVE = [
  { dot:"#FF3B30", text:"Probiotics missing → critical post-antibiotic for gut recovery" },
  { dot:"#FF3B30", text:"Urinary support supplement missing → reduces UTI recurrence risk" },
  { dot:"#FF9500", text:"Omega-3 not recorded → supports bladder health and joint function" },
  { dot:"#FF9500", text:"Current diet not recorded → add food info to get full nutrition analysis" },
  { dot:"#FFCC00", text:"Vitamin C low → acidifies urine, helps prevent crystal formation" },
];

const REMINDER_EXPLAINER = [
  ["1 week before",  "UPCOMING reminder with option to pre-order medicine, book home vet, or reorder meds."],
  ["Due date",       "Due today message sent at 9am with one-tap order or log action."],
  ["No action taken","Overdue follow-up sent every 7 days until the action is logged or completed."],
  ["Action taken",   "Reminder series stops automatically. Next cycle scheduled based on due date."],
  ["Condition meds", "Separate refill reminder series for each chronic medication — never miss a dose."],
];

const VAX_FREQ_OPTS   = [6, 9, 12, 18, 24];
const VAX_FREQ_LABELS = { 6:"Every 6 months", 9:"Every 9 months", 12:"Yearly", 18:"Every 18 months", 24:"Every 2 years" };

const FREQ_MODAL_UNITS   = ["day","week","month","year"];
const FREQ_MODAL_OPTIONS = { day:[1,2,3], week:[1,2,3,4,6], month:[1,2,3,6], year:[1] };

// ─── PURE UTILITY FUNCTIONS ───────────────────────────────────────────────────
// All date helpers consolidated and defined once at module scope

function formatDMY(date) {
  return `${String(date.getDate()).padStart(2,"0")}/${String(date.getMonth()+1).padStart(2,"0")}/${date.getFullYear()}`;
}

function parseDMY(str) {
  if (!str) return null;
  const [d,m,y] = str.split("/").map(Number);
  return new Date(y, m-1, d);
}

// Replaces both calcCareDue and calcNextDue (they were identical)
function addMonths(lastDone, freqMonths) {
  if (!lastDone) return null;
  const [d,m,y] = lastDone.split("/").map(Number);
  return formatDMY(new Date(y, m - 1 + freqMonths, d));
}

function addByUnit(last, freq, unit) {
  if (!last || last === "Not recorded") return null;
  const [d,m,y] = last.split("/").map(Number);
  const dt = new Date(y, m-1, d);
  if (unit==="day")   dt.setDate(dt.getDate() + freq);
  if (unit==="week")  dt.setDate(dt.getDate() + freq*7);
  if (unit==="month") dt.setMonth(dt.getMonth() + freq);
  if (unit==="year")  dt.setFullYear(dt.getFullYear() + freq);
  return formatDMY(dt);
}

function diffDaysFromToday(dateStr) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0,0,0,0);
  const next = parseDMY(dateStr);
  return next ? (next - today) / 86400000 : null;
}

function deriveCareStatus(lastDone, nextDue) {
  if (!lastDone) return "missing";
  if (!nextDue) return "missing";
  const diff = diffDaysFromToday(nextDue);
  if (diff === null) return "missing";
  return diff < 0 ? "overdue" : diff <= 60 ? "upcoming" : "done";
}

function getVaxStatus(lastGiven, nextDue) {
  if (!lastGiven) return "missing";
  const diff = diffDaysFromToday(nextDue);
  if (diff === null) return "missing";
  return diff < 0 ? "overdue" : diff <= 30 ? "upcoming" : "done";
}

// Replaces sharedUnitLabel and unitLabel (they were identical duplicates)
function freqLabel(freq, unit) {
  if (unit==="day")   return freq===1 ? "Daily"   : `Every ${freq} days`;
  if (unit==="week")  return freq===1 ? "Weekly"  : `Every ${freq} weeks`;
  if (unit==="month") return freq===1 ? "Monthly" : `Every ${freq} months`;
  if (unit==="year")  return freq===1 ? "Yearly"  : `Every ${freq} years`;
  return `Every ${freq} ${unit}s`;
}

function isDateInputValid(str) {
  const p = str.split("/");
  return p.length===3 && p[0].length<=2 && p[1].length<=2 && p[2].length===4;
}

const PRIORITY_SCORE = { ok:1, medium:0.6, high:0.3, urgent:0.1 };
const CARE_SCORE     = { done:1, upcoming:0.7, overdue:0.2, missing:0 };

function computeHealthScore(pet) {
  // Score based purely on health status — NOT monitoring consistency.
  // Grooming records, checkup logs, deworming cadence do NOT affect this score.
  const hr = pet.healthRecords;

  // 1. Organ health — consistently normal across all of Zayn's records
  const organScore = 1.0;

  // 2. Active unresolved conditions — each drags score significantly
  const unresolved = hr.conditions.filter(c => c.status !== "resolved");
  const conditionScore = unresolved.length === 0 ? 1.0
    : unresolved.length === 1 ? 0.65
    : unresolved.length === 2 ? 0.35
    : 0.15;

  // 3. Parasite / tick-borne disease risk (active health threat, not a record-keeping gap)
  const hasUntreatedTick = unresolved.some(c => c.name.toLowerCase().includes("anaplasma"));
  const parasiteScore = hasUntreatedTick ? 0.25 : hr.fleaTick.status === "done" ? 1.0 : 0.6;

  // 4. Vaccine protection — immunity status, not just whether records exist
  const mandatory = hr.vaccines.filter(v => v.mandatory);
  const vaccineScore = mandatory.filter(v => v.lastGiven).length / (mandatory.length || 1);

  const categories = [
    { key:"organs",     label:"Organ Health",      icon:"🫀", weight:40, score:organScore,    detail:"Liver, kidneys, heart, lungs — all normal", drag:false },
    { key:"conditions", label:"Active Conditions",  icon:"🦴", weight:35, score:conditionScore, detail:unresolved.length ? unresolved.length + " unresolved" : "No active conditions", drag:conditionScore < 0.7 },
    { key:"parasites",  label:"Parasite Risk",      icon:"🐛", weight:15, score:parasiteScore,  detail:hasUntreatedTick ? "Untreated tick infection on record" : "Managed", drag:parasiteScore < 0.5 },
    { key:"vaccines",   label:"Vaccine Protection", icon:"💉", weight:10, score:vaccineScore,   detail:mandatory.filter(v=>v.lastGiven).length + "/" + mandatory.length + " core vaccines current", drag:vaccineScore < 0.5 },
  ];

  const breakdown = categories.map(cat => ({ ...cat, weighted: cat.score * cat.weight }));
  const total = Math.round(breakdown.reduce((a,b) => a + b.weighted, 0));
  return {
    total,
    label:      total>=85?"Excellent":total>=70?"Good · Watch":total>=50?"Fair":"Needs Attention",
    labelColor: total>=85?"#34C759":total>=70?"#FF9500":"#FF3B30",
    ringColor:  total>=85?"#34C759":total>=70?"#FF9500":"#FF3B30",
    breakdown,
    draggers: breakdown.filter(b=>b.drag).map(b=>b.label),
  };
}

// ─── SHARED UI PRIMITIVES ─────────────────────────────────────────────────────

function Avatar({ name, size=56, imgSrc, onImgChange }) {
  const ini = name?.split(" ").map(n=>n[0]).join("").slice(0,2).toUpperCase();
  const inputRef = useRef();
  const handleFile = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => onImgChange?.(ev.target.result);
    reader.readAsDataURL(file);
  }, [onImgChange]);
  return (
    <div style={{position:"relative",flexShrink:0,cursor:onImgChange?"pointer":"default"}} onClick={()=>onImgChange&&inputRef.current?.click()}>
      {imgSrc
        ? <img src={imgSrc} alt={name} style={{width:size,height:size,borderRadius:"50%",objectFit:"cover",boxShadow:"0 4px 12px rgba(255,107,53,0.35)",border:"2px solid rgba(255,255,255,0.3)"}}/>
        : <div style={{width:size,height:size,borderRadius:"50%",background:"linear-gradient(135deg,#D44800,#FF9F1C)",display:"flex",alignItems:"center",justifyContent:"center",color:"white",fontFamily:"'Fraunces',serif",fontWeight:700,fontSize:size*0.35,boxShadow:"0 4px 12px rgba(255,107,53,0.35)"}}>{ini}</div>
      }
      {onImgChange && <div style={{position:"absolute",bottom:0,right:0,width:18,height:18,borderRadius:"50%",background:"white",display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,boxShadow:"0 1px 4px rgba(0,0,0,0.2)"}}>📷</div>}
      {onImgChange && <input ref={inputRef} type="file" accept="image/*" style={{display:"none"}} onChange={handleFile}/>}
    </div>
  );
}

function Ring({ pct, size=64, stroke=5, color="#D44800" }) {
  const r=(size-stroke*2)/2, c=2*Math.PI*r, off=c-(pct/100)*c;
  return (
    <svg width={size} height={size} style={{transform:"rotate(-90deg)"}}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#F2F2F7" strokeWidth={stroke}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" style={{transition:"stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1)"}}/>
    </svg>
  );
}

function BackBtn({ onBack, light }) {
  return <button onClick={onBack} style={{background:light?"rgba(255,255,255,0.15)":"#F2EDE8",border:"none",borderRadius:10,width:36,height:36,display:"flex",alignItems:"center",justifyContent:"center",cursor:"pointer",fontSize:16,color:light?"white":"#555",flexShrink:0}}>←</button>;
}

function Badge({ label, color, bg }) {
  return <div style={{background:bg,color,borderRadius:6,padding:"2px 8px",fontSize:10,fontWeight:700,flexShrink:0}}>{label}</div>;
}

// Single Toggle used everywhere — replaced the two separate inline implementations
function Toggle({ on, onToggle, showLabel=false }) {
  return (
    <div onClick={onToggle} style={{display:"flex",alignItems:"center",gap:5,cursor:"pointer",flexShrink:0}}>
      {showLabel && <div style={{fontSize:10,color:"#AEAEB2",fontWeight:600}}>{on?"Reminder on":"Reminder off"}</div>}
      <div style={{width:34,height:20,borderRadius:10,background:on?"#34C759":"#D1D1D6",position:"relative",transition:"background 0.2s"}}>
        <div style={{width:16,height:16,borderRadius:"50%",background:"white",position:"absolute",top:2,left:on?16:2,transition:"left 0.2s",boxShadow:"0 1px 3px rgba(0,0,0,0.2)"}}/>
      </div>
    </div>
  );
}

function GStyles() {
  return <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:wght@700;900&display=swap');@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}@keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-4px)}}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}*{box-sizing:border-box}::-webkit-scrollbar{display:none}`}</style>;
}

function AddRow({ label, onClick }) {
  return (
    <button onClick={onClick}
      style={{display:"flex",alignItems:"center",gap:8,width:"100%",background:"none",border:"1.5px dashed #D4480055",borderRadius:10,padding:"8px 12px",cursor:"pointer",color:"#D44800",fontWeight:600,fontSize:12,marginTop:6}}>
      <div style={{width:20,height:20,borderRadius:"50%",background:"#D4480015",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:700,flexShrink:0}}>+</div>
      {label}
    </button>
  );
}

// ─── SHARED COMPOUND COMPONENTS ───────────────────────────────────────────────

// ReminderBar defined once at module scope (was defined inside DashboardStep before)
function ReminderBar({ id, settings, setSettings, onFreqClick }) {
  const s = settings[id] || { freq:1, unit:"month", reminder:false };
  const on = s.reminder;
  return (
    <div style={{display:"flex",alignItems:"center",gap:8,marginTop:8,padding:"8px 10px",background:"#F7F4F0",borderRadius:10}}>
      <div style={{fontSize:11,color:"#8E8E93",flex:1}}>🔔 Reminder</div>
      <div onClick={()=>onFreqClick?.({id,freq:s.freq,unit:s.unit,isItem:true})}
        style={{display:"inline-flex",alignItems:"center",gap:4,background:on?"#EFF6FF":"#F2F2F7",color:on?"#007AFF":"#AEAEB2",borderRadius:20,padding:"3px 10px",fontSize:11,fontWeight:600,cursor:"pointer"}}>
        🔁 {freqLabel(s.freq,s.unit)} <span style={{fontSize:10,opacity:0.7}}>✎</span>
      </div>
      <Toggle on={on} onToggle={()=>setSettings(prev=>({...prev,[id]:{...prev[id],reminder:!prev[id].reminder}}))}/>
    </div>
  );
}

// DateEditSheet — extracted from three near-identical inline IIFE sheets
function DateEditSheet({ title, subtitle, inputLabel="Last Done", value, onChange, previewNext, onSave, onClose }) {
  const isValid = isDateInputValid(value);
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
        <div style={{fontWeight:700,fontSize:16,marginBottom:4}}>{title}</div>
        {subtitle && <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>{subtitle}</div>}
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>{inputLabel}</div>
        <input type="text" placeholder="DD/MM/YYYY" value={value} onChange={e=>onChange(e.target.value)}
          style={{width:"100%",padding:"12px 14px",borderRadius:12,border:"1.5px solid #E8E4DF",fontSize:14,outline:"none",boxSizing:"border-box",color:"#1A1A1A"}} autoFocus/>
        <div style={{marginTop:14,padding:"12px 14px",background:"#F7F4F0",borderRadius:12}}>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:4}}>Next Due (auto-calculated)</div>
          <div style={{fontSize:14,fontWeight:600,color:isValid?"#1A1A1A":"#AEAEB2"}}>{isValid&&previewNext ? previewNext : "Enter a valid date above"}</div>
        </div>
        <button onClick={()=>{ if(isValid) onSave(value); onClose(); }}
          style={{width:"100%",marginTop:20,background:isValid?"#D44800":"#D1D1D6",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:isValid?"pointer":"default"}}>
          Save Date
        </button>
        <button onClick={onClose} style={{width:"100%",background:"none",border:"none",color:"#8E8E93",padding:"10px",fontSize:13,cursor:"pointer",marginTop:4}}>Cancel</button>
      </div>
    </div>
  );
}

// FreqModal — extracted from inline IIFE, single implementation
function FreqModal({ modal, setModal, onSave }) {
  if (!modal) return null;
  const opts = FREQ_MODAL_OPTIONS[modal.unit] || [1,2,3];
  const label = freqLabel(modal.freq, modal.unit);
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:200,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setModal(null)}>
      <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
        <div style={{fontWeight:700,fontSize:16,marginBottom:4}}>Set Reminder Frequency</div>
        <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>How often should Zayn do this?</div>
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>Every</div>
        <div style={{display:"flex",gap:6,marginBottom:16,flexWrap:"wrap"}}>
          {opts.map(n=>(
            <button key={n} onClick={()=>setModal(f=>({...f,freq:n}))}
              style={{padding:"8px 16px",borderRadius:20,border:"none",background:modal.freq===n?"#D44800":"#F2EDE8",color:modal.freq===n?"white":"#555",fontWeight:600,fontSize:13,cursor:"pointer"}}>
              {n}
            </button>
          ))}
        </div>
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>Unit</div>
        <div style={{display:"flex",gap:6,marginBottom:24}}>
          {FREQ_MODAL_UNITS.map(u=>(
            <button key={u} onClick={()=>setModal(f=>({...f,unit:u,freq:(FREQ_MODAL_OPTIONS[u]||[1])[0]}))}
              style={{flex:1,padding:"8px 0",borderRadius:20,border:"none",background:modal.unit===u?"#D44800":"#F2EDE8",color:modal.unit===u?"white":"#555",fontWeight:600,fontSize:12,cursor:"pointer",textTransform:"capitalize"}}>
              {u}
            </button>
          ))}
        </div>
        <div style={{background:"#F7F4F0",borderRadius:10,padding:"10px 14px",marginBottom:16,textAlign:"center",fontSize:13,color:"#555"}}>
          Reminder set: <strong style={{color:"#D44800"}}>{label}</strong>
        </div>
        <button onClick={()=>{ onSave(modal); setModal(null); }}
          style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:12,padding:"12px",fontSize:14,fontWeight:700,cursor:"pointer"}}>
          Save Frequency
        </button>
      </div>
    </div>
  );
}

// ─── STEP 1: WhatsApp ─────────────────────────────────────────────────────────

function WhatsAppStep({ onNext }) {
  const [msgs, setMsgs] = useState([]);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (step >= WHATSAPP_CONV.length) return;
    const msg = WHATSAPP_CONV[step];
    const t = setTimeout(() => {
      setMsgs(p => [...p, msg]);
      setStep(s => s+1);
      if (step === WHATSAPP_CONV.length-1) setTimeout(onNext, 2200);
    }, step===0 ? 400 : msg.delay+300);
    return () => clearTimeout(t);
  }, [step]);

  return (
    <div style={{fontFamily:"'DM Sans',sans-serif",minHeight:"100vh",background:"#ECE5DD",display:"flex",flexDirection:"column"}}>
      <div style={{background:"#075E54",padding:"12px 16px",display:"flex",alignItems:"center",gap:12,boxShadow:"0 2px 8px rgba(0,0,0,0.2)"}}>
        <div style={{width:40,height:40,borderRadius:"50%",background:"#25D366",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20}}>🐾</div>
        <div>
          <div style={{color:"white",fontWeight:600,fontSize:16}}>PetCircle</div>
          <div style={{color:"#B2DFDB",fontSize:12}}>Typically replies instantly</div>
        </div>
        <div style={{marginLeft:"auto",background:"#25D366",color:"white",borderRadius:20,padding:"4px 14px",fontSize:12,fontWeight:600}}>VERIFIED ✓</div>
      </div>
      <div style={{flex:1,overflowY:"auto",padding:"16px 12px",display:"flex",flexDirection:"column",gap:8}}>
        <div style={{textAlign:"center",background:"rgba(0,0,0,0.08)",borderRadius:8,padding:"4px 12px",fontSize:11,color:"#555",alignSelf:"center",marginBottom:8}}>TODAY</div>
        {msgs.map((msg,i) => {
          const isUser = msg.from==="user";
          return (
            <div key={i} style={{display:"flex",justifyContent:isUser?"flex-end":"flex-start"}}>
              <div style={{maxWidth:"78%",padding:"8px 12px",borderRadius:isUser?"18px 18px 4px 18px":"18px 18px 18px 4px",background:isUser?"#DCF8C6":"white",boxShadow:"0 1px 2px rgba(0,0,0,0.12)",fontSize:14,lineHeight:1.5,whiteSpace:"pre-line",animation:"fadeIn 0.3s ease"}}>
                {msg.isProcessing ? (
                  <div>
                    <div style={{fontWeight:600,marginBottom:6}}>🤖 Analysing Zayn's records...</div>
                    <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
                      {["Parsing records","Mapping nutrition","Building care plan"].map((t,j)=>(
                        <div key={j} style={{background:"#F0F0F0",borderRadius:10,padding:"2px 8px",fontSize:11,color:"#555",animation:"pulse 1.5s infinite"}}>⏳ {t}</div>
                      ))}
                    </div>
                  </div>
                ) : <span dangerouslySetInnerHTML={{__html:msg.text.replace(/\*(.*?)\*/g,"<strong>$1</strong>")}}/>}
                <div style={{fontSize:10,color:"#999",textAlign:"right",marginTop:2}}>{new Date().toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"})}{isUser&&" ✓✓"}</div>
              </div>
            </div>
          );
        })}
        {step < WHATSAPP_CONV.length && (
          <div style={{alignSelf:"flex-start"}}>
            <div style={{background:"white",borderRadius:"18px 18px 18px 4px",padding:"10px 16px",boxShadow:"0 1px 2px rgba(0,0,0,0.12)"}}>
              <div style={{display:"flex",gap:4}}>{[0,1,2].map(i=><div key={i} style={{width:6,height:6,borderRadius:"50%",background:"#ccc",animation:`bounce 1.2s ${i*0.2}s infinite`}}/>)}</div>
            </div>
          </div>
        )}
      </div>
      <GStyles/>
    </div>
  );
}

// ─── STEP 2: Processing ───────────────────────────────────────────────────────

function ProcessingStep({ onNext, onBack }) {
  const [pct, setPct] = useState(0);
  const [cur, setCur] = useState(0);

  useEffect(() => {
    const increment = 100 / (PROCESSING_TASKS.length * 4);
    const iv = setInterval(()=>setPct(p=>{
      const n = p + increment;
      if (n >= 100) { clearInterval(iv); setTimeout(onNext,600); return 100; }
      return n;
    }), 80);
    const ti = setInterval(()=>setCur(c=>Math.min(c+1, PROCESSING_TASKS.length-1)), 700);
    return ()=>{ clearInterval(iv); clearInterval(ti); };
  }, []);

  return (
    <div style={{minHeight:"100vh",background:"#0A0A0A",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",fontFamily:"'DM Sans',sans-serif",padding:32}}>
      <div style={{position:"absolute",top:20,left:20}}><BackBtn onBack={onBack} light/></div>
      <div style={{position:"relative",marginBottom:40}}>
        <Ring pct={pct} size={140} stroke={8} color="#D44800"/>
        <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
          <div style={{fontSize:32}}>🐾</div>
          <div style={{color:"white",fontWeight:700,fontSize:18,fontFamily:"'Fraunces',serif"}}>{Math.round(pct)}%</div>
        </div>
      </div>
      <div style={{color:"white",fontFamily:"'Fraunces',serif",fontSize:26,fontWeight:700,marginBottom:8,textAlign:"center"}}>Analysing Zayn's Profile</div>
      <div style={{color:"#888",marginBottom:40}}>Health records + nutrition + care gaps</div>
      <div style={{width:"100%",maxWidth:380,background:"#1A1A1A",borderRadius:16,padding:20,display:"flex",flexDirection:"column",gap:10}}>
        {PROCESSING_TASKS.map((t,i)=>(
          <div key={i} style={{display:"flex",alignItems:"center",gap:12,opacity:i<=cur?1:0.25,transition:"opacity 0.4s"}}>
            <div style={{width:22,height:22,borderRadius:"50%",flexShrink:0,background:i<cur?"#34C759":i===cur?"#D44800":"#333",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,color:"white"}}>{i<cur?"✓":i===cur?"↻":""}</div>
            <div style={{color:i<=cur?"white":"#555",fontSize:14}}>{t}</div>
          </div>
        ))}
      </div>
      <GStyles/>
    </div>
  );
}

// ─── STEP 3: Dashboard ────────────────────────────────────────────────────────

function DashboardStep({ onNext, onBack, onCart, petImg, onPetImgChange }) {
  // onCart(itemId?) — navigates to cart, optionally pinning an item to top
  const [tab, setTab]               = useState("overview");
  const [freqModal, setFreqModal]   = useState(null);
  const [waOpen, setWaOpen]         = useState(false);

  // Shared "add entry" bottom sheet
  const [addSheet, setAddSheet]     = useState(null);
  const [addForm,  setAddForm]      = useState({});

  // Editable diet state — empty until Ashita adds food info
  const [dietRows, setDietRows] = useState([]);
  const [editDietRow, setEditDietRow] = useState(null);
  const [editDietForm, setEditDietForm] = useState({label:"", detail:""});

  const [vaccineState, setVaccineState] = useState({
    "dhppi":       { lastGiven:"06/05/2025", freqMonths:12 },
    "rabies":      { lastGiven:"06/05/2025", freqMonths:12 },
    "kennelcough": { lastGiven:"06/05/2025", freqMonths:12, reminder:false },
    "ccov":        { lastGiven:"06/05/2025", freqMonths:12, reminder:false },
  });
  const [editingVaxDate, setEditingVaxDate] = useState(null);
  const [vaxDateInput, setVaxDateInput]     = useState("");
  const [vaxFreqModal, setVaxFreqModal]     = useState(null);

  const [dwLastDone,  setDwLastDone]  = useState(mockPetData.healthRecords.deworming.lastDone);
  const [ftLastDone,  setFtLastDone]  = useState(mockPetData.healthRecords.fleaTick.lastDone);
  const [editingCareDate, setEditingCareDate] = useState(null);
  const [careDateInput,   setCareDateInput]   = useState("");

  // Anal glands cleaned 10 Sep 2025 per Dr Chavan prescription; bath not recorded
  const [periodicDates, setPeriodicDates] = useState({ "bath-nail":null, "anal-gland":"10/09/2025" });
  const [editingGroomDate, setEditingGroomDate] = useState(null);
  const [groomDateInput,   setGroomDateInput]   = useState("");

  const [openRemId,       setOpenRemId]       = useState(null);
  const [orderedRem,      setOrderedRem]      = useState([]);
  const [openDocSection,  setOpenDocSection]  = useState(null);

  const [contacts, setContacts] = useState([
    { id:"ct1", type:"vet", icon:"🩺", name:"Dr. Makarand Chavan", clinic:"Dogs & Cats Veterinary Clinic, Dadar", phone:"+91 98212 31587", note:"UTI treatment — Sep 2025" },
  ]);
  const [contactsOpen,    setContactsOpen]    = useState(true);
  const [editContact,     setEditContact]     = useState(null);   // contact obj being edited, or "new"
  const [contactForm,     setContactForm]     = useState({});

  const [hygieneSettings, setHygieneSettings] = useState({
    "coat-brush":  { freq:1, unit:"day",   reminder:true },
    "teeth-brush": { freq:1, unit:"day",   reminder:true },
    "ear-clean":   { freq:6, unit:"week",  reminder:true },
    "eye-wipe":    { freq:1, unit:"month", reminder:true },
    "bath-nail":   { freq:1, unit:"month", reminder:true },
    "anal-gland":  { freq:6, unit:"week",  reminder:true },
  });
  const [itemSettings, setItemSettings] = useState({
    "deworming":        { freq:3, unit:"month", reminder:true  },
    "flea-tick":        { freq:1, unit:"month", reminder:true  },
    "vet-visit":        { freq:1, unit:"year",  reminder:true  },
    "diagnostics":      { freq:1, unit:"year",  reminder:false },
    "meloxicam":        { freq:1, unit:"month", reminder:true  },
    "omega3":           { freq:1, unit:"month", reminder:true  },
    "xray":             { freq:1, unit:"year",  reminder:true  },
    "mobility":         { freq:6, unit:"month", reminder:true  },
    "nutrition":        { freq:1, unit:"month", reminder:false },
    "grooming":         { freq:1, unit:"month", reminder:true  },
    "chk-vet":          { freq:1, unit:"year",  reminder:true  },
    "chk-blood":        { freq:1, unit:"year",  reminder:true  },
    "chk-urine":        { freq:6, unit:"month", reminder:true  },
    "chk-culture":      { freq:6, unit:"month", reminder:true  },
    "chk-cbc":          { freq:6, unit:"month", reminder:true  },
    "chk-pcr":          { freq:12, unit:"month", reminder:true  },
  });

  const [checkupDates, setCheckupDates] = useState({
    "chk-vet":     "10/09/2025",
    "chk-blood":   "10/09/2025",
    "chk-urine":   "10/10/2025",
    "chk-culture": null,
    "chk-cbc":     null,
    "chk-pcr":     null,
  });
  const [editingCheckupId,   setEditingCheckupId]   = useState(null);
  const [checkupDateInput,   setCheckupDateInput]   = useState("");

  const pet = mockPetData;
  // useMemo so health score is only recomputed when pet data changes
  const hs = useMemo(() => computeHealthScore(pet), [pet]);
  const cartCount = useMemo(() => cartItemsData.filter(i=>i.inCart).length, []);

  // Shared handler passed to FreqModal
  const handleFreqSave = useCallback((modal) => {
    if (modal.isItem) {
      setItemSettings(s=>({...s,[modal.id]:{...s[modal.id],freq:modal.freq,unit:modal.unit}}));
    } else {
      setHygieneSettings(s=>({...s,[modal.id]:{...s[modal.id],freq:modal.freq,unit:modal.unit}}));
    }
  }, []);

  // Helper for care cards: derives status + display values from lastDone + freqMonths
  const getCareCardProps = useCallback((lastDone, freqMonths) => {
    const nextDue = addMonths(lastDone, freqMonths);
    const status  = deriveCareStatus(lastDone, nextDue);
    return {
      nextDue,
      status,
      c:   STATUS_COLOR[status] || "#34C759",
      bg:  STATUS_BG[status]    || "#F0FFF4",
      lbl: STATUS_LABEL[status] || "Up to date",
      subtext: lastDone ? ("Last: " + lastDone + (nextDue ? "  ·  Next: " + nextDue : "")) : "No record found",
    };
  }, []);

  // Reusable care card renderer for Deworming / Flea-Tick / Vet
  const CareCard = useCallback(({ icon, title, product, lastDone, freqMonths, editKey, reminderId, cartId }) => {
    const { status, c, bg, lbl, subtext } = getCareCardProps(lastDone, freqMonths);
    return (
      <div style={{background:"white",borderRadius:16,padding:16,border:`1.5px solid ${c}44`,boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:10}}>
          <div style={{width:44,height:44,borderRadius:12,background:bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>{icon}</div>
          <div style={{flex:1,minWidth:0}}>
            <div style={{fontWeight:700,fontSize:15}}>{title}</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{subtext}</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{product}</div>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
            <div style={{background:bg,color:c,borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>{lbl}</div>
            <button onClick={()=>{setEditingCareDate(editKey); setCareDateInput(lastDone||"");}}
              style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
          </div>
        </div>
        <ReminderBar id={reminderId} settings={itemSettings} setSettings={setItemSettings} onFreqClick={setFreqModal}/>
        <div style={{height:10}}/>
        <button onClick={()=>status!=="done"&&onCart(cartId||null)}
          style={{width:"100%",background:status==="done"?"#D1D1D6":"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:status==="done"?"default":"pointer"}}>
          {status==="done"?"✓ Up to Date":"Order Now"}
        </button>
      </div>
    );
  }, [getCareCardProps, itemSettings, onCart]);

  // ── OVERVIEW ──────────────────────────────────────────────────────────────
  const renderOverviewTab = () => {
    const vaxRows = pet.healthRecords.vaccines.filter(v=>v.mandatory).map(v=>{
      const vs = vaccineState[v.id];
      return getVaxStatus(vs.lastGiven, addMonths(vs.lastGiven, vs.freqMonths));
    });
    const vaxOverdue  = vaxRows.filter(s=>s==="overdue"||s==="missing").length;
    const vaxUpcoming = vaxRows.filter(s=>s==="upcoming").length;
    const [vacColor, vacBg, vacLabel, vacDue] = vaxOverdue
      ? ["#FF3B30","#FFF0F0","Attention",`${vaxOverdue} need attention`]
      : vaxUpcoming
      ? ["#FF9500","#FFF6ED","Due Soon","Booster coming up"]
      : ["#34C759","#F0FFF4","Current","All mandatory done"];

    const dw = pet.healthRecords.deworming;
    const ft = pet.healthRecords.fleaTick;
    const cond = pet.healthRecords.conditions[0];

    const tiles = [
      { icon:"💉", label:"Vaccines",    color:vacColor, bg:vacBg, status:vacLabel, due:vacDue, tab:"medical" },
      { icon:"🪱", label:"Deworming",   color:STATUS_COLOR[dw.status]||"#34C759", bg:STATUS_BG[dw.status]||"#F0FFF4", status:STATUS_LABEL[dw.status]||"Up to date", due:dw.nextDue?`Next: ${dw.nextDue}`:"Not started", tab:"medical" },
      { icon:"🐛", label:"Flea & tick", color:STATUS_COLOR[ft.status]||"#34C759", bg:STATUS_BG[ft.status]||"#F0FFF4", status:ft.status==="missing"?"No record":STATUS_LABEL[ft.status]||"Up to date", due:ft.nextDue?`Next: ${ft.nextDue}`:"Not started", tab:"medical" },
      { icon:"🪥", label:"Daily care",  color:"#FF9500", bg:"#FFF6ED", status:"Due soon",  due:"Coat · Teeth · Ears · Eyes", tab:"grooming" },
      { icon:"🛁", label:"Grooming",    color:"#FF3B30", bg:"#FFF0F0", status:"1 overdue", due:"Bath & nails · Anal gland",   tab:"grooming" },
      { icon:"🩺", label:"Ann. Checkup", color:"#FF9500", bg:"#FFF6ED", status:"Due Soon", due:"Wellness exam · Mar 2025", tab:"medical" },
    ];

    return (
      <div style={{display:"flex",flexDirection:"column",gap:12,animation:"slideUp 0.4s ease"}}>
        {/* Care tiles grid */}
        <div>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,marginBottom:8,paddingLeft:2}}>Care at a glance</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:8,marginBottom:12}}>
            {tiles.map((t,i)=>(
              <div key={i} onClick={()=>setTab(t.tab)} style={{background:"white",borderRadius:14,padding:"12px 10px",border:`1.5px solid ${t.color}33`,boxShadow:"0 1px 4px rgba(0,0,0,0.05)",cursor:"pointer"}}>
                <div style={{fontSize:20,marginBottom:5}}>{t.icon}</div>
                <div style={{fontSize:11,fontWeight:700,color:"#1A1A1A",marginBottom:4,lineHeight:1.2}}>{t.label}</div>
                <div style={{background:t.bg,color:t.color,borderRadius:20,padding:"2px 7px",fontSize:10,fontWeight:700,display:"inline-block",marginBottom:5}}>{t.status}</div>
                <div style={{fontSize:10,color:"#AEAEB2",lineHeight:1.3}}>{t.due}</div>
              </div>
            ))}
          </div>

          {/* Condition summary inline */}
          {cond && (() => {
            const urgentMeds = cond.medications.filter(m=>m.refillStatus==="urgent");
            const nextFollowup = [...cond.monitoringChecks].sort((a,b)=>a.nextDue.localeCompare(b.nextDue))[0];
            const borderC = urgentMeds.length?"#FF3B30":"#007AFF";
            return (
              <div style={{background:"white",borderRadius:16,padding:16,border:`1.5px solid ${borderC}33`,boxShadow:"0 1px 6px rgba(0,0,0,0.06)",marginBottom:12}}>
                <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10}}>
                  <div style={{width:42,height:42,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{cond.icon}</div>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700,fontSize:14}}>{cond.name}</div>
                    <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>{cond.managedBy}</div>
                  </div>
                  <div style={{background:"#F0F6FF",color:"#007AFF",borderRadius:20,padding:"4px 10px",fontSize:11,fontWeight:700}}>Managed</div>
                </div>
                {cond.medications.map((med,i)=>{
                  const c = med.refillStatus==="urgent"?"#FF3B30":med.refillStatus==="upcoming"?"#FF9500":"#34C759";
                  const bg= med.refillStatus==="urgent"?"#FFF0F0":med.refillStatus==="upcoming"?"#FFF6ED":"#F0FFF4";
                  const cartId = i===0 ? "c3" : "c3"; // Omega-3 urgent → c3; Meloxicam → c3 (closest orderable)
                  const isActionable = med.refillStatus==="urgent"||med.refillStatus==="upcoming";
                  return (
                    <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"6px 10px",background:"#FAFAF9",borderRadius:8,border:`1px solid ${c}22`,marginBottom:4}}>
                      <span style={{fontSize:13}}>💊</span>
                      <span style={{fontSize:12,fontWeight:600,flex:1}}>{med.name}</span>
                      {isActionable
                        ? <button onClick={()=>onCart(med.name.toLowerCase().includes("omega")?"c3":"c3")}
                            style={{background:bg,color:c,borderRadius:20,padding:"2px 10px",fontSize:10,fontWeight:700,border:"none",cursor:"pointer"}}>
                            {med.refillStatus==="urgent"?"Refill now →":"Refill soon →"}
                          </button>
                        : <div style={{background:bg,color:c,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>On track</div>
                      }
                    </div>
                  );
                })}
                {nextFollowup && (
                  <div style={{display:"flex",alignItems:"center",gap:8,padding:"8px 10px",background:"#F0F6FF",borderRadius:10}}>
                    <span style={{fontSize:14}}>📅</span>
                    <div style={{flex:1}}>
                      <div style={{fontSize:12,fontWeight:600,color:"#007AFF"}}>Next follow-up</div>
                      <div style={{fontSize:11,color:"#5590CC",marginTop:1}}>{nextFollowup.name} · {nextFollowup.nextDue}</div>
                    </div>
                    <button onClick={()=>setTab("conditions")} style={{background:"none",border:"none",color:"#007AFF",fontSize:11,fontWeight:700,cursor:"pointer",padding:0,flexShrink:0}}>Details →</button>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Single order CTA */}
          <button onClick={()=>onCart(null)}
            style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:12,padding:"12px",fontSize:14,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:8}}>
            🛒 Order Now
          </button>
        </div>

        {/* Nutrition note */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #D4480033",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12}}>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <div style={{width:36,height:36,borderRadius:10,background:"#FFF3EE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:17,flexShrink:0}}>🐾</div>
              <div style={{fontWeight:700,fontSize:14,color:"#1A1A1A"}}>Nutrition note</div>
            </div>
            <button onClick={()=>setTab("nutrition")} style={{background:"none",border:"none",color:"#D44800",fontSize:12,fontWeight:700,cursor:"pointer",padding:0}}>Details →</button>
          </div>
          <div style={{background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#8B5E00",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>Overall diet</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Diet not recorded — add Zayn's food details to get a full nutritional analysis.</div>
          </div>
          <div style={{background:"#F0F6FF",border:"1px solid #007AFF33",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#005BBB",textTransform:"uppercase",letterSpacing:0.4,marginBottom:5}}>What to improve</div>
            {NUTRITION_IMPROVE.map((item,i)=>(
              <div key={i} style={{display:"flex",alignItems:"flex-start",gap:7,marginBottom:i===NUTRITION_IMPROVE.length-1?0:4}}>
                <div style={{width:6,height:6,borderRadius:"50%",background:item.dot,flexShrink:0,marginTop:4}}/>
                <span style={{fontSize:12,color:"#333",lineHeight:1.4}}>{item.text}</span>
              </div>
            ))}
          </div>
          <div style={{background:"#F0FFF4",border:"1px solid #34C75933",borderRadius:10,padding:"8px 11px"}}>
            <div style={{fontSize:10,fontWeight:700,color:"#1A6B2A",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>Recommendation</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Add probiotics + urinary support supplement as priority.</div>
          </div>
        </div>

        {/* WhatsApp reminders card */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #25D36633",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div onClick={()=>setWaOpen(o=>!o)} style={{background:"#075E54",padding:"13px 16px",display:"flex",alignItems:"center",gap:12,cursor:"pointer"}}>
            <div style={{width:40,height:40,borderRadius:12,background:"#128C7E",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>📲</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:14,color:"white"}}>WhatsApp Reminders</div>
              <div style={{fontSize:11,color:"#B2DFDB",marginTop:1}}>{whatsappReminders.length} reminders scheduled · tap to view</div>
            </div>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <div style={{background:"#25D366",color:"white",borderRadius:20,padding:"3px 10px",fontSize:10,fontWeight:700}}>Active</div>
              <div style={{color:"rgba(255,255,255,0.7)",fontSize:13,transform:waOpen?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
            </div>
          </div>
          {waOpen && (
            <div style={{display:"flex",flexDirection:"column",gap:0}}>
              {whatsappReminders.map((rem,i)=>{
                const isOpen = openRemId===rem.id;
                const isOrdered = orderedRem.includes(rem.id);
                const color = WA_REMINDER_COLORS[rem.status];
                const label = WA_REMINDER_LABELS[rem.status];
                return (
                  <div key={rem.id} style={{borderTop:i===0?"none":"1px solid #F7F5F2"}}>
                    <div onClick={()=>setOpenRemId(isOpen?null:rem.id)} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 16px",cursor:"pointer"}}>
                      <div style={{width:32,height:32,borderRadius:9,background:color+"18",display:"flex",alignItems:"center",justifyContent:"center",fontSize:16,flexShrink:0}}>{rem.icon}</div>
                      <div style={{flex:1,minWidth:0}}>
                        <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{rem.title}</div>
                        <div style={{fontSize:10,color,fontWeight:700,marginTop:1}}>{label}{rem.daysOut>0?` · ${rem.daysOut}d`:""}</div>
                      </div>
                      {isOrdered
                        ? <div style={{fontSize:11,color:"#34C759",fontWeight:700,flexShrink:0}}>✅ Done</div>
                        : <div style={{fontSize:13,color:"#C7C7CC",flexShrink:0,transform:isOpen?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
                      }
                    </div>
                    {isOpen && (
                      <div style={{background:"#ECE5DD",padding:"8px 12px",borderTop:"1px solid #E8E4DF"}}>
                        <div style={{background:"white",borderRadius:"4px 14px 14px 14px",padding:"10px 12px",maxWidth:"95%",boxShadow:"0 1px 2px rgba(0,0,0,0.1)"}}>
                          <div style={{fontWeight:600,fontSize:13,marginBottom:4}}>{rem.title}</div>
                          <div style={{fontSize:12,color:"#444",lineHeight:1.5}}>{rem.body}</div>
                          {!isOrdered && (
                            <div style={{display:"flex",flexDirection:"column",gap:5,marginTop:8}}>
                              {rem.actions.map((act,j)=>(
                                <button key={j} onClick={()=>{if(j===0)setOrderedRem(o=>[...o,rem.id]);setOpenRemId(null);}}
                                  style={{background:j===0?"#D44800":act.color,color:"white",border:"none",borderRadius:10,padding:"8px 12px",fontSize:12,fontWeight:700,cursor:"pointer",textAlign:"left"}}>
                                  {act.label}
                                </button>
                              ))}
                            </div>
                          )}
                          <div style={{fontSize:10,color:"#999",textAlign:"right",marginTop:5}}>{new Date().toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"})} ✓✓</div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Uploaded documents — collapsible */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #8E8E9322",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div onClick={()=>setOpenDocSection(openDocSection==="__main__"?null:"__main__")} style={{padding:"14px 16px",display:"flex",alignItems:"center",gap:12,cursor:"pointer"}}>
            <div style={{width:44,height:44,borderRadius:12,background:"#F7F4F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📂</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:15}}>Uploaded Documents</div>
              <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{DOC_SECTIONS.reduce((a,s)=>a+s.files.length,0)} records read & parsed</div>
            </div>
            <div style={{display:"flex",alignItems:"center",gap:8,flexShrink:0}}>
              <div style={{background:"#F0FFF4",color:"#34C759",borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>All Parsed</div>
              <div style={{fontSize:13,color:"#C7C7CC",transform:openDocSection==="__main__"?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
            </div>
          </div>
          {openDocSection==="__main__" && (
            <>
              <div style={{borderTop:"1px solid #F0EDE8"}}>
                {DOC_SECTIONS.map((sec,i)=>{
                  const isOpen = openDocSection===sec.id;
                  return (
                    <div key={sec.id} style={{borderTop:i===0?"none":"1px solid #F7F5F2"}}>
                      <div onClick={e=>{e.stopPropagation();setOpenDocSection(isOpen?null:sec.id);}} style={{display:"flex",alignItems:"center",gap:12,padding:"12px 16px",cursor:"pointer"}}>
                        <div style={{width:36,height:36,borderRadius:10,background:sec.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>{sec.icon}</div>
                        <div style={{flex:1}}>
                          <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{sec.label}</div>
                          <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{sec.files.length} document{sec.files.length>1?"s":""}</div>
                        </div>
                        <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
                          <div style={{background:sec.bg,color:sec.color,borderRadius:20,padding:"2px 9px",fontSize:10,fontWeight:700}}>✓ Parsed</div>
                          <div style={{fontSize:13,color:"#C7C7CC",transform:isOpen?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
                        </div>
                      </div>
                      {isOpen && (
                        <div style={{background:"#FAFAF9",borderTop:"1px solid #F0EDE8",padding:"8px 16px 12px",display:"flex",flexDirection:"column",gap:6}}>
                          {sec.files.map((f,j)=>(
                            <div key={j} style={{background:"white",borderRadius:10,padding:"10px 12px",border:`1px solid ${sec.color}22`}}>
                              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
                                <div style={{fontSize:13}}>📎</div>
                                <div style={{fontSize:11,color:"#8E8E93",flex:1,fontFamily:"monospace"}}>{f.name}</div>
                                <div style={{fontSize:10,color:"#34C759",fontWeight:700}}>{f.status}</div>
                              </div>
                              <div style={{fontSize:12,fontWeight:600,color:"#1A1A1A",marginBottom:2}}>{f.parsed}</div>
                              <div style={{fontSize:11,color:"#AEAEB2"}}>{f.note}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div style={{borderTop:"1px solid #F0EDE8",padding:"10px 16px"}}>
                <label style={{display:"flex",alignItems:"center",gap:10,cursor:"pointer",padding:"8px 0"}}>
                  <input type="file" accept="image/*,.pdf" style={{display:"none"}} onChange={()=>{}}/>
                  <div style={{width:36,height:36,borderRadius:10,background:"#D4480018",border:"1.5px dashed #D44800",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0,color:"#D44800",fontWeight:700}}>+</div>
                  <div>
                    <div style={{fontWeight:600,fontSize:13,color:"#D44800"}}>Upload new document</div>
                    <div style={{fontSize:11,color:"#AEAEB2"}}>Vaccination card, prescription, report…</div>
                  </div>
                </label>
              </div>
            </>
          )}
        </div>

        {/* ── CONTACTS CARD ────────────────────────────────────────────── */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #007AFF33",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div onClick={()=>setContactsOpen(o=>!o)} style={{padding:"14px 16px",display:"flex",alignItems:"center",gap:12,cursor:"pointer"}}>
            <div style={{width:44,height:44,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📋</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:15}}>Care Contacts</div>
              <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{contacts.length} contact{contacts.length!==1?"s":""} saved</div>
            </div>
            <div style={{fontSize:13,color:"#C7C7CC",transform:contactsOpen?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
          </div>
          {contactsOpen && (
            <div style={{borderTop:"1px solid #F0EDE8"}}>
              {contacts.length===0 && (
                <div style={{padding:"18px 16px",textAlign:"center",color:"#AEAEB2",fontSize:13}}>No contacts added yet. Tap "+ Add" to save your vet or groomer.</div>
              )}
              {contacts.map((ct,i)=>(
                <div key={ct.id} style={{display:"flex",alignItems:"flex-start",gap:12,padding:"12px 16px",borderTop:i===0?"none":"1px solid #F7F5F2"}}>
                  <div style={{width:40,height:40,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{ct.icon}</div>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontWeight:700,fontSize:13,color:"#1A1A1A"}}>{ct.name}</div>
                    <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>{ct.clinic}</div>
                    <a href={`tel:${ct.phone}`} onClick={e=>e.stopPropagation()}
                      style={{display:"inline-flex",alignItems:"center",gap:4,marginTop:5,background:"#F0F6FF",border:"none",borderRadius:20,padding:"3px 10px",fontSize:11,fontWeight:600,color:"#007AFF",textDecoration:"none",cursor:"pointer"}}>
                      📞 {ct.phone}
                    </a>
                    {ct.note && <div style={{fontSize:11,color:"#AEAEB2",marginTop:4,fontStyle:"italic"}}>{ct.note}</div>}
                  </div>
                  <div style={{display:"flex",flexDirection:"column",gap:5,flexShrink:0}}>
                    <button onClick={()=>{setContactForm({...ct});setEditContact(ct.id);}}
                      style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
                    <button onClick={()=>setContacts(prev=>prev.filter(c=>c.id!==ct.id))}
                      style={{background:"#FFF0F0",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#FF3B30",cursor:"pointer",fontWeight:700}}>✕</button>
                  </div>
                </div>
              ))}
              <div style={{borderTop:"1px solid #F0EDE8",padding:"10px 16px"}}>
                <button onClick={()=>{setContactForm({type:"vet",icon:"🩺",name:"",clinic:"",phone:"",note:""});setEditContact("new");}}
                  style={{display:"flex",alignItems:"center",gap:10,width:"100%",background:"none",border:"1.5px dashed #007AFF55",borderRadius:10,padding:"8px 12px",cursor:"pointer",color:"#007AFF",fontWeight:600,fontSize:12}}>
                  <div style={{width:20,height:20,borderRadius:"50%",background:"#007AFF18",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:700,flexShrink:0}}>+</div>
                  Add vet, groomer, trainer, or specialist
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Edit / Add Contact Sheet */}
        {editContact && (
          <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setEditContact(null)}>
            <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
              <div style={{fontWeight:700,fontSize:16,marginBottom:4}}>{editContact==="new"?"Add Contact":"Edit Contact"}</div>
              <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>Vet, groomer, trainer, or specialist</div>

              {/* Type selector */}
              <div style={{display:"flex",gap:6,marginBottom:16,flexWrap:"wrap"}}>
                {[{v:"vet",i:"🩺",l:"Vet"},{v:"groomer",i:"✂️",l:"Groomer"},{v:"trainer",i:"🏅",l:"Trainer"},{v:"specialist",i:"🔬",l:"Specialist"},{v:"other",i:"📞",l:"Other"}].map(opt=>(
                  <button key={opt.v} onClick={()=>setContactForm(f=>({...f,type:opt.v,icon:opt.i}))}
                    style={{padding:"6px 12px",borderRadius:20,border:"none",background:contactForm.type===opt.v?"#007AFF":"#F2EDE8",color:contactForm.type===opt.v?"white":"#555",fontWeight:600,fontSize:12,cursor:"pointer"}}>
                    {opt.i} {opt.l}
                  </button>
                ))}
              </div>

              {[["Name / Clinic name","name","Dr. Meera Nair"],["Address / Location","clinic","Paws & Claws Clinic, Bandra"],["Phone number","phone","+91 98200 00000"],["Note (optional)","note","e.g. Managing urinary health"]].map(([lbl,key,ph])=>(
                <div key={key} style={{marginBottom:12}}>
                  <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>{lbl}</div>
                  <input value={contactForm[key]||""} onChange={e=>setContactForm(f=>({...f,[key]:e.target.value}))} placeholder={ph}
                    style={{width:"100%",padding:"10px 14px",borderRadius:12,border:"1.5px solid #E8E4DF",fontSize:13,outline:"none",boxSizing:"border-box",color:"#1A1A1A",fontFamily:"'DM Sans',sans-serif"}}/>
                </div>
              ))}

              <button onClick={()=>{
                if(!contactForm.name) return;
                if(editContact==="new") {
                  setContacts(prev=>[...prev,{...contactForm,id:"ct"+Date.now()}]);
                } else {
                  setContacts(prev=>prev.map(c=>c.id===editContact?{...c,...contactForm}:c));
                }
                setEditContact(null);
              }} style={{width:"100%",background:"#007AFF",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:"pointer",marginTop:4}}>
                Save Contact
              </button>
              <button onClick={()=>setEditContact(null)} style={{width:"100%",background:"none",border:"none",color:"#8E8E93",padding:"10px",fontSize:13,cursor:"pointer",marginTop:4}}>Cancel</button>
            </div>
          </div>
        )}

      </div>
    );
  };

  // ── HEALTH TAB ────────────────────────────────────────────────────────────
  const renderMedicalTab = () => {
    const vaccines = pet.healthRecords.vaccines;
    const rows = vaccines.map(v => {
      const vs = vaccineState[v.id];
      const nextDue = addMonths(vs.lastGiven, vs.freqMonths);
      return { ...v, lastGiven:vs.lastGiven, freqMonths:vs.freqMonths, nextDue, status:getVaxStatus(vs.lastGiven, nextDue) };
    });
    const overdueCount  = rows.filter(r=>r.status==="overdue"||r.status==="missing").length;
    const upcomingCount = rows.filter(r=>r.status==="upcoming").length;
    const ovColor = overdueCount?"#FF3B30":upcomingCount?"#FF9500":"#34C759";
    const ovBg    = overdueCount?"#FFF0F0":upcomingCount?"#FFF6ED":"#F0FFF4";
    const ovLabel = overdueCount?"Attention needed":upcomingCount?"Due Soon":"Up to date";

    const renderVaxRow = (v, isMandatory) => {
      const c   = (v.status==="overdue"||v.status==="missing") ? "#FF3B30" : v.status==="upcoming"?"#FF9500":"#34C759";
      const lbl = v.status==="overdue"?"Overdue":v.status==="missing"?(isMandatory?"Not recorded":"Not given"):v.status==="upcoming"?"Due Soon":"Up to date";
      const sub = v.lastGiven ? ("Given: " + v.lastGiven + (v.nextDue ? "  ·  Next: " + v.nextDue : "")) : isMandatory?"No record":"Not given yet";
      return (
        <div key={v.id} style={{background:"#FAFAF9",borderRadius:10,border:`1px solid ${c}22`,...(!isMandatory?{overflow:"hidden"}:{})}}>
          <div style={{display:"flex",alignItems:"center",gap:10,padding:"8px 10px"}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:c,flexShrink:0}}/>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontSize:13,fontWeight:600,color:"#1A1A1A"}}>{v.name}</div>
              <div style={{fontSize:11,color:"#AEAEB2",marginTop:2}}>{sub}</div>
            </div>
            <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
              <div style={{background:c+"18",color:c,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:700}}>{lbl}</div>
              <button onClick={()=>{setEditingVaxDate(v.id);setVaxDateInput(v.lastGiven||"");}}
                style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
            </div>
          </div>
          {!isMandatory && (
            <div style={{display:"flex",alignItems:"center",gap:8,padding:"6px 10px 8px",borderTop:"1px solid #F0EDE8"}}>
              <div style={{fontSize:11,color:"#8E8E93",flex:1}}>🔔 Reminder</div>
              <div onClick={()=>setVaxFreqModal({id:v.id,freqMonths:vaccineState[v.id].freqMonths})}
                style={{display:"inline-flex",alignItems:"center",gap:4,background:vaccineState[v.id].reminder?"#EFF6FF":"#F2F2F7",color:vaccineState[v.id].reminder?"#007AFF":"#AEAEB2",borderRadius:20,padding:"3px 10px",fontSize:11,fontWeight:600,cursor:"pointer"}}>
                🔁 {v.freqMonths===12?"Yearly":`Every ${v.freqMonths}m`} <span style={{fontSize:10,opacity:0.7}}>✎</span>
              </div>
              <Toggle on={!!vaccineState[v.id].reminder} onToggle={()=>setVaccineState(s=>({...s,[v.id]:{...s[v.id],reminder:!s[v.id].reminder}}))}/>
            </div>
          )}
        </div>
      );
    };

    return (
      <div style={{display:"flex",flexDirection:"column",gap:12,animation:"slideUp 0.4s ease"}}>
        {/* Vaccination card */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:`1.5px solid ${ovColor}44`,boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{padding:"14px 16px 10px",display:"flex",alignItems:"center",gap:12}}>
            <div style={{width:44,height:44,borderRadius:12,background:ovBg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>💉</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:15}}>Vaccinations</div>
              <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{overdueCount?`${overdueCount} need attention`:upcomingCount?`${upcomingCount} due soon`:"All vaccines current"}</div>
            </div>
            <div style={{background:ovBg,color:ovColor,borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>{ovLabel}</div>
          </div>
          <div style={{padding:"4px 16px 0",fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5}}>Mandatory</div>
          <div style={{borderTop:"1px solid #F5F2EE",padding:"8px 16px 10px",display:"flex",flexDirection:"column",gap:6}}>
            {rows.filter(r=>r.mandatory).map(v=>renderVaxRow(v,true))}
          </div>
          <div style={{padding:"4px 16px 0",fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,borderTop:"1px solid #F5F2EE",paddingTop:10}}>Optional</div>
          <div style={{padding:"8px 16px 14px",display:"flex",flexDirection:"column",gap:6}}>
            {rows.filter(r=>!r.mandatory).map(v=>renderVaxRow(v,false))}
            <AddRow label="Add vaccine" onClick={()=>{ setAddForm({}); setAddSheet({type:"vaccine"}); }}/>
          </div>
          {(overdueCount>0||upcomingCount>0) && (
            <div style={{padding:"0 16px 14px"}}>
              <button onClick={()=>onCart("c1")}
                style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
                Book Now
              </button>
            </div>
          )}
        </div>

        {/* Deworming / Flea-tick */}
        <CareCard icon="🪱" title="Deworming"            product="Milbemax · Every 3 months"      lastDone={dwLastDone}  freqMonths={3}  editKey="deworming" reminderId="deworming" cartId="c2"/>
        <CareCard icon="🐛" title="Flea & Tick Protection" product="Bravecto · Every month"         lastDone={ftLastDone}  freqMonths={1}  editKey="fleaTick"  reminderId="flea-tick" cartId="c5"/>

        {/* Preventive Check-up Plan */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #8E8E9344",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          {(()=>{
            // ── Sample bundles: group tests that use the same sample/visit ─────
            // Each bundle = one parent action (one trip / one sample)
            // Sub-items = individual tests ordered from that sample
            const bundles = [
              {
                // ── BLOOD SAMPLE ─────────────────────────────────────────────
                id:"bundle-blood",
                sampleIcon:"🩸",
                sampleLabel:"Blood Sample",
                actionLabel:"1 blood draw at home lab",
                tests: [
                  {
                    id:"chk-blood",
                    icon:"🩸",
                    name:"CBC + Chemistry Panel",
                    note:"Organ function, anaemia, infection markers",
                    source:"vet", rxDate:"Feb 2025", rxBy:"Dr. Chavan",
                    urgency:0,
                  },
                  {
                    id:"chk-cbc",
                    icon:"🔢",
                    name:"Manual Platelet Count",
                    note:"Automated machines under-read Zayn's — always request manual",
                    source:"petcircle", rxDate:null, rxBy:null,
                    urgency:0,
                  },
                  {
                    id:"chk-pcr",
                    icon:"🔬",
                    name:"Q-PCR — Anaplasma platys",
                    note:"PCR confirmed Nov 2023 (CT 22.1) — never treated, 2+ yrs overdue",
                    source:"petcircle", rxDate:null, rxBy:null,
                    urgency:0,
                  },
                ],
              },
              {
                // ── URINE SAMPLE ─────────────────────────────────────────────
                id:"bundle-urine",
                sampleIcon:"💧",
                sampleLabel:"Urine Sample",
                actionLabel:"1 urine sample — 2 tests run on it",
                tests: [
                  {
                    id:"chk-culture",
                    icon:"🧫",
                    name:"Urine Culture",
                    note:"Confirms E. coli clearance post-Augmentin. Prescribed by Dr. Chavan (Sep 2025). PetCircle recommends repeating every 6 months given 3 UTI episodes.",
                    source:"both",
                    rxDate:"Sep 2025", rxBy:"Dr. Chavan",
                    urgency:0,
                  },
                  {
                    id:"chk-urine",
                    icon:"🧪",
                    name:"Urinalysis",
                    note:"Monitors for silent inflammation between UTI episodes",
                    source:"petcircle", rxDate:null, rxBy:null,
                    urgency:1,
                  },
                ],
              },
              {
                // ── VET VISIT ────────────────────────────────────────────────
                id:"bundle-vet",
                sampleIcon:"🩺",
                sampleLabel:"Vet Visit",
                actionLabel:"Annual wellness exam",
                tests: [
                  {
                    id:"chk-vet",
                    icon:"🩺",
                    name:"Annual Wellness Exam",
                    note:"Full physical — weight, coat, ears, teeth, joints, general health",
                    source:"vet", rxDate:null, rxBy:null,
                    urgency:0,
                  },
                ],
              },
            ];

            // Flatten for progress calculation
            const allTests = bundles.flatMap(b=>b.tests);
            const doneCount = allTests.filter(t=>checkupDates[t.id]).length;
            const pct = Math.round((doneCount/allTests.length)*100);
            const barColor = pct===100?"#34C759":pct>=50?"#FF9500":"#FF3B30";
            const statusLabel = pct===100?"Up to Date":pct===0?"No Record":"In Progress";
            const statusColor = pct===100?"#34C759":pct===0?"#8E8E93":"#FF9500";
            const statusBg    = pct===100?"#F0FFF4":pct===0?"#F2F2F7":"#FFF6ED";

            const srcChip = (source, rxDate, rxBy) => {
              if (source==="both") return (
                <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
                  <span style={{background:"#F0F6FF",color:"#007AFF",borderRadius:20,padding:"1px 7px",fontSize:9,fontWeight:700}}>Vet Prescribed {rxDate ? "· "+rxDate : ""}</span>
                  <span style={{background:"#FFF3EE",color:"#D44800",borderRadius:20,padding:"1px 7px",fontSize:9,fontWeight:700}}>🐾 +PetCircle · repeat 6-monthly</span>
                </div>
              );
              if (source==="vet") return (
                <span style={{background:"#F0F6FF",color:"#007AFF",borderRadius:20,padding:"1px 7px",fontSize:9,fontWeight:700}}>
                  Vet Prescribed{rxDate ? " · "+rxDate : ""}
                </span>
              );
              return (
                <span style={{background:"#FFF3EE",color:"#D44800",borderRadius:20,padding:"1px 7px",fontSize:9,fontWeight:700}}>
                  🐾 PetCircle Recommended
                </span>
              );
            };

            return (
              <>
                {/* Header */}
                <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:10}}>
                  <div style={{width:44,height:44,borderRadius:12,background:"#F2F2F7",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>🩺</div>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700,fontSize:15}}>Preventive Check-up Plan</div>
                    <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Personalised · vet prescriptions + Zayn's health profile</div>
                  </div>
                  <div style={{background:statusBg,color:statusColor,borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>{statusLabel}</div>
                </div>

                {/* Progress bar */}
                <div style={{marginBottom:14}}>
                  <div style={{display:"flex",justifyContent:"space-between",fontSize:11,color:"#8E8E93",marginBottom:4}}>
                    <span>{doneCount}/{allTests.length} tests completed</span>
                    <span style={{fontWeight:700,color:barColor}}>{pct}%</span>
                  </div>
                  <div style={{height:6,borderRadius:3,background:"#F2F2F7",overflow:"hidden"}}>
                    <div style={{height:"100%",borderRadius:3,background:barColor,width:pct+"%",transition:"width 0.5s ease"}}/>
                  </div>
                </div>

                {/* Sample bundles */}
                <div style={{display:"flex",flexDirection:"column",gap:10,marginBottom:10}}>
                  {bundles.map((bundle)=>{
                    const bundleDone = bundle.tests.filter(t=>checkupDates[t.id]).length;
                    const bundleTotal = bundle.tests.length;
                    const allDone = bundleDone===bundleTotal;
                    const anyDone = bundleDone>0;
                    const bColor = allDone?"#34C759":anyDone?"#FF9500":"#8E8E93";
                    const bBg    = allDone?"#F0FFF4":anyDone?"#FFF6ED":"#F2F2F7";
                    const bLbl   = allDone?"Done":anyDone?"In Progress":"No Record";

                    return (
                      <div key={bundle.id} style={{border:"1.5px solid "+bColor+"33",borderRadius:12,overflow:"hidden",background:"white"}}>
                        {/* Bundle header — the "one action" */}
                        <div style={{display:"flex",alignItems:"center",gap:10,padding:"10px 12px",background:bBg+"88"}}>
                          <div style={{width:34,height:34,borderRadius:10,background:bBg,border:"1.5px solid "+bColor+"44",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>{bundle.sampleIcon}</div>
                          <div style={{flex:1,minWidth:0}}>
                            <div style={{fontWeight:700,fontSize:13,color:"#1A1A1A"}}>{bundle.sampleLabel}</div>
                            <div style={{fontSize:10.5,color:"#8E8E93",marginTop:1}}>{bundle.actionLabel}</div>
                          </div>
                          <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
                            <div style={{background:bBg,color:bColor,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:700}}>{bLbl}</div>
                            {bundleTotal>1&&<div style={{background:"#F2F2F7",color:"#8E8E93",borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:600}}>{bundleTotal} tests</div>}
                          </div>
                        </div>

                        {/* Sub-tests — individual components of this sample */}
                        <div style={{display:"flex",flexDirection:"column"}}>
                          {bundle.tests.map((t, ti)=>{
                            const last = checkupDates[t.id];
                            const nextDue = last ? addMonths(last, t.id==="chk-urine"||t.id==="chk-culture" ? 6 : 12) : null;
                            const diff = nextDue ? diffDaysFromToday(nextDue) : null;
                            const status = !last ? "missing" : diff < 0 ? "overdue" : diff <= 60 ? "upcoming" : "done";
                            const c  = status==="done"?"#34C759":status==="overdue"?"#FF3B30":status==="upcoming"?"#FF9500":"#8E8E93";
                            const bg = status==="done"?"#F0FFF4":status==="overdue"?"#FFF0F0":status==="upcoming"?"#FFF6ED":"#F2F2F7";
                            const lbl= status==="done"?"Done":status==="overdue"?"Overdue":status==="upcoming"?"Due Soon":"No Record";
                            return (
                              <div key={t.id} style={{borderTop:"1px solid #F0EDE8",padding:"9px 12px 0"}}>
                                <div style={{display:"flex",alignItems:"flex-start",gap:8}}>
                                  {/* Indent line to show sub-item */}
                                  <div style={{width:2,alignSelf:"stretch",background:c+"44",borderRadius:2,flexShrink:0,marginTop:3,marginLeft:6}}/>
                                  <div style={{flex:1,minWidth:0}}>
                                    <div style={{display:"flex",alignItems:"center",gap:5,flexWrap:"wrap",marginBottom:3}}>
                                      <span style={{fontSize:12,fontWeight:600,color:"#1A1A1A"}}>{t.name}</span>
                                      {srcChip(t.source, t.rxDate, t.rxBy)}
                                    </div>
                                    <div style={{fontSize:10.5,color:"#AEAEB2",lineHeight:1.4,marginBottom:4}}>
                                      {last
                                        ? ("Last: " + last + (nextDue ? " · Next: " + nextDue : ""))
                                        : t.note}
                                    </div>
                                    <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8}}>
                                      <div style={{background:bg,color:c,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>{lbl}</div>
                                      <button onClick={()=>{setEditingCheckupId(t.id);setCheckupDateInput(last||"");}}
                                        style={{background:"#F2EDE8",border:"none",borderRadius:7,padding:"3px 7px",fontSize:10,color:"#555",cursor:"pointer",fontWeight:600}}>✎ Log</button>
                                    </div>
                                  </div>
                                </div>
                                {/* Reminder bar for this specific test */}
                                <div style={{marginLeft:16,marginBottom:8}}>
                                  <ReminderBar id={t.id} settings={itemSettings} setSettings={setItemSettings} onFreqClick={setFreqModal}/>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <AddRow label="Add checkup record" onClick={()=>{ setAddForm({}); setAddSheet({type:"diagnostic"}); }}/>
                <div style={{height:10}}/>
                <button onClick={()=>onCart("c14")}
                  style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
                  Book Now
                </button>
              </>
            );
          })()}
        </div>

        {/* Weight Log */}
        {(()=>{
          const entries = [
            { date:"Feb 2025",    weight:29.0, note:"Vet visit — Dr. Chavan prescription (12 Feb 2025)" },
            { date:"Sep 2025",    weight:30.0, note:"Vet visit — UTI workup, Fredna Vet Diagnostics" },
          ];
          const latest = entries[entries.length-1];
          const prev    = entries[entries.length-2];
          const diff    = (latest.weight - prev.weight).toFixed(1);
          const trend   = diff > 0 ? "up" : diff < 0 ? "down" : "stable";
          const tColor  = trend==="up"?"#FF9500":trend==="down"?"#34C759":"#007AFF";
          const tIcon   = trend==="up"?"↑":trend==="down"?"↓":"→";
          const ideal   = { min:27, max:34 };
          const inRange = latest.weight >= ideal.min && latest.weight <= ideal.max;

          // Chart: use a sensible baseline so bars look meaningfully different
          const chartMin  = 25; // floor — anything below this is off-chart for a Labrador
          const chartMax  = 36; // ceiling
          const chartH    = 80; // total bar area height in px
          const barHeightPx = (w) => Math.round(((w - chartMin) / (chartMax - chartMin)) * chartH);

          // Y-axis guide lines
          const yGuides = [27, 30, 34]; // ideal min, Zayn current, ideal max

          return (
            <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #007AFF33",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
              <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
                <div style={{width:44,height:44,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>⚖️</div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:700,fontSize:15}}>Weight Log</div>
                  <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Ideal range for Labrador: {ideal.min}–{ideal.max} kg</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontWeight:800,fontSize:20,color:"#1A1A1A",lineHeight:1}}>{latest.weight} <span style={{fontSize:12,fontWeight:500,color:"#8E8E93"}}>kg</span></div>
                  <div style={{fontSize:11,fontWeight:700,color:tColor}}>{tIcon} {Math.abs(diff)} kg since last</div>
                </div>
              </div>

              {/* Status pill */}
              <div style={{background:inRange?"#F0FFF4":"#FFF6ED",border:"1px solid "+(inRange?"#34C75944":"#FF950044"),borderRadius:8,padding:"6px 10px",marginBottom:16,fontSize:11,color:inRange?"#1A6B2A":"#8B5E00",fontWeight:600}}>
                {inRange?"✅ Weight is within healthy range for Zayn's breed & age":"⚠️ Weight slightly above ideal — monitor closely. Obesity increases UTI risk in neutered males"}
              </div>

              {/* Bar chart with baseline + ideal band */}
              <div style={{position:"relative",marginBottom:4}}>
                {/* Ideal range shaded band */}
                {(()=>{
                  const bandTop    = chartH - barHeightPx(ideal.max);
                  const bandBottom = chartH - barHeightPx(ideal.min);
                  const bandHeight = bandBottom - bandTop;
                  return (
                    <div style={{position:"absolute",left:32,right:0,top:bandTop,height:bandHeight,background:"rgba(52,199,89,0.08)",borderTop:"1px dashed #34C75966",borderBottom:"1px dashed #34C75966",pointerEvents:"none",zIndex:0}}/>
                  );
                })()}

                <div style={{display:"flex",alignItems:"flex-end",gap:0,height:chartH,paddingLeft:32,position:"relative",zIndex:1}}>
                  {entries.map((e,i)=>{
                    const h = barHeightPx(e.weight);
                    const isLast = i===entries.length-1;
                    const barColor = isLast?"#007AFF":"#007AFF55";
                    return (
                      <div key={i} style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"flex-end",gap:4,height:"100%",paddingBottom:0}}>
                        <div style={{fontSize:10,fontWeight:700,color:isLast?"#007AFF":"#8E8E93"}}>{e.weight} kg</div>
                        <div style={{width:"60%",height:h,borderRadius:"4px 4px 0 0",background:barColor,transition:"height 0.5s ease"}}/>
                      </div>
                    );
                  })}
                </div>

                {/* Y-axis labels */}
                <div style={{position:"absolute",left:0,top:0,bottom:0,width:28,display:"flex",flexDirection:"column",justifyContent:"space-between",paddingBottom:0}}>
                  {[chartMax, 30, chartMin].map((v,i)=>(
                    <div key={i} style={{fontSize:8,color:"#C7C7CC",lineHeight:1,textAlign:"right",paddingRight:4}}>{v}</div>
                  ))}
                </div>

                {/* Baseline */}
                <div style={{height:1,background:"#E8E4DF",marginLeft:32}}/>
              </div>

              {/* X-axis labels */}
              <div style={{display:"flex",paddingLeft:32,marginBottom:14}}>
                {entries.map((e,i)=>(
                  <div key={i} style={{flex:1,textAlign:"center",fontSize:10,color:"#AEAEB2",marginTop:4}}>{e.date}</div>
                ))}
              </div>

              {/* Ideal range legend */}
              <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:14}}>
                <div style={{width:12,height:8,background:"rgba(52,199,89,0.15)",border:"1px dashed #34C75966",borderRadius:2}}/>
                <div style={{fontSize:10,color:"#8E8E93"}}>Ideal range: {ideal.min}–{ideal.max} kg</div>
              </div>

              {/* Log table */}
              <div style={{display:"flex",flexDirection:"column",gap:4}}>
                {[...entries].reverse().map((e,i)=>(
                  <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"7px 10px",background:i===0?"#F0F6FF":"#FAFAF9",borderRadius:8,border:i===0?"1px solid #007AFF22":"1px solid #F0EDE8"}}>
                    <div style={{fontSize:11,color:"#8E8E93",width:64,flexShrink:0,fontWeight:600}}>{e.date}</div>
                    <div style={{fontWeight:700,fontSize:13,color:"#1A1A1A",flexShrink:0}}>{e.weight} kg</div>
                    <div style={{fontSize:11,color:"#AEAEB2",flex:1}}>{e.note}</div>
                    {i===0&&<div style={{fontSize:10,fontWeight:700,color:"#007AFF",flexShrink:0}}>Latest</div>}
                  </div>
                ))}
              </div>
              <AddRow label="Log weight" onClick={()=>{ setAddForm({}); setAddSheet({type:"weight"}); }}/>
            </div>
          );
        })()}

      </div>
    );
  };

  // ── NUTRITION TAB ─────────────────────────────────────────────────────────
  const renderNutritionTab = () => {
    const food = pet.healthRecords.nutrition;
    const calTarget=1450, calActual=1280;
    const calDiff   = calActual - calTarget;
    const calStatus = calDiff < -100 ? "low" : calDiff > 150 ? "high" : "ok";
    const calC      = calStatus==="ok"?"#34C759":calStatus==="low"?"#FF9500":"#FF3B30";
    const calBg     = calStatus==="ok"?"#F0FFF4":calStatus==="low"?"#FFF6ED":"#FFF0F0";
    const calLbl    = calStatus==="ok"?"On target":calStatus==="low"?"Below target":"Above target";
    const calPct    = Math.round((calActual/calTarget)*100);

    const visibleMacros = NUTRITION_MACROS.filter(m=>m.name==="Protein"||m.status!=="ok");
    const vitaminGaps   = NUTRITION_VITAMINS.filter(v=>v.status!=="Adequate");
    const vitaminOverall= vitaminGaps.some(v=>v.priority==="high")?"#FF3B30":vitaminGaps.length?"#FF9500":"#34C759";
    const vitaminBg     = vitaminOverall==="#34C759"?"#F0FFF4":vitaminOverall==="#FF9500"?"#FFF6ED":"#FFF0F0";
    const vitaminLbl    = vitaminOverall==="#34C759"?"Adequate":vitaminGaps.some(v=>v.status==="Missing")?"Missing":"Low";

    const priorityRank = {urgent:0,high:1,medium:2,ok:3};

    const NutrientRow = ({ icon, name, status, priority, reason, supplement, price, unit, actual, target }) => {
      const c   = status==="Missing"?"#FF3B30":status==="Low"||status==="high"?"#FF9500":status==="High"?"#FF3B30":"#34C759";
      const bg  = status==="Missing"?"#FFF0F0":status==="Low"||status==="high"?"#FFF6ED":status==="High"?"#FFF0F0":"#F0FFF4";
      const lbl = status==="Missing"?"Missing":status==="Low"?"Low":status==="High"||status==="high"?"High":"Adequate";
      return (
        <div style={{display:"flex",alignItems:"flex-start",gap:10,padding:"9px 10px",background:"#FAFAF9",borderRadius:10,border:`1px solid ${c}22`}}>
          <div style={{fontSize:16,flexShrink:0,marginTop:1}}>{icon||"•"}</div>
          <div style={{flex:1}}>
            <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:2,flexWrap:"wrap"}}>
              <span style={{fontWeight:600,fontSize:13}}>{name}</span>
              <div style={{background:bg,color:c,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>{lbl}</div>
              {priority==="urgent"&&<div style={{background:"#FF3B30",color:"white",borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>Urgent</div>}
            </div>
            {reason&&<div style={{fontSize:11,color:"#8E8E93",lineHeight:1.4}}>{reason}</div>}
            {actual!=null&&<div style={{fontSize:11,color:"#8E8E93"}}>{actual}{unit} · target {target}{unit}</div>}
            {supplement&&<div style={{fontSize:11,color:"#007AFF",marginTop:3}}>→ {supplement} · {price}</div>}
          </div>
        </div>
      );
    };

    return (
      <div style={{display:"flex",flexDirection:"column",gap:12,animation:"slideUp 0.4s ease"}}>
        {/* Current diet */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1px solid #F0EDE8",boxShadow:"0 1px 4px rgba(0,0,0,0.06)"}}>
          <div style={{fontWeight:700,fontSize:14,marginBottom:12}}>🥣 Current diet</div>
          {dietRows.map((row,i)=>(
            <div key={row.id} style={{display:"flex",alignItems:"center",gap:10,padding:"9px 0",borderTop:i===0?"none":"1px solid #F0EDE8"}}>
              <div style={{fontSize:18,flexShrink:0}}>{row.icon}</div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{row.label}</div>
                <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>{row.detail}</div>
              </div>
              <div style={{display:"flex",gap:5,flexShrink:0}}>
                <button onClick={()=>{ setEditDietRow(row); setEditDietForm({label:row.label,detail:row.detail}); }}
                  style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
                <button onClick={()=>setDietRows(prev=>prev.filter(r=>r.id!==row.id))}
                  style={{background:"#FFF0F0",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#FF3B30",cursor:"pointer",fontWeight:700}}>✕</button>
              </div>
            </div>
          ))}
          <AddRow label="Add food" onClick={()=>{ setAddForm({}); setAddSheet({type:"addFood"}); }}/>
          <div style={{marginTop:12,fontSize:11,color:"#8E8E93",marginBottom:6,fontWeight:600,textTransform:"uppercase",letterSpacing:0.5}}>Current supplements</div>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {food.supplements.map((s,i)=>(
              <div key={i} style={{background:"#F0F6FF",color:"#007AFF",borderRadius:8,padding:"3px 10px",fontSize:12,fontWeight:600}}>✓ {s}</div>
            ))}
          </div>
          <AddRow label="Add supplement" onClick={()=>{ setAddForm({}); setAddSheet({type:"supplement"}); }}/>
        </div>

        {/* Edit diet row sheet */}
        {editDietRow && (
          <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setEditDietRow(null)}>
            <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
              <div style={{width:40,height:4,background:"#E0E0E0",borderRadius:2,margin:"0 auto 20px"}}/>
              <div style={{fontWeight:700,fontSize:16,marginBottom:18}}>Edit food item</div>
              <div style={{display:"flex",flexDirection:"column",gap:12}}>
                <div>
                  <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Name / brand</div>
                  <input value={editDietForm.label} onChange={e=>setEditDietForm(f=>({...f,label:e.target.value}))} placeholder="e.g. Royal Canin Adult"
                    style={{width:"100%",padding:"10px 14px",borderRadius:10,border:"1.5px solid #E8E4DF",fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif"}}/>
                </div>
                <div>
                  <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Quantity / frequency</div>
                  <input value={editDietForm.detail} onChange={e=>setEditDietForm(f=>({...f,detail:e.target.value}))} placeholder="e.g. 280g · 2x/day"
                    style={{width:"100%",padding:"10px 14px",borderRadius:10,border:"1.5px solid #E8E4DF",fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif"}}/>
                </div>
              </div>
              <button onClick={()=>{ setDietRows(prev=>prev.map(r=>r.id===editDietRow.id?{...r,label:editDietForm.label,detail:editDietForm.detail}:r)); setEditDietRow(null); }}
                style={{width:"100%",marginTop:20,background:editDietForm.label?"#D44800":"#D1D1D6",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:editDietForm.label?"pointer":"default"}}>
                Save
              </button>
              <button onClick={()=>{ setDietRows(prev=>prev.filter(r=>r.id!==editDietRow.id)); setEditDietRow(null); }}
                style={{width:"100%",marginTop:8,background:"none",border:"1.5px solid #FF3B3044",borderRadius:12,padding:"11px",fontSize:13,fontWeight:600,color:"#FF3B30",cursor:"pointer"}}>
                Delete this item
              </button>
              <button onClick={()=>setEditDietRow(null)} style={{width:"100%",background:"none",border:"none",color:"#8E8E93",padding:"10px",fontSize:13,cursor:"pointer",marginTop:2}}>Cancel</button>
            </div>
          </div>
        )}

        {/* Order reminders */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1px solid #F0EDE8",boxShadow:"0 1px 4px rgba(0,0,0,0.06)"}}>
          <div style={{fontWeight:700,fontSize:14,marginBottom:8}}>🔔 Order reminders</div>
          <div style={{background:"#F7F4F0",borderRadius:10,padding:"12px 14px",fontSize:12,color:"#8E8E93",lineHeight:1.5}}>
            No food or supplement information recorded for Zayn. Add diet details above to set up order reminders.
          </div>
          <AddRow label="Add food or supplement" onClick={()=>{ setAddForm({}); setAddSheet({type:"addFood"}); }}/>
        </div>

        {/* Nutrition insight summary */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #D4480033",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
            <div style={{width:38,height:38,borderRadius:10,background:"#FFF3EE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>🐾</div>
            <div style={{fontWeight:700,fontSize:14,color:"#1A1A1A"}}>Nutrition note</div>
          </div>
          <div style={{background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#8B5E00",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>Overall diet</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Diet not recorded — macros and calorie analysis unavailable. Add Zayn's food to get a full breakdown.</div>
          </div>
          <div style={{background:"#F0F6FF",border:"1px solid #007AFF33",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#005BBB",textTransform:"uppercase",letterSpacing:0.4,marginBottom:5}}>What to address (based on health records)</div>
            {NUTRITION_IMPROVE.map((item,i)=>(
              <div key={i} style={{display:"flex",alignItems:"flex-start",gap:7,marginBottom:i===NUTRITION_IMPROVE.length-1?0:5}}>
                <div style={{width:6,height:6,borderRadius:"50%",background:item.dot,flexShrink:0,marginTop:4}}/>
                <span style={{fontSize:12,color:"#333",lineHeight:1.4}}>{item.text}</span>
              </div>
            ))}
          </div>
          <div style={{background:"#F0FFF4",border:"1px solid #34C75933",borderRadius:10,padding:"8px 11px",marginBottom:14}}>
            <div style={{fontSize:10,fontWeight:700,color:"#1A6B2A",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>PetCircle recommendation</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Start probiotics + cranberry/urinary support immediately given UTI history. Add diet details for full nutrition analysis.</div>
          </div>
        </div>

        {/* Supplement recommendations based on health records */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #FF9500",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{background:"#FFF3EE",padding:"14px 16px",borderBottom:"1px solid #F5C4AE44"}}>
            <div style={{display:"flex",alignItems:"center",gap:10}}>
              <div style={{width:3,height:36,background:"#D44800",borderRadius:2,flexShrink:0}}/>
              <div style={{flex:1}}>
                <div style={{display:"flex",alignItems:"center",gap:7,marginBottom:2}}>
                  <div style={{fontWeight:800,fontSize:15,color:"#1A1A1A",letterSpacing:-0.2}}>Supplement Recommendations</div>
                  <div style={{background:"#FFF3EE",border:"1.5px solid #D4480044",color:"#D44800",borderRadius:20,padding:"2px 8px",fontSize:9,fontWeight:700}}>🐾 PetCircle Recommended</div>
                </div>
                <div style={{fontSize:11,color:"#9B6040",marginTop:0}}>Based on Zayn's health records · not diet (not recorded)</div>
              </div>
              <div style={{background:"white",color:"#D44800",borderRadius:20,padding:"4px 12px",fontSize:11,fontWeight:700,boxShadow:"0 1px 4px rgba(212,72,0,0.12)"}}>3 Missing</div>
            </div>
          </div>
          <div style={{padding:16}}>
            <div style={{fontSize:11,color:"#8B5E00",background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:10,padding:"7px 10px",marginBottom:12}}>
              💡 Calorie and macro analysis requires diet information. Add Zayn's food above to unlock full breakdown.
            </div>

            {/* Supplements derived from health records */}
            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Based on health records</div>
            <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:14}}>
              {[...NUTRITION_MINERALS].sort((a,b)=>{const r={urgent:0,high:1,medium:2,ok:3};return r[a.priority]-r[b.priority];}).map((m,i)=><NutrientRow key={i} {...m}/>)}
            </div>

            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Other key supplements</div>
            <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:14}}>
              {[...NUTRITION_OTHERS].sort((a,b)=>{const r={urgent:0,high:1,medium:2,ok:3};return r[a.priority]-r[b.priority];}).map((m,i)=><NutrientRow key={i} {...m}/>)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ── HYGIENE TAB ────────────────────────────────────────────────────────────
  const renderGroomingTab = () => {
    const FreqPill = ({ id }) => {
      const s = hygieneSettings[id];
      return (
        <div onClick={e=>{ e.stopPropagation(); setFreqModal({id,freq:s.freq,unit:s.unit}); }}
          style={{display:"inline-flex",alignItems:"center",gap:4,background:"#F0F6FF",color:"#007AFF",borderRadius:20,padding:"3px 10px",fontSize:11,fontWeight:600,cursor:"pointer",flexShrink:0}}>
          🔁 {freqLabel(s.freq,s.unit)} <span style={{fontSize:10,opacity:0.7}}>✎</span>
        </div>
      );
    };

    return (
      <div style={{display:"flex",flexDirection:"column",gap:14,animation:"slideUp 0.4s ease"}}>
        <div style={{background:"#FFF6ED",border:"1px solid #FF9500",borderRadius:12,padding:"10px 14px",fontSize:12,color:"#8B5E00"}}>
          💡 Frequencies are breed-adjusted for Labradors. Tap the frequency pill to customise.
        </div>

        {/* Daily activities */}
        <div>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,marginBottom:8,paddingLeft:2}}>🌅 Frequent activities</div>
          <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1px solid #F0EDE8",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
            {DAILY_HYGIENE_ITEMS.map((item,i)=>{
              const c  = item.status==="done"?"#34C759":item.status==="overdue"?"#FF3B30":item.status==="upcoming"?"#FF9500":"#8E8E93";
              const bg = item.status==="done"?"#F0FFF4":item.status==="overdue"?"#FFF0F0":item.status==="upcoming"?"#FFF6ED":"#F2F2F7";
              const lbl= item.status==="done"?"Done":item.status==="overdue"?"Overdue":item.status==="upcoming"?"Due Soon":"Missing";
              return (
                <div key={item.id} style={{padding:"13px 16px",borderTop:i===0?"none":"1px solid #F7F5F2"}}>
                  <div style={{display:"flex",alignItems:"center",gap:12}}>
                    <div style={{width:40,height:40,borderRadius:12,background:bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{item.icon}</div>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{item.name}</div>
                      <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Last: {item.lastDone}</div>
                    </div>
                    <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:5,flexShrink:0}}>
                      <div style={{background:bg,color:c,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:700}}>{lbl}</div>
                      <Toggle
                        on={hygieneSettings[item.id]?.reminder}
                        onToggle={e=>{ setHygieneSettings(s=>({...s,[item.id]:{...s[item.id],reminder:!s[item.id].reminder}})); }}
                        showLabel
                      />
                    </div>
                  </div>
                  <div style={{marginTop:8,display:"flex",alignItems:"center",justifyContent:"space-between",gap:8}}>
                    <div style={{fontSize:11,color:"#AEAEB2",flex:1,lineHeight:1.4}}>ℹ️ {item.note}</div>
                    <FreqPill id={item.id}/>
                  </div>
                </div>
              );
            })}
            <div style={{padding:"8px 16px 12px",borderTop:"1px solid #F0EDE8"}}>
              <AddRow label="Add hygiene activity" onClick={()=>{ setAddForm({}); setAddSheet({type:"hygiene"}); }}/>
            </div>
          </div>
        </div>

        {/* Periodic grooming */}
        <div>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,marginBottom:8,paddingLeft:2}}>📅 Periodic grooming</div>
          <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #FF3B3033",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
            {PERIODIC_HYGIENE_ITEMS.map((item,i)=>{
              const lastDone = periodicDates[item.id];
              const hs = hygieneSettings[item.id] || {freq:1,unit:"month"};
              const nextDue  = addByUnit(lastDone, hs.freq, hs.unit);
              const status   = deriveCareStatus(lastDone, nextDue);
              const c  = STATUS_COLOR[status]||"#8E8E93";
              const bg = STATUS_BG[status]||"#F2F2F7";
              const lbl= status==="done"?"Up to date":status==="overdue"?"Overdue":status==="upcoming"?"Due Soon":"No record";
              const subtext = lastDone ? ("Last: " + lastDone + (nextDue ? "  ·  Next: " + nextDue : "")) : "No record";
              return (
                <div key={item.id} style={{padding:"13px 16px",borderTop:i===0?"none":"1px solid #F7F5F2"}}>
                  <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:8}}>
                    <div style={{width:40,height:40,borderRadius:12,background:bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{item.icon}</div>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{item.name}</div>
                      <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{subtext}</div>
                    </div>
                    <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:5,flexShrink:0}}>
                      <div style={{display:"flex",alignItems:"center",gap:6}}>
                        <div style={{background:bg,color:c,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:700}}>{lbl}</div>
                        <button onClick={()=>{setEditingGroomDate(item.id);setGroomDateInput(lastDone&&lastDone!=="Not recorded"?lastDone:"");}}
                          style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
                      </div>
                      <Toggle
                        on={hygieneSettings[item.id]?.reminder}
                        onToggle={()=>setHygieneSettings(s=>({...s,[item.id]:{...s[item.id],reminder:!s[item.id].reminder}}))}
                        showLabel
                      />
                    </div>
                  </div>
                  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8}}>
                    <div style={{fontSize:11,color:"#AEAEB2",flex:1,lineHeight:1.4}}>ℹ️ {item.note}</div>
                    <FreqPill id={item.id}/>
                  </div>
                </div>
              );
            })}
            <div style={{padding:"12px 16px",borderTop:"1px solid #F0EDE8",display:"flex",flexDirection:"column",gap:8}}>
              <AddRow label="Add grooming activity" onClick={()=>{ setAddForm({}); setAddSheet({type:"hygiene"}); }}/>
              <button onClick={()=>onCart("c7")}
                style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"11px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
                Book Now
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ── CONDITIONS TAB ─────────────────────────────────────────────────────────
  const ConditionsChronology = () => {
    const [open, setOpen] = useState("peek");
    const timeline = [
      {
        date:"Oct 10, 2025", label:"E. coli UTI", sublabel:"Partial Resolution", labelColor:"#FF9500",
        icon:"🦠", border:"#FF9500",
        testName:"Urine Test",
        source:"Oct 10, 2025  ·  Self-initiated  ·  Unique Bio Diagnostics",
        pills:[
          {t:"pH: Acidic",          c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Crystals: Absent",    c:"#34C759", bg:"#F0FFF4"},
          {t:"Occult blood: Absent",c:"#34C759", bg:"#F0FFF4"},
          {t:"Pus cells: 2–3/hpf", c:"#FF9500", bg:"#FFF6ED"},
          {t:"Epithelial: 3–4/hpf",c:"#8E8E93", bg:"#F2F2F7"},
          {t:"SG: 1.020",           c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Post-antibiotic culture: Not done", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Symptoms: House soiling ×3 in 10 days", c:"#FF9500", bg:"#FFF6ED"},
        ],
      },
      {
        date:"Sep 12, 2025", label:"UTI Treatment", sublabel:"Prescribed", labelColor:"#007AFF",
        icon:"💊", border:"#007AFF",
        testName:"Prescription",
        source:"Sep 12, 2025  ·  Dr. Makarand Chavan  ·  Dogs & Cats Vet Clinic, Dadar",
        pills:[
          {t:"Augmentin Duo 375 (Amox/Clav) — 1 tab BD × 5 days", c:"#007AFF", bg:"#F0F6FF"},
          {t:"Cystone — 1 tab BD × 15 days",                       c:"#007AFF", bg:"#F0F6FF"},
          {t:"Dompan (Domperidone) — 1 tab BD × 5 days",           c:"#007AFF", bg:"#F0F6FF"},
          {t:"Antibiotic: Matched Sep 2025 antibiogram",            c:"#34C759", bg:"#F0FFF4"},
        ],
      },
      {
        date:"Sep 10, 2025", label:"E. coli Detected", sublabel:"Episode 3", labelColor:"#FF3B30",
        icon:"🦠", border:"#FF3B30",
        testName:"Blood Test + Urine Test + Urine Culture + Ultrasound + X-Ray",
        source:"Sep 10, 2025  ·  Fredna Vet Diagnostics + Unique Bio Diagnostics  ·  Dr. Chavan",
        pills:[
          {t:"Urine culture: E. coli positive (<10³ CFU)", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Urine pH: Alkaline",                         c:"#FF9500", bg:"#FFF6ED"},
          {t:"Struvite crystals: 7–8/hpf",                c:"#FF9500", bg:"#FFF6ED"},
          {t:"Platelets: 160K — Thrombocytopenia",        c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Pus cells: 2–3/hpf  ·  RBCs: 2–3/hpf",    c:"#FF9500", bg:"#FFF6ED"},
          {t:"Susceptible: Amox/Clav · Nitrofurantoin · Fluoroquinolones · Cotrimoxazole", c:"#34C759", bg:"#F0FFF4"},
          {t:"USG: No calculus · Bladder wall 2.3mm · Prostate normal", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"X-Ray abdomen + chest: No abnormality",     c:"#34C759", bg:"#F0FFF4"},
          {t:"KFT: Creatinine 1.10 · BUN 19.1 · Glucose 90", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"LFT: GOT 30 · GPT 41 · ALP 26 · TBIL 0.2",    c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Electrolytes: Na 148 · K 4.9 · Cl 107",        c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
      {
        date:"Feb 26, 2025", label:"UTI", sublabel:"Near Resolved", labelColor:"#34C759",
        icon:"✅", border:"#34C759",
        testName:"Urine Test",
        source:"Feb 26, 2025  ·  Tata Trusts SAH  ·  Dr. Hamid Shah  ·  Dr. Abhilash Jadhao PhD",
        pills:[
          {t:"Appearance: Clear to slightly hazy", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Pus cells: Nil",    c:"#34C759", bg:"#F0FFF4"},
          {t:"RBCs: Nil",        c:"#34C759", bg:"#F0FFF4"},
          {t:"Bacteria: Nil",    c:"#34C759", bg:"#F0FFF4"},
          {t:"SG: 1.010",        c:"#8E8E93", bg:"#F2F2F7"},
          {t:"pH: 7.5",          c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Protein: Trace",   c:"#FF9500", bg:"#FFF6ED"},
          {t:"Pathologist impression: No remarkable changes", c:"#34C759", bg:"#F0FFF4"},
        ],
      },
      {
        date:"Feb 22, 2025", label:"Immune Shifts + Platelets Resolved", sublabel:"", labelColor:"#34C759",
        icon:"✅", border:"#34C759",
        testName:"Blood Test",
        source:"Feb 22, 2025  ·  Tata Trusts SAH  ·  Dr. Hamid Shah  ·  IDEXX Catalyst One",
        pills:[
          {t:"Platelets: 222K/cmm",           c:"#34C759", bg:"#F0FFF4"},
          {t:"WBC: 10.8 × 10³",               c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Neutrophils: 63.3%",             c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Lymphocytes: 25%",               c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Haemoglobin: 16.0 g/dl",         c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Bilirubin Total: 0.1 · Direct: 0.0 (resolved)", c:"#34C759", bg:"#F0FFF4"},
          {t:"Creatinine: 1.4 · BUN: 20 · Phosphorus: 3.9",  c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Cholesterol: 280 · Amylase: 1036 · Lipase: 1237", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Pathologist smear: Normal — normocytic normochromic", c:"#34C759", bg:"#F0FFF4"},
        ],
      },
      {
        date:"Feb 12, 2025", label:"Lymphocytosis", sublabel:"Detected", labelColor:"#8B44AD",
        icon:"🛡", border:"#8B44AD",
        testName:"Blood Test + Urine Test + Parasite Screen",
        source:"Feb 12, 2025  ·  Unique Bio Diagnostics  ·  Dr. Chavan",
        pills:[
          {t:"Neutrophils: 30% — Lymphocytosis (+)", c:"#FF9500", bg:"#FFF6ED"},
          {t:"Lymphocytes: 64%",                     c:"#FF9500", bg:"#FFF6ED"},
          {t:"Platelets: 252K/cmm (manual) — recovered", c:"#34C759", bg:"#F0FFF4"},
          {t:"Haemoglobin: 17.6 g/dl",               c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Bilirubin Direct: 0.2 mg/dl (above limit)", c:"#FF9500", bg:"#FFF6ED"},
          {t:"Urine: Pus cells 1–2/hpf · Proteins trace · Bile pigments trace", c:"#FF9500", bg:"#FFF6ED"},
          {t:"Haemoprotozoon screen: All negative (microscopy)", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"SGOT: 28 · SGPT: 45 · ALP: 82",        c:"#8E8E93", bg:"#F2F2F7"},
          {t:"BUN: 24.1 · Creatinine: 1.3 · Blood sugar: 87", c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
      {
        date:"Feb 1, 2025", label:"E. coli UTI", sublabel:"Improving", labelColor:"#FF9500",
        icon:"🦠", border:"#FF9500",
        testName:"Urine Test",
        source:"Feb 1, 2025  ·  Self-initiated  ·  Unique Bio Diagnostics",
        pills:[
          {t:"Pus cells: 3–4/hpf",    c:"#FF9500", bg:"#FFF6ED"},
          {t:"Epithelial: 5–6/hpf",   c:"#FF9500", bg:"#FFF6ED"},
          {t:"Proteins: Trace",        c:"#FF9500", bg:"#FFF6ED"},
          {t:"RBCs: Absent",           c:"#34C759", bg:"#F0FFF4"},
          {t:"Crystals: Absent",       c:"#34C759", bg:"#F0FFF4"},
          {t:"pH: Acidic",             c:"#8E8E93", bg:"#F2F2F7"},
          {t:"SG: 1.020",              c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
      {
        date:"Jan 29, 2025", label:"Low Platelets", sublabel:"+ Eosinophilia", labelColor:"#FF3B30",
        icon:"🩸", border:"#FF3B30",
        testName:"Blood Test",
        source:"Jan 29, 2025  ·  Unique Bio Diagnostics  ·  Dr. Chavan",
        pills:[
          {t:"Platelets: 158K (auto) · 188K (manual)", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Eosinophils: 11% — Eosinophilia (+)",    c:"#FF9500", bg:"#FFF6ED"},
          {t:"Phosphorus: 6.1 mg/dl",                  c:"#FF9500", bg:"#FFF6ED"},
          {t:"Haemoglobin: 14.1 g/dl",                 c:"#8E8E93", bg:"#F2F2F7"},
          {t:"WBC: 10.6 × 10³",                        c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Neutrophils: 61% · Lymphocytes: 28%",    c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Creatinine: 1.3 · BUN: 20.7 · Calcium: 9.7", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Electrolytes: Na 146 · K 4.3 · Cl 110",  c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
      {
        date:"Jan 28, 2025", label:"Low Platelets", sublabel:"In-clinic", labelColor:"#FF3B30",
        icon:"🩸", border:"#FF3B30",
        testName:"Blood Test",
        source:"Jan 28, 2025  ·  Dogs & Cats Vet Clinic  ·  Dr. Chavan  ·  IDEXX in-house",
        pills:[
          {t:"Platelets: 156K/cmm",                      c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Creatinine: 1.7 mg/dl · Lipemia 3+ noted", c:"#FF9500", bg:"#FFF6ED"},
          {t:"WBC: 10.1 × 10³",                          c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Haemoglobin: 14.8 g/dl",                   c:"#8E8E93", bg:"#F2F2F7"},
          {t:"ALT · AST · ALP: Normal range",             c:"#34C759", bg:"#F0FFF4"},
          {t:"BUN · Calcium · Phosphorus: Normal range",  c:"#34C759", bg:"#F0FFF4"},
        ],
      },
      {
        date:"Nov 28, 2024", label:"E. coli Detected", sublabel:"Episode 2", labelColor:"#FF3B30",
        icon:"🦠", border:"#FF3B30",
        testName:"Urine Test + Urine Culture",
        source:"Nov 28, 2024  ·  Self-initiated  ·  Unique Bio Diagnostics",
        pills:[
          {t:"Urine culture: E. coli · 10³ CFU",           c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Resistant: Ampicillin · Cefazolin · Ciprofloxacin · Ofloxacin · Norfloxacin · Levofloxacin", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Susceptible: Amox/Clav · Ceftriaxone · Gentamicin · Amikacin · Nitrofurantoin", c:"#34C759", bg:"#F0FFF4"},
          {t:"Bacteria (+) on microscopy",                 c:"#FF9500", bg:"#FFF6ED"},
          {t:"Appearance: Hazy · pH: Acidic · SG: 1.020", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Epithelial: 7–8/hpf · Pus cells: 1–2/hpf", c:"#FF9500", bg:"#FFF6ED"},
          {t:"Bile pigments trace · Bile salts trace",     c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
      {
        date:"Dec 12, 2023", label:"E. coli UTI", sublabel:"Episode 1", labelColor:"#FF3B30",
        icon:"🦠", border:"#FF3B30",
        testName:"Urine Test + Blood Test (ALT)",
        source:"Dec 12, 2023  ·  Self-initiated  ·  Unique Bio Diagnostics  ·  Dr. Vengsarkar Shah",
        pills:[
          {t:"Pus cells: 7–8/hpf",              c:"#FF3B30", bg:"#FFF0F0"},
          {t:"RBCs: 2–3/hpf",                   c:"#FF9500", bg:"#FFF6ED"},
          {t:"Epithelial: 7–8/hpf",             c:"#FF9500", bg:"#FFF6ED"},
          {t:"Amorphous ureates: Present (+)",   c:"#FF9500", bg:"#FFF6ED"},
          {t:"Appearance: Hazy · pH: Acidic · SG: 1.020", c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Urine culture: Not done",          c:"#8E8E93", bg:"#F2F2F7"},
          {t:"ALT: 89 U/L",                      c:"#FF9500", bg:"#FFF6ED"},
          {t:"Platelets (manual): 178K/cmm",     c:"#FF9500", bg:"#FFF6ED"},
        ],
      },
      {
        date:"Nov 6, 2023", label:"Tick Fever", sublabel:"First Detected", labelColor:"#FF3B30",
        icon:"🔬", border:"#FF3B30",
        testName:"PCR Blood Parasite Panel",
        source:"Nov 6, 2023  ·  Dr. Atul Patil  ·  ChromoXpert, Navi Mumbai  ·  Ref. Pawsitive Wellness Centre",
        pills:[
          {t:"Anaplasma platys: DETECTED · CT value 22.1", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Hepatozoon canis: DETECTED · CT value 34.0", c:"#FF3B30", bg:"#FFF0F0"},
          {t:"Platelets (manual): 178K/cmm",               c:"#FF9500", bg:"#FFF6ED"},
          {t:"Haemoglobin: 15.2 g/dl",                     c:"#8E8E93", bg:"#F2F2F7"},
          {t:"WBC: 9.0 × 10³",                             c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Neutrophils: 67% · Lymphocytes: 24%",        c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Treatment: None recorded",                   c:"#8E8E93", bg:"#F2F2F7"},
          {t:"Repeat PCR: Not done",                       c:"#8E8E93", bg:"#F2F2F7"},
        ],
      },
    ];

    const isPeek = open === "peek";
    const isFull = open === "full";
    const visibleEvents = isPeek ? timeline.slice(0, 1) : timeline;

    return (
      <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #8E8E9333",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>

        {/* ── Header — icon + title + collapse button (shown only when full) ── */}
        <div style={{padding:"14px 16px",display:"flex",alignItems:"center",gap:12}}>
          <div style={{width:44,height:44,borderRadius:12,background:"#F7F4F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📅</div>
          <div style={{flex:1,minWidth:0}}>
            <div style={{fontWeight:700,fontSize:15}}>Health Management Timeline</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Latest to oldest · {timeline.length} events · 2 years of records</div>
          </div>
          {isFull && (
            <button onClick={()=>setOpen("peek")}
              style={{flexShrink:0,background:"#F2EDE8",border:"none",borderRadius:20,padding:"6px 13px",fontSize:12,fontWeight:700,color:"#D44800",cursor:"pointer",display:"flex",alignItems:"center",gap:4,whiteSpace:"nowrap"}}>
              ↑ Collapse
            </button>
          )}
        </div>

        {/* ── Event cards ── */}
        <div style={{borderTop:"1px solid #F0EDE8",padding:"12px 16px 0",display:"flex",flexDirection:"column",gap:0}}>
          {visibleEvents.map((ev,i)=>(
            <div key={i} style={{display:"flex",gap:12,paddingBottom:i<visibleEvents.length-1?16:12,position:"relative"}}>
              {isFull && i < visibleEvents.length-1 && (
                <div style={{position:"absolute",left:44,top:78,bottom:0,width:1.5,background:"#E8E4DF",zIndex:0}}/>
              )}
              <div style={{width:80,flexShrink:0,zIndex:1}}>
                <div style={{background:ev.border+"12",border:"1.5px solid "+ev.border+"44",borderRadius:12,padding:"8px 5px",textAlign:"center",minHeight:68,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:2}}>
                  <div style={{fontSize:17}}>{ev.icon}</div>
                  <div style={{fontSize:9.5,fontWeight:700,color:ev.labelColor,lineHeight:1.2,textAlign:"center"}}>{ev.label}</div>
                  {ev.sublabel && <div style={{fontSize:8.5,color:ev.labelColor,opacity:0.85,lineHeight:1.1}}>{ev.sublabel}</div>}
                  <div style={{fontSize:8.5,color:"#8E8E93",marginTop:1,lineHeight:1.2}}>{ev.date}</div>
                </div>
              </div>
              <div style={{flex:1,background:"white",borderRadius:12,border:"1px solid #F0EDE8",padding:"11px 13px",minWidth:0}}>
                <div style={{fontWeight:700,fontSize:13,color:"#1A1A1A",marginBottom:3,lineHeight:1.3}}>{ev.testName}</div>
                <div style={{fontSize:10,color:"#AEAEB2",marginBottom:8,lineHeight:1.4}}>{ev.source}</div>
                <div style={{display:"flex",flexWrap:"wrap",gap:4}}>
                  {ev.pills.map((p,j)=>(
                    <div key={j} style={{background:p.bg,color:p.c,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:600,lineHeight:1.4}}>{p.t}</div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Expand button — solid orange, full width, only in peek ── */}
        {isPeek && (
          <button onClick={()=>setOpen("full")}
            style={{display:"block",width:"calc(100% - 32px)",margin:"0 16px 14px",background:"#D44800",border:"none",borderRadius:10,padding:"12px 16px",cursor:"pointer",textAlign:"center"}}>
            <span style={{fontWeight:700,fontSize:13,color:"white",letterSpacing:0.3}}>
              See all {timeline.length} events ↓
            </span>
          </button>
        )}

      </div>
    );
  };

  const PDF_B64 = "";

  const DownloadHealthHistoryBtn = () => {
    const handleDownload = () => {
      const byteChars = atob(PDF_B64);
      const byteArr = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
      const blob = new Blob([byteArr], {type:"application/pdf"});
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    };
    return (
      <button onClick={handleDownload}
        style={{width:"100%",background:"#1A1A1A",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:8}}>
        📥 Download Health History
      </button>
    );
  };

  const renderConditionsTab = () => {
    const utiCond  = pet.healthRecords.conditions[0];
    const anapCond = pet.healthRecords.conditions[1];

    return (
    <div style={{display:"flex",flexDirection:"column",gap:12,animation:"slideUp 0.4s ease"}}>

      {/* ── 1. HEALTH SCORE + BRIEF SUMMARY ───────────────────────────── */}
      {(()=>{
        // Colour theme driven by score: >= 50 → pale green, < 50 → warm cream
        const above50 = hs.total >= 50;
        const cardBg      = above50 ? "#F4FBF6" : "#FFF8F5";
        const cardBorder  = above50 ? "#C2E8CC" : "#E8956A";
        const ringColor   = above50 ? "#34C759" : "#D44800";
        const ringTrack   = above50 ? "rgba(52,199,89,0.15)"  : "rgba(212,72,0,0.12)";
        const scoreColor  = above50 ? "#1A6B2A" : "#9B3A00";
        const scoreSub    = above50 ? "#4A9A5A"  : "#C07050";
        const labelColor  = above50 ? "#1A6B2A"  : "#9B3A00";
        const badgeBg     = above50 ? "#D8F0DE"  : "#FFDDD0";
        const badgeBorder = above50 ? "#B0DDB8"  : "#E8956A55";
        const badgeColor  = above50 ? "#1A6B2A"  : "#8B3000";
        const subtitleC   = above50 ? "#4A8A58"  : "#B06040";
        const insightC    = above50 ? "#1C3A22"  : "#4A2810";
        const strongC     = above50 ? "#1A6B2A"  : "#D44800";
        // Stroke dashoffset: circumference * (1 - score/100)
        const circ = 2 * Math.PI * 30;
        const offset = circ * (1 - hs.total / 100);

        return (
          <div style={{background:cardBg,borderRadius:16,padding:18,border:"1.5px solid "+cardBorder,boxShadow:"0 2px 12px rgba(0,0,0,0.06)"}}>
            {/* Score row */}
            <div style={{display:"flex",alignItems:"center",gap:16,marginBottom:14}}>
              <div style={{position:"relative",flexShrink:0}}>
                <svg width={72} height={72} style={{transform:"rotate(-90deg)"}}>
                  <circle cx={36} cy={36} r={30} fill="none" stroke={ringTrack} strokeWidth={5}/>
                  <circle cx={36} cy={36} r={30} fill="none" stroke={ringColor} strokeWidth={5}
                    strokeDasharray={circ} strokeDashoffset={offset}
                    strokeLinecap="round"/>
                </svg>
                <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
                  <div style={{fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900,color:scoreColor,lineHeight:1}}>{hs.total}</div>
                  <div style={{fontSize:9,color:scoreSub,lineHeight:1.4}}>/100</div>
                </div>
              </div>
              <div style={{flex:1}}>
                <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
                  <div style={{fontFamily:"'Fraunces',serif",fontSize:18,fontWeight:900,color:labelColor}}>{hs.label}</div>
                  <div style={{background:badgeBg,border:"1px solid "+badgeBorder,color:badgeColor,borderRadius:20,padding:"2px 9px",fontSize:10,fontWeight:700}}>2 OPEN CONDITIONS</div>
                </div>
                <div style={{fontSize:11,color:subtitleC,lineHeight:1.4}}>Based on organ health, test results & active conditions</div>
              </div>
            </div>

            {/* Brief insight */}
            <div style={{fontSize:12.5,color:insightC,lineHeight:1.65,marginBottom:14}}>
              Zayn is <span style={{color:strongC,fontWeight:600}}>structurally healthy</span> — liver, kidneys, heart and lungs consistently normal across 2 years of records. Score is pulled down by two unresolved conditions: a <span style={{color:"#B05000",fontWeight:600}}>recurring E. coli UTI not yet confirmed cleared</span> and <span style={{color:"#8B0000",fontWeight:600}}>Anaplasma platys (tick bacteria) confirmed in 2023, never treated</span> — likely cause of recurring low platelets.
            </div>

            {/* Status pills */}
            <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
              {[
                {icon:"✅", label:"Core organs — normal",      c:"#1A6B2A", bg:"#D8F0DE"},
                {icon:"⚠️", label:"UTI — not cleared",          c:"#8B5E00", bg:"#FFF3DC"},
                {icon:"🚨", label:"Anaplasma — never treated", c:"#8B0000", bg:"#FFE8E8"},
                {icon:"🩸", label:"Platelets — cycling low",   c:"#7A0035", bg:"#FFE8F0"},
              ].map((p,i)=>(
                <div key={i} style={{background:p.bg,borderRadius:20,padding:"4px 10px",fontSize:10,fontWeight:600,color:p.c,display:"flex",alignItems:"center",gap:4}}>
                  <span>{p.icon}</span><span>{p.label}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* ── 2. ONGOING CONDITIONS SUBHEADING ──────────────────────────── */}
      <div style={{display:"flex",alignItems:"center",gap:10,paddingLeft:2,paddingTop:4}}>
        <div style={{fontSize:13,fontWeight:800,color:"#1A1A1A",letterSpacing:-0.2}}>Ongoing Conditions</div>
        <div style={{flex:1,height:1,background:"#E8E4DF"}}/>
        <div style={{background:"#FFF0F0",color:"#FF3B30",borderRadius:20,padding:"2px 9px",fontSize:10,fontWeight:700}}>2 Active</div>
      </div>

      {/* ── 3. SINGLE CONDITIONS CARD (UTI + ANAPLASMA) ────────────────── */}
      <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #E8E4DF",boxShadow:"0 2px 10px rgba(0,0,0,0.06)"}}>

        {/* — UTI SECTION — */}
        <div style={{padding:"16px 16px 0"}}>
          <div style={{display:"flex",alignItems:"flex-start",gap:10,marginBottom:10}}>
            <div style={{width:42,height:42,borderRadius:11,background:"#FFF6ED",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{utiCond.icon}</div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontWeight:700,fontSize:14,color:"#1A1A1A",lineHeight:1.3}}>{utiCond.name}</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:2}}>
                <span style={{color:"#AEAEB2"}}>First: </span><span style={{color:"#555",fontWeight:600}}>{utiCond.diagnosedOn}</span>
                <span style={{color:"#AEAEB2"}}> · Last: </span><span style={{color:"#D44800",fontWeight:600}}>Sep 2025</span>
                <span style={{color:"#AEAEB2"}}> · 3 episodes</span>
              </div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>{utiCond.managedBy}</div>
            </div>
            <Badge label="FOLLOW-UP DUE" color="#FF9500" bg="#FFF6ED"/>
          </div>

          <div style={{background:"#FFF8EE",border:"1px solid #FFCC8044",borderRadius:9,padding:"7px 10px",marginBottom:12,display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontSize:14,flexShrink:0}}>⚠️</span>
            <div style={{fontSize:11.5,color:"#7A4800",lineHeight:1.5}}><strong>Status unknown</strong> — pus cells persist (2–3/hpf), no post-antibiotic culture done, symptoms ongoing.</div>
          </div>

          {/* Prescription */}
          <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:7}}><div style={{width:3,height:14,background:"#007AFF",borderRadius:2}}/><div style={{fontSize:10,fontWeight:700,color:"#007AFF",textTransform:"uppercase",letterSpacing:0.5}}>Vet Prescribed — Sep 2025</div></div>
          <div style={{display:"flex",flexDirection:"column",gap:5,marginBottom:12}}>
            {utiCond.medications.map((med,j)=>(
              <div key={j} style={{display:"flex",alignItems:"center",gap:9,padding:"8px 10px",background:"#F7F4F0",borderRadius:9}}>
                <span style={{fontSize:15}}>💊</span>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontWeight:600,fontSize:12,color:"#1A1A1A"}}>{med.name}</div>
                  <div style={{fontSize:10.5,color:"#8E8E93",marginTop:1}}>{med.dose}</div>
                </div>
                <Badge label="Completed" color="#34C759" bg="#F0FFF4"/>
              </div>
            ))}
            <AddRow label="Add medication" onClick={()=>{ setAddForm({}); setAddSheet({type:"medication"}); }}/>
          </div>

          {/* Follow-up tests */}
          <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:7}}><div style={{width:3,height:14,background:"#007AFF",borderRadius:2}}/><div style={{fontSize:10,fontWeight:700,color:"#007AFF",textTransform:"uppercase",letterSpacing:0.5}}>Vet Prescribed — Dr. Chavan</div></div>
          <div style={{display:"flex",flexDirection:"column",gap:5,marginBottom:14}}>
            {utiCond.monitoringChecks.filter(c=>c.source==="vet").map((chk,j)=>{
              const cs = ST_CFG[chk.status] || ST_CFG.missing;
              return (
                <div key={j} style={{display:"flex",alignItems:"flex-start",gap:9,padding:"8px 10px",background:"#F0F6FF",borderRadius:9}}>
                  <span style={{fontSize:15,flexShrink:0,marginTop:1}}>🩺</span>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontWeight:600,fontSize:12,color:"#1A1A1A",marginBottom:2}}>{chk.name}</div>
                    <div style={{fontSize:10.5,color:"#8E8E93",marginBottom:3}}>{chk.sourceNote}</div>
                    <div style={{display:"flex",alignItems:"center",gap:6}}>
                      <span style={{fontSize:10.5,color:"#8E8E93"}}>Due: {chk.nextDue}</span>
                      <Badge label={cs.label} color={cs.color} bg={cs.bg}/>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <button onClick={()=>onCart("c2")}
            style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer",marginBottom:14}}>
            📅 Book Follow-up Tests
          </button>
        </div>

        {/* Divider between conditions */}
        <div style={{height:8,background:"#F7F4F0",borderTop:"1px solid #EEEBE6",borderBottom:"1px solid #EEEBE6",display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div style={{width:32,height:2,borderRadius:2,background:"#D8D4CE"}}/>
        </div>

        {/* — ANAPLASMA SECTION — */}
        <div style={{padding:"16px 16px"}}>
          <div style={{display:"flex",alignItems:"flex-start",gap:10,marginBottom:10}}>
            <div style={{width:42,height:42,borderRadius:11,background:"#FFF0F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>{anapCond.icon}</div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontWeight:700,fontSize:14,color:"#1A1A1A",lineHeight:1.3}}>{anapCond.name}</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:2}}>Detected {anapCond.diagnosedOn} · {anapCond.managedBy}</div>
            </div>
            <Badge label="NEVER TREATED" color="#FF3B30" bg="#FFF0F0"/>
          </div>

          <div style={{background:"#FFF5F5",border:"1px solid #FFCACA44",borderRadius:9,padding:"8px 11px",marginBottom:12,fontSize:11.5,color:"#7A0000",lineHeight:1.55}}>
            🚨 <strong>Never treated. No follow-up in 2+ years.</strong> PCR confirmed (CT 22.1) Nov 2023. Most likely cause of Zayn's recurring low platelets. Treatment exists and is straightforward.
          </div>

          {/* Platelet trend */}
          <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8}}><div style={{width:3,height:14,background:"#007AFF",borderRadius:2}}/><div style={{fontSize:10,fontWeight:700,color:"#007AFF",textTransform:"uppercase",letterSpacing:0.5}}>Platelet History — Blood Tests</div></div>
          <div style={{display:"flex",gap:5,marginBottom:12}}>
            {[["Nov 2023","178K ↓","#FF3B30"],["Jan 2025","156K ↓","#FF3B30"],["Feb 2025","252K ↑","#34C759"],["Sep 2025","160K ↓","#FF3B30"]].map(([d,v,c],k)=>(
              <div key={k} style={{background:c+"12",border:"1px solid "+c+"30",borderRadius:9,padding:"6px 8px",textAlign:"center",flex:1}}>
                <div style={{fontSize:9.5,color:"#AEAEB2",marginBottom:2}}>{d}</div>
                <div style={{fontSize:12.5,fontWeight:700,color:c}}>{v}</div>
              </div>
            ))}
          </div>

          <button onClick={()=>onCart("c1")}
            style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
            📅 Book PCR Retest
          </button>
        </div>
      </div>

      {/* ── 4. LAST VET VISIT ──────────────────────────────────────────── */}
      <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #34C75933",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
          <div style={{width:44,height:44,borderRadius:12,background:"#F0FFF4",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>🩺</div>
          <div style={{flex:1}}>
            <div style={{fontWeight:700,fontSize:15}}>Last Vet Visit</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Most recent recorded visit</div>
          </div>
          <div style={{background:"#F0FFF4",color:"#34C759",borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>On Record</div>
        </div>
        <div style={{display:"flex",flexDirection:"column",gap:8}}>
          <div style={{display:"flex",gap:12,padding:"10px 12px",background:"#FAFAF9",borderRadius:10,border:"1px solid #F0EDE8"}}>
            <div style={{width:38,height:38,borderRadius:10,background:"#F0FFF4",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>👨‍⚕️</div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>Dr. Makarand Chavan</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>Dogs & Cats Veterinary Clinic · Dadar</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>UTI (E. coli) — treatment prescribed Sep 2025</div>
            </div>
          </div>
          <div style={{display:"flex",gap:8}}>
            <div style={{flex:1,background:"#F7F4F0",borderRadius:10,padding:"9px 12px"}}>
              <div style={{fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.4,marginBottom:3}}>Last Visit</div>
              <div style={{fontSize:13,fontWeight:600,color:"#1A1A1A"}}>12 Sep 2025</div>
              <div style={{fontSize:11,color:"#8E8E93",fontWeight:500,marginTop:2}}>~6 months ago</div>
            </div>
            <div style={{flex:1,background:"#FFF6ED",borderRadius:10,border:"1px solid #FF950033",padding:"9px 12px"}}>
              <div style={{fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.4,marginBottom:3}}>Follow-up Due</div>
              <div style={{fontSize:13,fontWeight:600,color:"#1A1A1A"}}>Oct 2025</div>
              <div style={{fontSize:11,color:"#FF3B30",fontWeight:600,marginTop:2}}>Overdue — not done</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 5. HEALTH TIMELINE ─────────────────────────────────────────── */}
      <ConditionsChronology/>

      {/* ── 6. DOWNLOAD HEALTH HISTORY ─────────────────────────────────── */}
      <DownloadHealthHistoryBtn/>

      {/* ── 7. ASK THE VET ─────────────────────────────────────────────── */}
      <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #007AFF33",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        {/* Header */}
        <div style={{background:"#F0F6FF",padding:"14px 16px",borderBottom:"1px solid #D8E8FF"}}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <div style={{width:38,height:38,borderRadius:10,background:"white",border:"1px solid #C0D8FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>🩺</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:15,color:"#0C447C"}}>Ask the Vet</div>
              <div style={{fontSize:11,color:"#4A80C0",marginTop:1}}>Key questions to raise at Zayn's next consult</div>
            </div>
          </div>
        </div>

        {/* Questions */}
        <div style={{padding:"12px 16px",display:"flex",flexDirection:"column",gap:10}}>

          {[
            {
              priority:"urgent",
              icon:"🔬",
              q:"Can we redo the Anaplasma platys Q-PCR?",
              context:"PCR confirmed it at CT 22.1 in Nov 2023 — never treated or rechecked. The Feb 2025 parasite screen used microscopy, which can't detect A. platys at low loads. Two years of cyclic low platelets (178K → 156K → 252K → 160K) match exactly what A. platys does. A repeat PCR would confirm if it's still active and guide whether Doxycycline is needed.",
            },
            {
              priority:"urgent",
              icon:"🧫",
              q:"Should we run a post-antibiotic urine culture now?",
              context:"The Sep 2025 Augmentin course wasn't followed by a culture. As of Oct 2025, Zayn was still showing pus cells (2–3/hpf) and house soiling — current status unknown. A culture now confirms whether E. coli was cleared or just suppressed — and if resistant, flags the need to change antibiotic.",
            },
            {
              priority:"high",
              icon:"💊",
              q:"Was 5 days of Augmentin long enough for Zayn's UTI?",
              context:"Both Sep 2025 and the previous episode used 5-day courses. Standard canine UTI with a confirmed organism typically needs 7–14 days. If E. coli is still present, ask about a longer course or whether Nitrofurantoin — which stays concentrated in urine — might be a better fit.",
            },
            {
              priority:"high",
              icon:"🥣",
              q:"Should we consider a urinary health diet?",
              context:"Struvite crystals appeared in Sep 2025, resolved after pH normalised. A diet lower in magnesium and phosphorus, with higher moisture content, may reduce crystal risk in future episodes. Worth discussing wet food or a urinary-specific dry food.",
            },
          ].map((item, i)=>{
            const isUrgent = item.priority==="urgent";
            const pColor = isUrgent ? "#FF3B30" : "#FF9500";
            const pBg    = isUrgent ? "#FFF0F0" : "#FFF6ED";
            const pLabel = isUrgent ? "Urgent" : "Important";
            return (
              <div key={i} style={{borderRadius:10,border:"1px solid #E8EFFF",overflow:"hidden",background:"#FAFCFF"}}>
                <div style={{padding:"10px 12px 8px"}}>
                  <div style={{display:"flex",alignItems:"flex-start",gap:9}}>
                    <span style={{fontSize:17,flexShrink:0,marginTop:1}}>{item.icon}</span>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4,flexWrap:"wrap"}}>
                        <div style={{fontWeight:700,fontSize:13,color:"#0C447C",lineHeight:1.3}}>{item.q}</div>
                        <div style={{background:pBg,color:pColor,borderRadius:20,padding:"1px 7px",fontSize:9,fontWeight:700,flexShrink:0}}>{pLabel}</div>
                      </div>
                      <div style={{fontSize:11,color:"#555",lineHeight:1.55}}>{item.context}</div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

        </div>
      </div>

      <button style={{background:"white",border:"1.5px dashed #C7C7CC",borderRadius:14,padding:16,display:"flex",alignItems:"center",gap:12,cursor:"pointer",width:"100%"}}>
        <div style={{width:40,height:40,borderRadius:12,background:"#F2F2F7",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20}}>➕</div>
        <div><div style={{fontWeight:600,fontSize:14,color:"#333"}}>Add Another Condition</div><div style={{fontSize:12,color:"#8E8E93"}}>Allergies, skin conditions, chronic issues & more</div></div>
      </button>

      {/* ── DASHBOARD DISCLAIMER ───────────────────────────────────────── */}
      <div style={{borderRadius:10,padding:"10px 13px",background:"#F7F4F0",border:"1px solid #E8E4DF",display:"flex",alignItems:"flex-start",gap:8}}>
        <span style={{fontSize:14,flexShrink:0,marginTop:1}}>📋</span>
        <div style={{fontSize:10.5,color:"#8E8E93",lineHeight:1.6}}>
          All information on this dashboard is compiled from Zayn's uploaded records and PetCircle's analysis. It is intended to help you track health, ask better questions, and stay informed — not to replace clinical advice. All decisions about diagnosis and treatment should be made in consultation with a qualified vet.
        </div>
      </div>

    </div>
    );
  };

  return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif"}}>
      {/* Header */}
      <div style={{background:"linear-gradient(135deg,#D44800 0%,#FF9A6C 100%)",padding:"20px 20px 24px",position:"relative",overflow:"hidden"}}>
        <div style={{position:"absolute",top:-40,right:-40,width:200,height:200,borderRadius:"50%",background:"rgba(255,255,255,0.04)"}}/>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:14,position:"relative"}}>
          <Avatar name="Zayn" size={48} imgSrc={petImg} onImgChange={onPetImgChange}/>
          <div style={{flex:1}}>
            <div style={{color:"white",fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900,lineHeight:1}}>Zayn</div>
            <div style={{color:"rgba(255,255,255,0.7)",fontSize:12}}>Labrador · 4 yrs · Mumbai</div>
            <div style={{color:"rgba(255,255,255,0.55)",fontSize:11,marginTop:1}}>Parent: Ashita Arora</div>
          </div>
        </div>
        <div onClick={onCart} style={{background:"transparent",border:"1px solid rgba(255,255,255,0.8)",borderRadius:12,padding:"10px 14px",display:"flex",alignItems:"center",gap:10,position:"relative",cursor:"pointer"}}>
          <div style={{width:36,height:36,borderRadius:10,background:"white",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0,position:"relative"}}>
            ⚡
            <div style={{position:"absolute",top:-5,right:-5,width:16,height:16,borderRadius:"50%",background:"#FF3B30",display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,fontWeight:700,color:"white"}}>{cartItemsData.filter(i=>i.inCart).length}</div>
          </div>
          <div style={{flex:1}}>
            <div style={{color:"white",fontWeight:700,fontSize:13}}>{cartItemsData.filter(i=>i.inCart).length} Actions Due</div>
            <div style={{color:"rgba(255,255,255,0.65)",fontSize:11}}>Lab tests · Supplements · Vet follow-up</div>
          </div>
          <div style={{background:"white",color:"#D44800",borderRadius:10,padding:"6px 14px",fontSize:12,fontWeight:700,flexShrink:0}}>Order →</div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{display:"flex",background:"white",borderBottom:"1px solid #E8E4DF",overflowX:"auto",scrollbarWidth:"none"}}>
        {DASHBOARD_TABS.map(([id,label])=>(
          <button key={id} onClick={()=>setTab(id)} style={{flexShrink:0,padding:"12px 12px",border:"none",background:"none",color:tab===id?"#D44800":"#8E8E93",fontWeight:tab===id?700:500,fontSize:12,cursor:"pointer",borderBottom:tab===id?"2px solid #D44800":"2px solid transparent",transition:"all 0.2s",whiteSpace:"nowrap"}}>{label}</button>
        ))}
      </div>

      <div style={{padding:16,maxWidth:500,margin:"0 auto",paddingBottom:90}}>
        {tab==="overview"    && renderOverviewTab()}
        {tab==="medical"     && renderMedicalTab()}
        {tab==="nutrition"   && renderNutritionTab()}
        {tab==="grooming"    && renderGroomingTab()}
        {tab==="conditions"  && renderConditionsTab()}
      </div>

      {/* FAB */}
      <div style={{position:"fixed",bottom:24,right:24}}>
        <button onClick={onNext} style={{background:"linear-gradient(135deg,#D44800,#FF9F1C)",color:"white",border:"none",borderRadius:"50%",width:56,height:56,fontSize:22,cursor:"pointer",boxShadow:"0 4px 20px rgba(255,107,53,0.45)",display:"flex",alignItems:"center",justifyContent:"center"}}>⚡</button>
      </div>

      {/* Modals */}
      <FreqModal modal={freqModal} setModal={setFreqModal} onSave={handleFreqSave}/>

      {editingGroomDate && (
        <DateEditSheet
          title="Edit Date"
          subtitle={editingGroomDate==="bath-nail"?"Bath, Brush & Nail Trim":"Anal Gland Cleaning"}
          value={groomDateInput}
          onChange={setGroomDateInput}
          previewNext={addByUnit(groomDateInput, hygieneSettings[editingGroomDate]?.freq||1, hygieneSettings[editingGroomDate]?.unit||"month")}
          onSave={v=>setPeriodicDates(s=>({...s,[editingGroomDate]:v}))}
          onClose={()=>setEditingGroomDate(null)}
        />
      )}

      {editingCareDate && (()=>{
        const cfg = { deworming:{label:"Deworming",freqMths:3,setter:setDwLastDone}, fleaTick:{label:"Flea & Tick Protection",freqMths:1,setter:setFtLastDone} };
        const c = cfg[editingCareDate];
        return (
          <DateEditSheet
            title="Edit Date" subtitle={c.label}
            value={careDateInput} onChange={setCareDateInput}
            previewNext={addMonths(careDateInput, c.freqMths)}
            onSave={v=>c.setter(v)}
            onClose={()=>setEditingCareDate(null)}
          />
        );
      })()}

      {editingCheckupId && (()=>{
        const labels = { "chk-vet":"Vet Visit", "chk-blood":"Blood Work", "chk-urine":"Urinalysis", "chk-culture":"Urine Culture", "chk-cbc":"CBC / Platelet Count" };
        return (
          <DateEditSheet
            title="Log Checkup Date" subtitle={labels[editingCheckupId]||"Checkup"} inputLabel="Date Done"
            value={checkupDateInput} onChange={setCheckupDateInput}
            previewNext={addMonths(checkupDateInput, 12)}
            onSave={v=>setCheckupDates(s=>({...s,[editingCheckupId]:v}))}
            onClose={()=>setEditingCheckupId(null)}
          />
        );
      })()}

      {editingVaxDate && (()=>{
        const vac = pet.healthRecords.vaccines.find(v=>v.id===editingVaxDate);
        const vs  = vaccineState[editingVaxDate]||{};
        return (
          <DateEditSheet
            title="Edit Vaccination Date" subtitle={vac?.name} inputLabel="Last Given"
            value={vaxDateInput} onChange={setVaxDateInput}
            previewNext={addMonths(vaxDateInput, vs.freqMonths||12)}
            onSave={v=>setVaccineState(s=>({...s,[editingVaxDate]:{...s[editingVaxDate],lastGiven:v}}))}
            onClose={()=>setEditingVaxDate(null)}
          />
        );
      })()}

      {vaxFreqModal && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setVaxFreqModal(null)}>
          <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
            <div style={{fontWeight:700,fontSize:16,marginBottom:4}}>Set Vaccine Frequency</div>
            <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>How often should this vaccine be given?</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:8,marginBottom:20}}>
              {VAX_FREQ_OPTS.map(m=>(
                <button key={m} onClick={()=>setVaxFreqModal(f=>({...f,freqMonths:m}))}
                  style={{padding:"10px 18px",borderRadius:20,border:"none",background:vaxFreqModal.freqMonths===m?"#D44800":"#F2EDE8",color:vaxFreqModal.freqMonths===m?"white":"#555",fontWeight:600,fontSize:13,cursor:"pointer"}}>
                  {VAX_FREQ_LABELS[m]}
                </button>
              ))}
            </div>
            <button onClick={()=>{setVaccineState(s=>({...s,[vaxFreqModal.id]:{...s[vaxFreqModal.id],freqMonths:vaxFreqModal.freqMonths}}));setVaxFreqModal(null);}}
              style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:12,padding:"12px",fontSize:14,fontWeight:700,cursor:"pointer"}}>
              Save Frequency
            </button>
          </div>
        </div>
      )}

      {/* Add Entry Sheet */}
      {addSheet && (() => {
        const cfg = {
          vaccine:    { title:"Add vaccine", fields:[{key:"name",label:"Vaccine name",placeholder:"e.g. Bordetella"},{key:"date",label:"Date given",placeholder:"DD/MM/YYYY"},{key:"nextDue",label:"Next due",placeholder:"DD/MM/YYYY"}] },
          homemade:   { title:"Add homemade food", fields:[{key:"ingredient",label:"Ingredient",placeholder:"e.g. Boiled eggs"},{key:"quantity",label:"Quantity",placeholder:"e.g. 50g"},{key:"frequency",label:"Frequency",placeholder:"e.g. Daily"}] },
          addFood:    { title:"Add food", hint:"We'll classify it as packaged or homemade.", fields:[{key:"label",label:"What do you feed?",placeholder:"e.g. Pedigree Adult or boiled eggs"},{key:"detail",label:"Quantity / frequency",placeholder:"e.g. 200g · Daily"}] },
          supplement: { title:"Add supplement", fields:[{key:"name",label:"Supplement name",placeholder:"e.g. Vitamin C"},{key:"dose",label:"Dose",placeholder:"e.g. 1 tablet daily"}] },
          hygiene:    { title:"Add hygiene activity", fields:[{key:"name",label:"Activity name",placeholder:"e.g. Paw cleaning"},{key:"lastDone",label:"Last done",placeholder:"DD/MM/YYYY"},{key:"freq",label:"Frequency",placeholder:"e.g. Weekly"}] },
          medication: { title:"Add medication", fields:[{key:"name",label:"Medicine name",placeholder:"e.g. Apoquel"},{key:"dose",label:"Dose",placeholder:"e.g. Once daily"},{key:"refillDue",label:"Refill due",placeholder:"DD/MM/YYYY"}] },
          diagnostic: { title:"Add diagnostic", fields:[{key:"name",label:"Test name",placeholder:"e.g. Urinalysis"},{key:"date",label:"Date done",placeholder:"DD/MM/YYYY"},{key:"note",label:"Note",placeholder:"e.g. Results normal"}] },
          currentFood:{ title:"Edit current food", fields:[{key:"brand",label:"Brand & food name",placeholder:"e.g. Royal Canin Adult"},{key:"portion",label:"Portion per meal (g)",placeholder:"e.g. 280"},{key:"meals",label:"Meals per day",placeholder:"e.g. 2"}] },
        };
        const c = cfg[addSheet.type];
        const isValid = c.fields.slice(0,1).every(f => (addForm[f.key]||"").trim().length > 0);
        const packaged_kw = ["royal canin","pedigree","hills","drools","purina","kibble","wet food","can","pouch","whiskas","iams","eukanuba","orijen","acana"];
        const classifyFood = (label="") => packaged_kw.some(k=>label.toLowerCase().includes(k)) ? "packaged" : "homemade";
        return (
          <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setAddSheet(null)}>
            <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
              <div style={{width:40,height:4,background:"#E0E0E0",borderRadius:2,margin:"0 auto 20px"}}/>
              <div style={{fontWeight:700,fontSize:16,marginBottom:c.hint?6:18}}>{c.title}</div>
              {c.hint && <div style={{fontSize:12,color:"#8E8E93",marginBottom:18}}>{c.hint}</div>}
              <div style={{display:"flex",flexDirection:"column",gap:12}}>
                {c.fields.map(f=>(
                  <div key={f.key}>
                    <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>{f.label}</div>
                    <input value={addForm[f.key]||""} onChange={e=>setAddForm(p=>({...p,[f.key]:e.target.value}))} placeholder={f.placeholder}
                      style={{width:"100%",padding:"10px 14px",borderRadius:10,border:"1.5px solid #E8E4DF",fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif",color:"#1A1A1A"}}/>
                  </div>
                ))}
              </div>
              <button onClick={()=>{ if(isValid){
                if(addSheet.type==="addFood"){
                  const type = classifyFood(addForm.label||"");
                  const icon = type==="packaged"?"🥣":"🥗";
                  setDietRows(prev=>[...prev,{id:"d"+Date.now(),type,icon,label:addForm.label||"",detail:addForm.detail||""}]);
                }
                setAddSheet(null); setAddForm({});
              }}}
                style={{width:"100%",marginTop:20,background:isValid?"#D44800":"#D1D1D6",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:isValid?"pointer":"default"}}>
                Save
              </button>
              <button onClick={()=>{ setAddSheet(null); setAddForm({}); }} style={{width:"100%",background:"none",border:"none",color:"#8E8E93",padding:"10px",fontSize:13,cursor:"pointer",marginTop:4}}>Cancel</button>
            </div>
          </div>
        );
      })()}

      <GStyles/>
    </div>
  );
}

// ─── STEP 4: WhatsApp Reminders ───────────────────────────────────────────────

function RemindersStep({ onBack }) {
  const [active, setActive]   = useState(null);
  const [ordered, setOrdered] = useState([]);

  return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif"}}>
      <div style={{background:"white",padding:"20px 20px 16px",borderBottom:"1px solid #E8E4DF"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:4}}>
          <BackBtn onBack={onBack}/>
          <div style={{fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900}}>WhatsApp Reminder Schedule</div>
        </div>
        <div style={{color:"#8E8E93",fontSize:13}}>How PetCircle will remind you on WhatsApp</div>
      </div>

      {/* Timeline legend */}
      <div style={{padding:"12px 16px",display:"flex",gap:8,flexWrap:"wrap",background:"white",borderBottom:"1px solid #F0EDE8"}}>
        {[["7 days before","#FF9500"],["3 days before","#FF3B30"],["On due date","#FF3B30"],["Overdue","#8E8E93"]].map(([label,color],i)=>(
          <div key={i} style={{display:"flex",alignItems:"center",gap:6}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:color}}/>
            <div style={{fontSize:11,color:"#555"}}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{padding:16,maxWidth:500,margin:"0 auto",display:"flex",flexDirection:"column",gap:12}}>
        {whatsappReminders.map((rem,i)=>{
          const isOrdered = ordered.includes(rem.id);
          const color = WA_REMINDER_COLORS[rem.status];
          const bg    = WA_REMINDER_BG[rem.status];
          const label = WA_REMINDER_LABELS[rem.status];
          const isOpen = active===rem.id;
          return (
            <div key={rem.id} style={{background:"white",borderRadius:16,overflow:"hidden",border:`1.5px solid ${color}33`,boxShadow:`0 2px 12px ${color}15`,animation:`slideUp 0.3s ${i*0.06}s both ease`}}>
              <div style={{background:"#075E54",padding:"8px 12px",display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:28,height:28,borderRadius:"50%",background:"#25D366",display:"flex",alignItems:"center",justifyContent:"center",fontSize:14}}>🐾</div>
                <div style={{flex:1}}>
                  <div style={{color:"white",fontWeight:600,fontSize:12}}>PetCircle</div>
                  <div style={{color:"#B2DFDB",fontSize:10}}>Verified Business</div>
                </div>
                <div style={{background:color,color:"white",borderRadius:8,padding:"2px 8px",fontSize:9,fontWeight:700}}>{label}</div>
                {rem.daysOut>0&&<div style={{color:"rgba(255,255,255,0.7)",fontSize:10}}>{rem.daysOut}d before</div>}
              </div>
              <div style={{padding:12,background:"#ECE5DD"}}>
                <div style={{background:"white",borderRadius:"4px 14px 14px 14px",padding:"10px 12px",maxWidth:"90%",boxShadow:"0 1px 2px rgba(0,0,0,0.1)"}}>
                  <div style={{fontWeight:600,fontSize:13,marginBottom:4}}>{rem.title}</div>
                  <div style={{fontSize:12,color:"#444",lineHeight:1.5,marginBottom:8}}>{rem.body}</div>
                  {isOpen && !isOrdered && (
                    <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:8}}>
                      {rem.actions.map((act,j)=>(
                        <button key={j} onClick={()=>{if(j===0)setOrdered(o=>[...o,rem.id]);}}
                          style={{background:act.color,color:"white",border:"none",borderRadius:10,padding:"9px 14px",fontSize:13,fontWeight:700,cursor:"pointer",textAlign:"left"}}>
                          {act.label}
                        </button>
                      ))}
                    </div>
                  )}
                  {isOrdered && (
                    <div style={{background:"#F0FFF4",border:"1px solid #34C759",borderRadius:10,padding:"8px 12px",fontSize:12,color:"#1A6B2A",marginTop:8}}>
                      ✅ Order confirmed! Tracking link sent to WhatsApp.
                    </div>
                  )}
                  <div style={{fontSize:10,color:"#999",textAlign:"right",marginTop:4}}>{new Date().toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"})} ✓✓</div>
                </div>
              </div>
              {!isOpen&&!isOrdered&&(
                <button onClick={()=>setActive(rem.id)} style={{width:"100%",background:"#F7F4F0",border:"none",padding:"10px",fontSize:12,fontWeight:600,color:"#D44800",cursor:"pointer",borderTop:"1px solid #F0EDE8"}}>View Actions →</button>
              )}
              {isOpen&&!isOrdered&&(
                <button onClick={()=>setActive(null)} style={{width:"100%",background:"#F7F4F0",border:"none",padding:"10px",fontSize:12,fontWeight:600,color:"#8E8E93",cursor:"pointer",borderTop:"1px solid #F0EDE8"}}>Collapse ↑</button>
              )}
            </div>
          );
        })}

        <div style={{background:"#F0F6FF",border:"1.5px solid #007AFF",borderRadius:16,padding:16}}>
          <div style={{fontWeight:700,fontSize:14,marginBottom:8,color:"#007AFF"}}>📲 How WhatsApp reminders work</div>
          {REMINDER_EXPLAINER.map(([t,d],i)=>(
            <div key={i} style={{display:"flex",gap:10,padding:"6px 0",borderTop:i===0?"none":"1px solid #D0E4FF"}}>
              <div style={{fontSize:12,fontWeight:600,color:"#007AFF",flexShrink:0,minWidth:90}}>{t}</div>
              <div style={{fontSize:12,color:"#444"}}>{d}</div>
            </div>
          ))}
        </div>
      </div>
      <GStyles/>
    </div>
  );
}

// ─── STEP 5: Action Plan ──────────────────────────────────────────────────────

function NudgesStep({ onBack, onNext, onCart }) {
  const NUDGE_CART_MAP = { 1:"c2", 2:"c1", 3:"c3", 4:"c4", 5:"c5", 6:"c6", 7:"c7", 8:"c8", 9:"c11", 10:"c9" };
  const [dismissed,  setDismissed]  = useState([]);
  const [expanded,   setExpanded]   = useState(null);
  const [filter,     setFilter]     = useState("all");

  const active   = useMemo(()=>nudges.filter(n=>!dismissed.includes(n.id)), [dismissed]);
  const filtered = useMemo(()=>{
    const entry = NUDGE_FILTERS.find(f=>f.val===filter);
    return entry ? entry.fn(active) : active;
  }, [active, filter]);

  return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif"}}>
      <div style={{background:"white",padding:"20px 20px 0",borderBottom:"1px solid #E8E4DF"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:4}}>
          <BackBtn onBack={onBack}/>
          <div style={{fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900}}>Zayn's Action Plan</div>
        </div>
        <div style={{color:"#8E8E93",fontSize:13,marginBottom:12}}>
          {active.filter(n=>n.mandatory).length} mandatory · {active.filter(n=>!n.mandatory).length} recommended
        </div>
        <div onClick={onNext} style={{background:"#F0FFF4",border:"1px solid #25D366",borderRadius:12,padding:"10px 12px",display:"flex",alignItems:"center",gap:10,marginBottom:12,cursor:"pointer"}}>
          <div style={{fontSize:20}}>📲</div>
          <div style={{flex:1}}>
            <div style={{fontWeight:600,fontSize:13,color:"#1A6B2A"}}>WhatsApp Reminders Active</div>
            <div style={{fontSize:11,color:"#2E7D32"}}>5 reminders scheduled · Tap to preview</div>
          </div>
          <div style={{color:"#25D366",fontSize:14}}>→</div>
        </div>
        <div style={{display:"flex",gap:8,paddingBottom:12,overflowX:"auto",scrollbarWidth:"none"}}>
          {NUDGE_FILTERS.map(({val,label})=>(
            <button key={val} onClick={()=>setFilter(val)}
              style={{flexShrink:0,background:filter===val?"#D44800":"#F2EDE8",color:filter===val?"white":"#555",border:"none",borderRadius:20,padding:"6px 14px",fontSize:12,fontWeight:600,cursor:"pointer"}}>
              {label(active.length)}
            </button>
          ))}
        </div>
      </div>

      <div style={{padding:16,maxWidth:500,margin:"0 auto",display:"flex",flexDirection:"column",gap:10}}>
        {filtered.length===0 && (
          <div style={{textAlign:"center",padding:"60px 20px"}}>
            <div style={{fontSize:56,marginBottom:16}}>🎉</div>
            <div style={{fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:700,marginBottom:8}}>All done!</div>
            <div style={{color:"#8E8E93"}}>Zayn's care is up to date here.</div>
          </div>
        )}
        {filtered.map((nudge,i)=>{
          const cfg=PRI_CFG[nudge.pri]||PRI_CFG.medium;
          const isExp=expanded===nudge.id;
          return (
            <div key={nudge.id} style={{background:"white",borderRadius:16,overflow:"hidden",border:`1.5px solid ${cfg.border}`,boxShadow:`0 2px 12px ${cfg.border}22`,animation:`slideUp 0.3s ${i*0.05}s both ease`}}>
              <div onClick={()=>setExpanded(isExp?null:nudge.id)} style={{padding:"14px 16px",cursor:"pointer"}}>
                <div style={{display:"flex",alignItems:"flex-start",gap:12}}>
                  <div style={{width:44,height:44,borderRadius:12,background:cfg.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>{nudge.icon}</div>
                  <div style={{flex:1}}>
                    <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:3,flexWrap:"wrap"}}>
                      <div style={{fontWeight:700,fontSize:14}}>{nudge.title}</div>
                      <Badge label={cfg.label} color="white" bg={cfg.badge}/>
                      {nudge.mandatory&&<Badge label="MANDATORY" color="#FF3B30" bg="#FF3B3015"/>}
                    </div>
                    <div style={{fontSize:12,color:"#666",lineHeight:1.45}}>{nudge.msg}</div>
                  </div>
                  <div style={{fontSize:14,color:"#C7C7CC",flexShrink:0,transform:isExp?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
                </div>
              </div>
              {isExp&&(
                <div style={{borderTop:`1px solid ${cfg.border}40`,background:cfg.bg,padding:"12px 16px",display:"flex",gap:8,flexWrap:"wrap"}}>
                  {nudge.orderable&&(
                    <button onClick={()=>onCart(NUDGE_CART_MAP[nudge.id]||null)}
                      style={{flex:1,background:"#D44800",color:"white",border:"none",borderRadius:10,padding:10,fontWeight:700,fontSize:13,cursor:"pointer",minWidth:120}}>
                      {nudge.orderType==="homeVet"?"Book Now":"Order Now"}
                    </button>
                  )}
                  <button onClick={e=>{e.stopPropagation();setDismissed(d=>[...d,nudge.id]);setExpanded(null);}}
                    style={{background:"white",color:"#8E8E93",border:"1px solid #E0E0E0",borderRadius:10,padding:"10px 14px",fontWeight:600,fontSize:13,cursor:"pointer"}}>Dismiss</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <GStyles/>
    </div>
  );
}

// ─── STEP 6: Cart ─────────────────────────────────────────────────────────────

// CartItem extracted as a proper component (was duplicated for urgent/recommended sections)
function CartItem({ item, inCart, qty, onToggle, onQtyChange }) {
  return (
    <div style={{background:"white",borderRadius:12,border:`1.5px solid ${inCart?item.tagColor+"55":"#EBEBEB"}`,opacity:inCart?1:0.6,transition:"all 0.18s"}}>
      <div style={{display:"flex",alignItems:"center",gap:10,padding:"10px 12px"}}>
        <div style={{width:38,height:38,borderRadius:10,background:item.tagColor+"15",display:"flex",alignItems:"center",justifyContent:"center",fontSize:19,flexShrink:0}}>{item.icon}</div>
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:1}}>
            <span style={{fontWeight:700,fontSize:13,color:"#1A1A1A"}}>{item.name}</span>
            <span style={{background:item.tagColor+"18",color:item.tagColor,borderRadius:5,padding:"1px 6px",fontSize:9,fontWeight:800,letterSpacing:0.3,flexShrink:0}}>{item.tag}</span>
          </div>
          <div style={{fontSize:11,color:"#AEAEB2"}}>{item.sub}</div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8,flexShrink:0}}>
          <span style={{fontSize:14,fontWeight:800,color:"#D44800"}}>₹{item.price}</span>
          <button onClick={onToggle} style={{width:26,height:26,borderRadius:"50%",border:"none",background:inCart?"#D44800":"#F2EDE8",color:inCart?"white":"#777",fontSize:13,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",fontWeight:700,flexShrink:0}}>
            {inCart?"✓":"＋"}
          </button>
        </div>
      </div>
      {inCart && (
        <div style={{display:"flex",alignItems:"center",justifyContent:"flex-end",gap:6,padding:"6px 12px 8px",borderTop:"1px solid #F5F2EE"}}>
          <button onClick={()=>onQtyChange(qty-1)} style={{width:24,height:24,borderRadius:7,border:"1px solid #E0E0E0",background:"white",cursor:"pointer",fontSize:13,color:"#333",display:"flex",alignItems:"center",justifyContent:"center"}}>−</button>
          <span style={{fontWeight:700,fontSize:13,minWidth:14,textAlign:"center"}}>{qty}</span>
          <button onClick={()=>onQtyChange(qty+1)} style={{width:24,height:24,borderRadius:7,border:"1px solid #E0E0E0",background:"white",cursor:"pointer",fontSize:13,color:"#333",display:"flex",alignItems:"center",justifyContent:"center"}}>+</button>
          <span style={{fontSize:12,fontWeight:700,color:"#D44800",marginLeft:4}}>₹{(item.price*qty).toLocaleString("en-IN")}</span>
        </div>
      )}
    </div>
  );
}

function CartStep({ onBack, pinnedItemId }) {
  const [cart,   setCart]   = useState(()=>cartItemsData.reduce((a,i)=>({...a,[i.id]:i.inCart}),{}));
  const [qtys,   setQtys]   = useState(()=>cartItemsData.reduce((a,i)=>({...a,[i.id]:1}),{}));
  const [screen, setScreen] = useState("cart");
  const [payMethod,     setPayMethod]     = useState("upi");
  const [upiId,         setUpiId]         = useState("");
  const [coupon,        setCoupon]        = useState("");
  const [couponApplied, setCouponApplied] = useState(false);

  // Address state
  const [addresses, setAddresses] = useState([
    { id:"a1", name:"Ashita Arora", line:"Mumbai 400016", tag:"Home", selected:true },
  ]);
  const [addressSheet, setAddressSheet] = useState(null); // null | { mode:"edit"|"add", id?:string }
  const [addrForm, setAddrForm] = useState({ name:"", line:"", tag:"Home" });

  const selectedAddr = addresses.find(a=>a.selected) || addresses[0];

  const openEditAddress = () => {
    setAddrForm({ name:selectedAddr.name, line:selectedAddr.line, tag:selectedAddr.tag });
    setAddressSheet({ mode:"edit", id:selectedAddr.id });
  };
  const openAddAddress = () => {
    setAddrForm({ name:"", line:"", tag:"Home" });
    setAddressSheet({ mode:"add" });
  };
  const saveAddress = () => {
    if (!addrForm.name || !addrForm.line) return;
    if (addressSheet.mode === "edit") {
      setAddresses(prev => prev.map(a => a.id===addressSheet.id ? {...a,...addrForm} : a));
    } else {
      const newId = "a"+(addresses.length+1);
      setAddresses(prev => [...prev.map(a=>({...a,selected:false})), { id:newId,...addrForm, selected:true }]);
    }
    setAddressSheet(null);
  };

  // Card state
  const [cardNum,   setCardNum]   = useState("");
  const [cardName,  setCardName]  = useState("");
  const [cardExp,   setCardExp]   = useState("");
  const [cardCvv,   setCardCvv]   = useState("");
  // Net banking state
  const [netBank,   setNetBank]   = useState("");

  // Auto-add pinned item to cart on mount
  useEffect(()=>{
    if (pinnedItemId) {
      setCart(prev=>({...prev,[pinnedItemId]:true}));
    }
  }, [pinnedItemId]);

  // Sort helper: pinned item always first, then by original order
  const sortWithPin = useCallback((items) => {
    if (!pinnedItemId) return items;
    return [...items].sort((a,b)=>{
      if (a.id===pinnedItemId) return -1;
      if (b.id===pinnedItemId) return 1;
      return 0;
    });
  }, [pinnedItemId]);

  // Derived cart values memoised
  const { inCart, subtotal, discount, delivery, total } = useMemo(()=>{
    const inCart   = cartItemsData.filter(i=>cart[i.id]);
    const subtotal = inCart.reduce((s,i)=>s+i.price*qtys[i.id],0);
    const discount = couponApplied ? Math.round(subtotal*0.1) : 0;
    const delivery = subtotal>999 ? 0 : 49;
    return { inCart, subtotal, discount, delivery, total:subtotal-discount+delivery };
  }, [cart, qtys, couponApplied]);

  const toggleCart = useCallback((id)=>setCart(p=>({...p,[id]:!p[id]})), []);
  const setQty     = useCallback((id,v)=>setQtys(p=>({...p,[id]:Math.max(1,v)})), []);

  const urgentItems = useMemo(()=>sortWithPin(cartItemsData.filter(i=>i.inCart||i.id===pinnedItemId)),  [sortWithPin, pinnedItemId]);
  const recItems    = useMemo(()=>sortWithPin(cartItemsData.filter(i=>!i.inCart&&i.id!==pinnedItemId)), [sortWithPin, pinnedItemId]);

  if (screen==="success") return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:28,textAlign:"center"}}>
      <div style={{fontSize:64,marginBottom:12}}>🎉</div>
      <div style={{fontFamily:"'Fraunces',serif",fontSize:24,fontWeight:900,marginBottom:6}}>Order Confirmed!</div>
      <div style={{color:"#8E8E93",fontSize:13,marginBottom:24}}>Order ID: PC-{Math.floor(Math.random()*90000+10000)}</div>
      <div style={{background:"white",borderRadius:16,padding:16,width:"100%",maxWidth:360,marginBottom:20,textAlign:"left",border:"1.5px solid #34C75933"}}>
        {inCart.map(i=>(
          <div key={i.id} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"6px 0",borderBottom:"1px solid #F5F2EE"}}>
            <span style={{fontSize:13}}>{i.icon} {i.name}</span>
            <span style={{fontSize:13,fontWeight:700,color:"#D44800"}}>₹{(i.price*qtys[i.id]).toLocaleString("en-IN")}</span>
          </div>
        ))}
        <div style={{display:"flex",justifyContent:"space-between",paddingTop:8,marginTop:2}}>
          <span style={{fontWeight:700}}>Total paid</span>
          <span style={{fontWeight:800,color:"#D44800",fontSize:15}}>₹{total.toLocaleString("en-IN")}</span>
        </div>
      </div>
      <div style={{background:"#F0FFF4",borderRadius:12,padding:"10px 14px",width:"100%",maxWidth:360,marginBottom:20,fontSize:12,color:"#1A6B2A",textAlign:"left"}}>
        ✅ Payment received · Estimated delivery 1–2 business days<br/>
        🏠 Home vet visit & grooming scheduled for confirmed slots
      </div>
      <button onClick={onBack} style={{width:"100%",maxWidth:360,background:"#D44800",color:"white",border:"none",borderRadius:14,padding:14,fontSize:15,fontWeight:700,cursor:"pointer"}}>← Back to Dashboard</button>
      <GStyles/>
    </div>
  );

  const NET_BANKS = ["HDFC Bank","ICICI Bank","SBI","Axis Bank","Kotak Bank","Yes Bank"];
  const inputStyle = {width:"100%",padding:"10px 14px",borderRadius:10,border:"1.5px solid #E8E4DF",fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif",color:"#1A1A1A"};

  if (screen==="payment") return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif",paddingBottom:100}}>
      <div style={{background:"white",padding:"16px 16px 14px",borderBottom:"1px solid #E8E4DF",display:"flex",alignItems:"center",gap:12}}>
        <BackBtn onBack={()=>setScreen("cart")}/>
        <div style={{fontFamily:"'Fraunces',serif",fontSize:18,fontWeight:900}}>Payment</div>
      </div>

      <div style={{padding:16,maxWidth:500,margin:"0 auto",display:"flex",flexDirection:"column",gap:12}}>
        {/* Order summary pill */}
        <div style={{background:"white",borderRadius:14,padding:"12px 14px",display:"flex",justifyContent:"space-between",alignItems:"center",border:"1px solid #E8E4DF"}}>
          <div style={{fontSize:13,color:"#555"}}>{inCart.length} items for Zayn</div>
          <div style={{fontSize:16,fontWeight:800,color:"#D44800"}}>₹{total.toLocaleString("en-IN")}</div>
        </div>

        {/* Deliver to */}
        <div style={{background:"white",borderRadius:14,padding:"12px 14px",border:"1px solid #E8E4DF"}}>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>Deliver to</div>
          {addresses.map(addr=>(
            <div key={addr.id} onClick={()=>setAddresses(prev=>prev.map(a=>({...a,selected:a.id===addr.id})))}
              style={{display:"flex",alignItems:"center",gap:10,padding:"8px 0",borderBottom:"1px solid #F5F2EE",cursor:"pointer"}}>
              <div style={{width:18,height:18,borderRadius:"50%",border:`2px solid ${addr.selected?"#D44800":"#C7C7CC"}`,background:addr.selected?"#D44800":"white",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center"}}>
                {addr.selected&&<div style={{width:6,height:6,borderRadius:"50%",background:"white"}}/>}
              </div>
              <div style={{fontSize:18}}>📍</div>
              <div style={{flex:1}}>
                <div style={{fontWeight:600,fontSize:13}}>{addr.name}</div>
                <div style={{fontSize:12,color:"#8E8E93"}}>{addr.line} · {addr.tag}</div>
              </div>
              {addr.selected && (
                <button onClick={e=>{e.stopPropagation();openEditAddress();}}
                  style={{background:"none",border:"none",color:"#D44800",fontSize:12,fontWeight:700,cursor:"pointer",padding:"2px 6px"}}>Edit</button>
              )}
            </div>
          ))}
          <button onClick={openAddAddress}
            style={{marginTop:8,display:"flex",alignItems:"center",gap:8,background:"none",border:"1.5px dashed #D4480066",borderRadius:10,padding:"9px 12px",width:"100%",cursor:"pointer",color:"#D44800",fontWeight:600,fontSize:13}}>
            <span style={{fontSize:16}}>＋</span> Add new address
          </button>
        </div>

        {/* Payment method */}
        <div style={{background:"white",borderRadius:14,padding:"12px 14px",border:"1px solid #E8E4DF"}}>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:10}}>Payment method</div>
          {PAYMENT_METHODS.map((pm,idx)=>(
            <div key={pm.id}>
              <div onClick={()=>setPayMethod(pm.id)} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 0",borderBottom: (payMethod===pm.id&&(pm.id==="upi"||pm.id==="card"||pm.id==="net"))?"none":"1px solid #F5F2EE",cursor:"pointer"}}>
                <div style={{width:18,height:18,borderRadius:"50%",border:`2px solid ${payMethod===pm.id?"#D44800":"#C7C7CC"}`,background:payMethod===pm.id?"#D44800":"white",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center"}}>
                  {payMethod===pm.id&&<div style={{width:6,height:6,borderRadius:"50%",background:"white"}}/>}
                </div>
                <div style={{fontSize:20}}>{pm.icon}</div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:600,fontSize:13}}>{pm.label}</div>
                  <div style={{fontSize:11,color:"#8E8E93"}}>{pm.sub}</div>
                </div>
              </div>

              {/* UPI input */}
              {payMethod==="upi" && pm.id==="upi" && (
                <div style={{padding:"10px 0 14px",borderBottom:"1px solid #F5F2EE"}}>
                  <input value={upiId} onChange={e=>setUpiId(e.target.value)} placeholder="Enter UPI ID (e.g. name@upi)" style={inputStyle}/>
                </div>
              )}

              {/* Card input */}
              {payMethod==="card" && pm.id==="card" && (
                <div style={{padding:"10px 0 14px",borderBottom:"1px solid #F5F2EE",display:"flex",flexDirection:"column",gap:8}}>
                  <input value={cardNum} onChange={e=>setCardNum(e.target.value.replace(/\D/g,"").slice(0,16).replace(/(.{4})/g,"$1 ").trim())}
                    placeholder="Card number" style={inputStyle} maxLength={19}/>
                  <input value={cardName} onChange={e=>setCardName(e.target.value)}
                    placeholder="Name on card" style={inputStyle}/>
                  <div style={{display:"flex",gap:8}}>
                    <input value={cardExp} onChange={e=>{
                      let v=e.target.value.replace(/\D/g,"");
                      if(v.length>=2) v=v.slice(0,2)+"/"+v.slice(2,4);
                      setCardExp(v);
                    }} placeholder="MM/YY" style={{...inputStyle,flex:1}} maxLength={5}/>
                    <input value={cardCvv} onChange={e=>setCardCvv(e.target.value.replace(/\D/g,"").slice(0,4))}
                      placeholder="CVV" style={{...inputStyle,flex:1}} maxLength={4} type="password"/>
                  </div>
                </div>
              )}

              {/* Net banking input */}
              {payMethod==="net" && pm.id==="net" && (
                <div style={{padding:"10px 0 14px",borderBottom:"1px solid #F5F2EE"}}>
                  <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>Select your bank</div>
                  <div style={{display:"flex",flexWrap:"wrap",gap:6}}>
                    {NET_BANKS.map(bank=>(
                      <button key={bank} onClick={()=>setNetBank(bank)}
                        style={{padding:"7px 12px",borderRadius:20,border:`1.5px solid ${netBank===bank?"#D44800":"#E8E4DF"}`,background:netBank===bank?"#FFF3EE":"white",color:netBank===bank?"#D44800":"#555",fontSize:12,fontWeight:netBank===bank?700:500,cursor:"pointer"}}>
                        {bank}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Bill summary */}
        <div style={{background:"white",borderRadius:14,padding:"12px 14px",border:"1px solid #E8E4DF"}}>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:10}}>Bill summary</div>
          {[["Subtotal",`₹${subtotal.toLocaleString("en-IN")}`,"#1A1A1A"],...(couponApplied?[["Discount (10%)",`-₹${discount.toLocaleString("en-IN")}`,"#34C759"]]:[]),["Delivery",delivery===0?"FREE":`₹${delivery}`,delivery===0?"#34C759":"#1A1A1A"]].map(([l,v,c],i)=>(
            <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"5px 0",borderBottom:"1px solid #F5F2EE"}}>
              <span style={{fontSize:13,color:"#555"}}>{l}</span>
              <span style={{fontSize:13,fontWeight:600,color:c}}>{v}</span>
            </div>
          ))}
          <div style={{display:"flex",justifyContent:"space-between",paddingTop:10,marginTop:2}}>
            <span style={{fontWeight:700,fontSize:14}}>Total</span>
            <span style={{fontWeight:800,fontSize:16,color:"#D44800"}}>₹{total.toLocaleString("en-IN")}</span>
          </div>
        </div>
      </div>

      {/* Address bottom sheet */}
      {addressSheet && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",zIndex:300,display:"flex",alignItems:"flex-end",justifyContent:"center"}} onClick={()=>setAddressSheet(null)}>
          <div onClick={e=>e.stopPropagation()} style={{background:"white",borderRadius:"20px 20px 0 0",padding:24,width:"100%",maxWidth:430}}>
            <div style={{width:40,height:4,background:"#E0E0E0",borderRadius:2,margin:"0 auto 20px"}}/>
            <div style={{fontWeight:700,fontSize:16,marginBottom:4}}>{addressSheet.mode==="edit"?"Edit address":"Add new address"}</div>
            <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>Delivery details for Zayn's order</div>
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              <div>
                <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Full name</div>
                <input value={addrForm.name} onChange={e=>setAddrForm(f=>({...f,name:e.target.value}))} placeholder="e.g. Ashita Arora" style={inputStyle}/>
              </div>
              <div>
                <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Address & pincode</div>
                <input value={addrForm.line} onChange={e=>setAddrForm(f=>({...f,line:e.target.value}))} placeholder="e.g. Mumbai 400016" style={inputStyle}/>
              </div>
              <div>
                <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Tag</div>
                <div style={{display:"flex",gap:8}}>
                  {["Home","Work","Other"].map(tag=>(
                    <button key={tag} onClick={()=>setAddrForm(f=>({...f,tag}))}
                      style={{flex:1,padding:"8px 0",borderRadius:20,border:"none",background:addrForm.tag===tag?"#D44800":"#F2EDE8",color:addrForm.tag===tag?"white":"#555",fontWeight:600,fontSize:13,cursor:"pointer"}}>
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <button onClick={saveAddress}
              style={{width:"100%",marginTop:20,background:addrForm.name&&addrForm.line?"#D44800":"#D1D1D6",color:"white",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:700,cursor:addrForm.name&&addrForm.line?"pointer":"default"}}>
              Save Address
            </button>
            <button onClick={()=>setAddressSheet(null)} style={{width:"100%",background:"none",border:"none",color:"#8E8E93",padding:"10px",fontSize:13,cursor:"pointer",marginTop:4}}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{position:"fixed",bottom:0,left:"50%",transform:"translateX(-50%)",width:"100%",maxWidth:430,background:"white",borderTop:"1px solid #E8E4DF",padding:"10px 16px 24px",boxShadow:"0 -4px 20px rgba(0,0,0,0.08)",zIndex:100}}>
        <button onClick={()=>setScreen("success")} style={{width:"100%",background:"#D44800",color:"white",border:"none",borderRadius:14,padding:"14px",fontSize:15,fontWeight:700,cursor:"pointer"}}>
          Pay ₹{total.toLocaleString("en-IN")} →
        </button>
      </div>
      <GStyles/>
    </div>
  );

  return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif",paddingBottom:120}}>
      <div style={{background:"white",padding:"16px 16px 14px",borderBottom:"1px solid #E8E4DF",display:"flex",alignItems:"center",gap:12}}>
        <BackBtn onBack={onBack}/>
        <div style={{fontFamily:"'Fraunces',serif",fontSize:18,fontWeight:900}}>Zayn's Care Orders</div>
        <div style={{marginLeft:"auto",background:"#FF3B30",color:"white",borderRadius:20,padding:"3px 10px",fontSize:12,fontWeight:700}}>{inCart.length} items</div>
      </div>

      <div style={{padding:"16px 16px 0",maxWidth:500,margin:"0 auto",display:"flex",flexDirection:"column",gap:8}}>
        {pinnedItemId && (()=>{
          const pinned = cartItemsData.find(i=>i.id===pinnedItemId);
          return pinned ? (
            <div style={{background:"#FFF6ED",border:"1.5px solid #FF950055",borderRadius:12,padding:"9px 13px",display:"flex",alignItems:"center",gap:10,marginBottom:2}}>
              <span style={{fontSize:16}}>{pinned.icon}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:12,fontWeight:700,color:"#B86000"}}>Added from your dashboard</div>
                <div style={{fontSize:11,color:"#8E5A00"}}>{pinned.name} is at the top of your order</div>
              </div>
            </div>
          ) : null;
        })()}
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,margin:"4px 0 2px",paddingLeft:2}}>🚨 Urgent for Zayn</div>
        {urgentItems.map(item=>(
          <CartItem key={item.id} item={item} inCart={!!cart[item.id]} qty={qtys[item.id]} onToggle={()=>toggleCart(item.id)} onQtyChange={v=>setQty(item.id,v)}/>
        ))}
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,margin:"8px 0 2px",paddingLeft:2}}>✨ Recommended for Zayn</div>
        {recItems.map(item=>(
          <CartItem key={item.id} item={item} inCart={!!cart[item.id]} qty={qtys[item.id]} onToggle={()=>toggleCart(item.id)} onQtyChange={v=>setQty(item.id,v)}/>
        ))}
      </div>

      {/* Sticky footer */}
      <div style={{position:"fixed",bottom:0,left:"50%",transform:"translateX(-50%)",width:"100%",maxWidth:430,background:"white",borderTop:"1px solid #E8E4DF",padding:"10px 16px 20px",boxShadow:"0 -4px 20px rgba(0,0,0,0.08)",zIndex:100}}>
        <div style={{display:"flex",gap:8,marginBottom:8}}>
          <input value={coupon} onChange={e=>setCoupon(e.target.value)} placeholder="Coupon code"
            style={{flex:1,border:"1px solid #E0E0E0",borderRadius:10,padding:"7px 12px",fontSize:12,outline:"none",fontFamily:"'DM Sans',sans-serif"}}/>
          <button onClick={()=>{if(coupon.length>2)setCouponApplied(true);}}
            style={{background:couponApplied?"#34C759":"#F2EDE8",color:couponApplied?"white":"#555",border:"none",borderRadius:10,padding:"7px 14px",fontSize:12,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap"}}>
            {couponApplied?"✓ Applied":"Apply"}
          </button>
        </div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
          <div style={{fontSize:12,color:"#666"}}>
            {inCart.length} items · {delivery===0?<span style={{color:"#34C759",fontWeight:600}}>Free delivery</span>:`₹${delivery} delivery`}
            {couponApplied&&<span style={{color:"#34C759",fontWeight:600}}> · −₹{discount} off</span>}
          </div>
          <div style={{fontSize:17,fontWeight:800,color:"#D44800"}}>₹{total.toLocaleString("en-IN")}</div>
        </div>
        <button onClick={()=>setScreen("payment")} disabled={inCart.length===0}
          style={{width:"100%",background:inCart.length?"#D44800":"#D1D1D6",color:"white",border:"none",borderRadius:14,padding:"13px",fontSize:15,fontWeight:700,cursor:inCart.length?"pointer":"default"}}>
          Proceed to Payment →
        </button>
      </div>
      <GStyles/>
    </div>
  );
}

// ─── ROOT ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [step,           setStep]           = useState(0);
  const [petImg,         setPetImg]         = useState(null);
  const [pinnedCartItem, setPinnedCartItem] = useState(null);
  const stepLabels = ["Chat","AI","Dashboard","Actions","Reminders","Cart"];

  const goToCart = useCallback((itemId=null) => {
    setPinnedCartItem(itemId);
    setStep(5);
  }, []);

  return (
    <div style={{maxWidth:430,margin:"0 auto",minHeight:"100vh",position:"relative",boxShadow:"0 0 60px rgba(0,0,0,0.15)"}}>
      <div style={{position:"fixed",top:10,left:"50%",transform:"translateX(-50%)",zIndex:100,display:"flex",gap:5,pointerEvents:"none"}}>
        {stepLabels.map((_,i)=>(
          <div key={i} style={{height:3,borderRadius:2,background:i<=step?"#D44800":"rgba(180,180,180,0.4)",width:i===step?28:14,transition:"all 0.3s"}}/>
        ))}
      </div>
      {step===0 && <WhatsAppStep  onNext={()=>setStep(1)}/>}
      {step===1 && <ProcessingStep onNext={()=>setStep(2)} onBack={()=>setStep(0)}/>}
      {step===2 && <DashboardStep  onNext={()=>setStep(3)} onBack={()=>setStep(1)} onCart={goToCart} petImg={petImg} onPetImgChange={setPetImg}/>}
      {step===3 && <NudgesStep     onBack={()=>setStep(2)} onNext={()=>setStep(4)} onCart={goToCart}/>}
      {step===4 && <RemindersStep  onBack={()=>setStep(3)}/>}
      {step===5 && <CartStep       onBack={()=>setStep(2)} pinnedItemId={pinnedCartItem}/>}
    </div>
  );
}
