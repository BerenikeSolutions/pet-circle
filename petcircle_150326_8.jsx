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
  name:"Bruno", breed:"Golden Retriever", dob:"15/03/2022",
  gender:"Male", pincode:"400001", parent:"Priya Sharma",
  healthRecords: {
    vaccines: [
      { id:"9in1",        name:"9-in-1 (DHPPiL+)", mandatory:true,  freqMonths:12, lastGiven:"12/06/2023" },
      { id:"rabies",      name:"Rabies",            mandatory:true,  freqMonths:12, lastGiven:"20/06/2023" },
      { id:"kennelcough", name:"Kennel Cough",      mandatory:false, freqMonths:12, lastGiven:null },
      { id:"covid",       name:"Covid (CCoV)",      mandatory:false, freqMonths:12, lastGiven:null },
    ],
    deworming: { lastDone:"01/01/2024", nextDue:"01/04/2024", status:"overdue" },
    fleaTick:  { lastDone:null, nextDue:null, status:"missing" },
    checkups:  [{ name:"Annual Wellness Exam", lastDone:"15/03/2023", nextDue:"15/03/2025", status:"upcoming" }],
    grooming: [
      { name:"Bath & Brush",    icon:"🛁", lastDone:"10/01/2024", nextDue:"10/02/2024", freq:"Monthly",     status:"overdue",  note:"Goldens need monthly baths to manage shedding and skin oils." },
      { name:"Nail Trimming",   icon:"✂️", lastDone:"20/12/2023", nextDue:"20/02/2024", freq:"Every 6 wks", status:"overdue",  note:"Overgrown nails alter gait and stress joints." },
      { name:"Dental Cleaning", icon:"🦷", lastDone:null,          nextDue:null,          freq:"Annually",   status:"missing",  note:"Goldens are tartar-prone. Annual vet cleaning prevents gum disease." },
      { name:"Ear Cleaning",    icon:"👂", lastDone:"10/01/2024", nextDue:"10/03/2024", freq:"Every 6 wks", status:"upcoming", note:"Floppy ears trap moisture — key infection prevention." },
      { name:"Eye Wipe",        icon:"👁️", lastDone:"01/02/2024", nextDue:"01/03/2024", freq:"Monthly",     status:"upcoming", note:"Prevents tear stain buildup common in Goldens." },
    ],
    conditions: [{
      name:"Hip Dysplasia (Mild)", icon:"🦴", diagnosedOn:"10/09/2023",
      managedBy:"Dr. Meera Nair, Bandra", status:"managed",
      medications: [
        { name:"Meloxicam 1mg",      dose:"Once daily with food", refillDue:"01/04/2024", refillStatus:"upcoming", price:"₹280", orderable:true },
        { name:"Omega-3 Supplement", dose:"1 capsule daily",      refillDue:"15/03/2024", refillStatus:"urgent",   price:"₹349", orderable:true },
      ],
      monitoringChecks: [
        { name:"X-ray Follow-up",     nextDue:"10/09/2024", status:"upcoming" },
        { name:"Mobility Assessment", nextDue:"10/04/2024", status:"upcoming" },
      ],
      notes:"Avoid high-impact activities. Swimming recommended.",
    }],
    nutrition: {
      currentFood: { brand:"Royal Canin Golden Retriever Adult", type:"Dry Kibble", portionG:280, mealsPerDay:2 },
      supplements: ["Omega-3 (for hip)", "Calcium tablet"],
      homemade: [
        { ingredient:"Boiled chicken breast", quantity:"100g", frequency:"3x/week", notes:"Extra protein top-up" },
        { ingredient:"Steamed carrots",       quantity:"50g",  frequency:"Daily",   notes:"Treats and snacks" },
        { ingredient:"Brown rice",            quantity:"80g",  frequency:"2x/week", notes:"Mixed with kibble" },
      ],
      breedGaps: [
        { nutrient:"Vitamin E",   level:"Low",     reason:"Critical antioxidant for Goldens with joint issues; supports immune function.",      supplement:"Vit E 400 IU softgel", priority:"high",   orderable:true,  price:"₹349/mo" },
        { nutrient:"Glucosamine", level:"Missing", reason:"Essential for cartilage repair — especially important given Bruno's hip dysplasia.",  supplement:"Cosequin DS Chewable", priority:"urgent", orderable:true,  price:"₹799/mo" },
        { nutrient:"Probiotics",  level:"Low",     reason:"Goldens are prone to digestive issues. Gut health affects coat quality and immunity.", supplement:"FortiFlora Probiotic", priority:"medium", orderable:true,  price:"₹649/mo" },
        { nutrient:"Vitamin D",   level:"Low",     reason:"Supports bone density — relevant alongside hip dysplasia management.",                supplement:"Calcitriol 0.25mcg",  priority:"medium", orderable:true,  price:"₹299/mo" },
        { nutrient:"Zinc",        level:"Adequate",reason:"Current food provides sufficient zinc for coat and skin.",                            supplement:null,                  priority:"ok",     orderable:false, price:null },
        { nutrient:"Protein",     level:"Adequate",reason:"Royal Canin GR formula meets adult Golden protein requirements.",                     supplement:null,                  priority:"ok",     orderable:false, price:null },
      ],
    },
  },
};

const whatsappReminders = [
  { id:"r1", type:"deworming",  daysOut:7,  status:"upcoming", icon:"🪱", title:"Bruno's deworming is due in 1 week",     body:"Hi Priya 🐾 Bruno's deworming is due on 01 Apr. Protect him from intestinal parasites — order Drontal Plus delivered home or find a nearby vet.", actions:[{label:"🛒 Order Medicine — ₹189",color:"#25D366"},{label:"📍 Find Vet Nearby",color:"#075E54"}] },
  { id:"r2", type:"vaccine",    daysOut:7,  status:"upcoming", icon:"💉", title:"Bruno's Rabies booster due in 1 week",   body:"Hi Priya 🐾 Bruno's Rabies booster is due 20 Jun 2025. Book a home vet visit — no clinic queues, vaccinated at your doorstep.", actions:[{label:"🏠 Book Home Vet — ₹499",color:"#25D366"},{label:"📍 Find Clinic Nearby",color:"#075E54"}] },
  { id:"r3", type:"supplement", daysOut:7,  status:"upcoming", icon:"💊", title:"Meloxicam refill due in 1 week",         body:"Hi Priya 🐾 Bruno's Meloxicam (for hip dysplasia) refill is due 01 Apr. Don't let his pain management lapse — reorder now.", actions:[{label:"🔄 Reorder Meloxicam — ₹280",color:"#25D366"},{label:"⏭ Remind Later",color:"#8E8E93"}] },
  { id:"r4", type:"deworming",  daysOut:0,  status:"due",      icon:"🪱", title:"Bruno's deworming is due TODAY",         body:"Priya, today is the day for Bruno's deworming 🐾 Keep him protected — order now for same-day delivery or log if already done.", actions:[{label:"🛒 Order Now — ₹189",color:"#FF9500"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
  { id:"r5", type:"deworming",  daysOut:-7, status:"overdue",  icon:"🚨", title:"🚨 Bruno's deworming is 1 week overdue", body:"Priya, Bruno's deworming was due Apr 1 and is now a week overdue. Intestinal parasites can cause serious harm — please act today.", actions:[{label:"🛒 Order Now — ₹189",color:"#FF3B30"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
];

const nudges = [
  { id:1,  cat:"deworming", pri:"urgent", icon:"🪱", title:"Deworming Overdue",         msg:"Bruno's deworming was due 01 Apr 2024. Essential every 3 months against intestinal parasites.", mandatory:true,  orderable:true, price:"₹189", orderType:"medicine"   },
  { id:2,  cat:"vaccine",   pri:"urgent", icon:"💉", title:"DHPPiL Booster Overdue",     msg:"Bruno missed his annual DHPPiL booster — protects against 5 life-threatening diseases.",      mandatory:true,  orderable:true, price:"₹499", orderType:"homeVet"    },
  { id:3,  cat:"condition", pri:"urgent", icon:"🦴", title:"Omega-3 Refill Critical",    msg:"Bruno's Omega-3 for hip dysplasia runs out in 3 days. Missing doses worsen joint inflammation.", mandatory:true, orderable:true, price:"₹349", orderType:"supplement" },
  { id:4,  cat:"nutrition", pri:"urgent", icon:"💊", title:"Glucosamine Missing",        msg:"Bruno has hip dysplasia but no glucosamine supplement. Critical for cartilage repair.",         mandatory:true,  orderable:true, price:"₹799", orderType:"supplement" },
  { id:5,  cat:"flea",      pri:"high",   icon:"🐛", title:"No Flea & Tick Protection",  msg:"No flea/tick records for Bruno. Monthly protection essential in Mumbai's humid climate.",       mandatory:true,  orderable:true, price:"₹420", orderType:"medicine"   },
  { id:6,  cat:"nutrition", pri:"high",   icon:"🌿", title:"Vitamin E Deficiency",       msg:"Bruno's diet is low in Vitamin E — key antioxidant for Goldens with joint conditions.",        mandatory:false, orderable:true, price:"₹349", orderType:"supplement" },
  { id:7,  cat:"grooming",  pri:"high",   icon:"🛁", title:"Bath & Brush Overdue",       msg:"Bruno's last bath was Jan 10 — over a month overdue. Prevents matting and skin issues.",       mandatory:false, orderable:true, price:"₹599", orderType:"grooming"   },
  { id:8,  cat:"grooming",  pri:"high",   icon:"✂️", title:"Nail Trim Overdue",          msg:"Nails last trimmed Dec 20. Overgrown nails affect posture and cause joint stress.",            mandatory:false, orderable:true, price:"₹299", orderType:"grooming"   },
  { id:9,  cat:"nutrition", pri:"medium", icon:"🦠", title:"Probiotics Recommended",     msg:"Goldens are digestive-sensitive. A probiotic improves gut health, coat, and immunity.",        mandatory:false, orderable:true, price:"₹649", orderType:"supplement" },
  { id:10, cat:"vaccine",   pri:"medium", icon:"💉", title:"Bordetella Vaccine Missing",  msg:"No Bordetella record found. Required if Bruno visits parks, groomers, or boarding.",           mandatory:false, orderable:true, price:"₹499", orderType:"homeVet"    },
];

// Moved outside CartStep — never changes
const cartItemsData = [
  { id:"c1",  icon:"🏠", name:"Home Vet Visit",              sub:"Vaccination — DHPPiL + Rabies boosters",     price:499,  tag:"OVERDUE",         tagColor:"#FF3B30", inCart:true  },
  { id:"c2",  icon:"🪱", name:"Bayer Drontal Plus",          sub:"Deworming — overdue since Apr 2024",         price:189,  tag:"OVERDUE",         tagColor:"#FF3B30", inCart:true  },
  { id:"c3",  icon:"🫙", name:"Zesty Paws Omega-3",          sub:"Joint supplement — hip dysplasia refill",    price:349,  tag:"CRITICAL REFILL", tagColor:"#FF3B30", inCart:true  },
  { id:"c4",  icon:"🦴", name:"Nutramax Cosequin DS",        sub:"Joint supplement — glucosamine missing",     price:799,  tag:"MISSING",         tagColor:"#FF3B30", inCart:true  },
  { id:"c5",  icon:"🐛", name:"Boehringer NexGard",          sub:"Flea & tick protection — no record found",   price:420,  tag:"NO RECORD",       tagColor:"#FF9500", inCart:true  },
  { id:"c6",  icon:"🌿", name:"Vit E 400 IU Softgel",        sub:"Antioxidant — breed gap for Goldens",        price:349,  tag:"HIGH PRIORITY",   tagColor:"#FF9500", inCart:false },
  { id:"c7",  icon:"🛁", name:"Full Grooming Session",        sub:"Bath, brush & nail trim",                    price:799,  tag:"OVERDUE",         tagColor:"#FF9500", inCart:false },
  { id:"c8",  icon:"✂️", name:"Home Grooming — Nail Trim",   sub:"Nail care — affects gait & joints",          price:299,  tag:"OVERDUE",         tagColor:"#FF9500", inCart:false },
  { id:"c9",  icon:"💉", name:"Kennel Cough Vaccine",        sub:"Vaccination — recommended for park/boarding",price:349,  tag:"NOT GIVEN",       tagColor:"#FF9500", inCart:false },
  { id:"c10", icon:"💉", name:"CCoV (Covid) Vaccine",        sub:"Vaccination — optional, no record found",    price:349,  tag:"NOT GIVEN",       tagColor:"#FF9500", inCart:false },
  { id:"c11", icon:"🦠", name:"Purina FortiFlora Probiotic", sub:"Gut health — breed recommendation",           price:649,  tag:"BREED REC",       tagColor:"#007AFF", inCart:false },
  { id:"c12", icon:"☀️", name:"Sun Pharma Calcitriol",       sub:"Vitamin D — bone density, hip support",      price:299,  tag:"LOW",             tagColor:"#B8860B", inCart:false },
  { id:"c13", icon:"🥣", name:"Royal Canin GR Adult",        sub:"Main food — breed-specific kibble reorder",  price:2499, tag:"REORDER",         tagColor:"#34C759", inCart:false },
  { id:"c14", icon:"🩺", name:"Home Vet — Wellness Exam",    sub:"Annual checkup — due Mar 2025",               price:799,  tag:"UPCOMING",        tagColor:"#007AFF", inCart:false },
];

// WhatsApp conversation — outside component, never recreated
const WHATSAPP_CONV = [
  { from:"bot",  text:"Hi Priya! 🐾 Welcome to *PetCircle* — India's first preventive pet health platform. Let's build Bruno's complete health profile.", delay:600 },
  { from:"user", text:"Sure! Let's go 😊", delay:0 },
  { from:"bot",  text:"Perfect! Share a *photo of Bruno* and his *name*.", delay:800 },
  { from:"user", text:"📷 Bruno.jpg  |  His name is Bruno!", delay:0 },
  { from:"bot",  text:"Adorable! 😍 What's Bruno's *breed*, *date of birth*, and *gender*?", delay:700 },
  { from:"user", text:"Golden Retriever, 15 March 2022, Male", delay:0 },
  { from:"bot",  text:"Got it. And your *pincode*? Helps us find nearby vets and labs.", delay:700 },
  { from:"user", text:"400001", delay:0 },
  { from:"bot",  text:"What does Bruno *currently eat*? Let's start with packaged food — brand and type (dry/wet).", delay:700 },
  { from:"user", text:"Royal Canin Golden Retriever Adult dry kibble, ~280g twice a day", delay:0 },
  { from:"bot",  text:"Do you add any *homemade food* to his diet? (chicken, rice, veggies, eggs etc.) Type 'None' if not.", delay:700 },
  { from:"user", text:"Yes — boiled chicken 3x a week, steamed carrots daily, sometimes brown rice", delay:0 },
  { from:"bot",  text:"Great 🥗 Any *supplements* Bruno is currently on?", delay:700 },
  { from:"user", text:"Omega-3 and a calcium tablet daily. Also on Meloxicam for mild hip dysplasia.", delay:0 },
  { from:"bot",  text:"Got it 🦴 Last step — *upload vaccination cards, prescriptions, or health records*. Multiple photos welcome!", delay:800 },
  { from:"user", text:"📎 vaccine_card.jpg\n📎 deworming_record.jpg\n📎 hip_xray_report.jpg", delay:0 },
  { from:"bot",  text:"🤖 *Analysing Bruno's records & nutrition...*\n\nParsing records · Mapping nutrition gaps · Building care plan", delay:1200, isProcessing:true },
  { from:"bot",  text:"✅ Profile complete!\n\n• Found Rabies & Distemper vaccines, deworming entry\n• Hip dysplasia plan logged\n• *3 nutrition gaps* identified for Golden Retrievers\n\nOpening Bruno's Health Dashboard →", delay:2000 },
];

const PROCESSING_TASKS = [
  "Reading vaccination card...", "Parsing deworming record...", "Extracting hip dysplasia report...",
  "Analysing nutrition label...", "Identifying breed-specific gaps...", "Calculating next due dates...",
  "Mapping WhatsApp reminder schedule...", "Building supplement recommendations...", "Profile ready ✓",
];

const DASHBOARD_TABS = [["overview","Overview"],["medical","Health"],["grooming","Hygiene"],["nutrition","Nutrition"],["conditions","Conditions"]];

const DAILY_HYGIENE_ITEMS = [
  { id:"coat-brush",  icon:"🪮", name:"Coat Brushing",  note:"Prevents matting & reduces shedding in Goldens.",     lastDone:"Today",      status:"done"     },
  { id:"teeth-brush", icon:"🦷", name:"Teeth Brushing", note:"Daily brushing prevents plaque and gum disease.",      lastDone:"2 days ago", status:"overdue"  },
  { id:"ear-clean",   icon:"👂", name:"Ear Cleaning",   note:"Floppy ears trap moisture — key infection prevention.", lastDone:"10/01/2024", status:"upcoming" },
  { id:"eye-wipe",    icon:"👁️", name:"Eye Wipe",       note:"Prevents tear stain buildup common in Goldens.",       lastDone:"01/02/2024", status:"upcoming" },
];

const PERIODIC_HYGIENE_ITEMS = [
  { id:"bath-nail",  icon:"🛁", name:"Bath, brush & nail trim", note:"Monthly baths manage shedding & skin oils. Nail trims prevent joint stress.", lastDone:"10/01/2024",   status:"overdue"  },
  { id:"anal-gland", icon:"🐾", name:"Anal gland cleaning",     note:"Prevents impaction & discomfort. Goldens are prone to anal gland issues.",   lastDone:"Not recorded", status:"upcoming" },
];

const DOC_SECTIONS = [
  { id:"vaccination", icon:"💉", label:"Vaccination Card",  color:"#34C759", bg:"#F0FFF4", files:[{ name:"vaccine_card.jpg",    parsed:"Rabies · 20 Jun 2023",              note:"Next due: 20 Jun 2024",        status:"Parsed ✓" },{ name:"vaccine_card.jpg",    parsed:"9-in-1 (DHPPiL+) · 12 Jun 2023",   note:"Next due: 12 Jun 2024",        status:"Parsed ✓" }] },
  { id:"prescriptions",icon:"📋",label:"Prescriptions",     color:"#007AFF", bg:"#F0F6FF", files:[{ name:"hip_xray_report.jpg", parsed:"Meloxicam 1mg — once daily",          note:"Hip dysplasia management",     status:"Parsed ✓" },{ name:"hip_xray_report.jpg", parsed:"Omega-3 Supplement — 1 capsule daily", note:"Joint inflammation support",   status:"Parsed ✓" }] },
  { id:"reports",      icon:"🔬",label:"Reports",            color:"#FF9500", bg:"#FFF6ED", files:[{ name:"hip_xray_report.jpg", parsed:"Hip X-Ray — Mild dysplasia confirmed", note:"Dr. Meera Nair · 10 Sep 2023", status:"Parsed ✓" },{ name:"deworming_record.jpg",parsed:"Deworming record · Last done 01 Jan 2024",note:"Next due: 01 Apr 2024",        status:"Parsed ✓" }] },
];

const NUDGE_FILTERS = [
  { val:"all",       label:(n)=>`All (${n})`,  fn:(active)=>active },
  { val:"mandatory", label:()=>"🔴 Must Do",   fn:(active)=>active.filter(n=>n.mandatory) },
  { val:"nutrition", label:()=>"🥣 Nutrition", fn:(active)=>active.filter(n=>n.cat==="nutrition") },
  { val:"grooming",  label:()=>"🛁 Grooming",  fn:(active)=>active.filter(n=>n.cat==="grooming") },
];

const NUTRITION_MACROS = [
  { name:"Protein",       icon:"🥩", actual:28, target:30, unit:"%", status:"low",  note:"Slightly below optimal for an active adult Golden." },
  { name:"Fat",           icon:"🧈", actual:14, target:14, unit:"%", status:"ok",   note:"Within healthy range." },
  { name:"Carbohydrates", icon:"🌾", actual:46, target:40, unit:"%", status:"high", note:"Slightly elevated — monitor for weight gain." },
  { name:"Fibre",         icon:"🥦", actual:3,  target:4,  unit:"%", status:"low",  note:"Could be improved with more vegetable additions." },
  { name:"Moisture",      icon:"💧", actual:10, target:10, unit:"%", status:"ok",   note:"Normal for dry kibble." },
];

const NUTRITION_VITAMINS = [
  { name:"Vitamin E",  status:"Low",      supplement:"Vit E 400 IU",       price:"₹349/mo", priority:"high"   },
  { name:"Vitamin D",  status:"Low",      supplement:"Calcitriol 0.25mcg", price:"₹299/mo", priority:"medium" },
  { name:"Vitamin B12",status:"Adequate", supplement:null, price:null, priority:"ok" },
  { name:"Vitamin C",  status:"Adequate", supplement:null, price:null, priority:"ok" },
];

const NUTRITION_MINERALS = [
  { name:"Glucosamine", icon:"🦴", status:"Missing",  priority:"urgent", reason:"Essential for cartilage repair — especially important given Bruno's hip dysplasia.", supplement:"Cosequin DS Chewable",  price:"₹799/mo" },
  { name:"Calcium",     icon:"🥛", status:"Adequate", priority:"ok",     reason:"Supplement in use. Bone support in place.",                                          supplement:null, price:null },
  { name:"Zinc",        icon:"⚡", status:"Adequate", priority:"ok",     reason:"Royal Canin GR provides sufficient zinc for coat and skin.",                          supplement:null, price:null },
  { name:"Iron",        icon:"🔩", status:"Adequate", priority:"ok",     reason:"Adequate from current kibble and chicken.",                                           supplement:null, price:null },
];

const NUTRITION_OTHERS = [
  { name:"Omega-3",    icon:"🐟", status:"Adequate", priority:"ok",     reason:"Supplement in use. Maintain current dose.",                                        supplement:null,                    price:null },
  { name:"Probiotics", icon:"🦠", status:"Low",      priority:"medium", reason:"Goldens are digestive-sensitive. A probiotic improves gut health, coat & immunity.", supplement:"FortiFlora Probiotic", price:"₹649/mo" },
];

const DIAGNOSTICS_ITEMS = [
  { icon:"🩸", name:"Blood Work (CBC / Chemistry)", last:"10/09/2023", note:"Done alongside hip dysplasia diagnosis" },
  { icon:"🦴", name:"X-Ray (Hip)",                  last:"10/09/2023", note:"Hip dysplasia confirmed, mild" },
  { icon:"🔬", name:"Urinalysis",                   last:"—",          note:"No record", optional:true },
];

const PAYMENT_METHODS = [
  { id:"upi",  label:"UPI",             icon:"📱", sub:"Pay via any UPI app" },
  { id:"card", label:"Card",            icon:"💳", sub:"Credit / Debit card" },
  { id:"net",  label:"Net Banking",     icon:"🏦", sub:"All major banks" },
  { id:"cod",  label:"Cash on Delivery",icon:"💵", sub:"Pay when delivered" },
];

const NUTRITION_IMPROVE = [
  { dot:"#FF3B30", text:"Glucosamine missing → critical for hip joint support" },
  { dot:"#FF9500", text:"Vitamin E & D low → immunity & bone density" },
  { dot:"#FF9500", text:"Protein slightly low → muscle recovery & energy" },
  { dot:"#FF9500", text:"Calories below target → increase daily portions" },
  { dot:"#FFCC00", text:"Probiotics low → gut health & coat quality" },
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
  return diff < 0 ? "overdue" : diff <= 60 ? "upcoming" : "done";
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
  const hr = pet.healthRecords;

  const categories = [
    { key:"vaccines", label:"Vaccines",       icon:"💉", weight:25, calc:() => {
        const mandatory = hr.vaccines.filter(v=>v.mandatory);
        const scores = mandatory.map(v => v.lastGiven ? 0.7 : 0);
        const avg = scores.reduce((a,b)=>a+b,0) / (mandatory.length||1);
        return { score:avg, detail:`${mandatory.filter(v=>v.lastGiven).length}/${mandatory.length} mandatory recorded`, drag:avg<0.5 };
    }},
    { key:"deworming", label:"Deworming & Flea", icon:"🪱", weight:20, calc:() => {
        const avg = (CARE_SCORE[hr.deworming.status]||0 + CARE_SCORE[hr.fleaTick.status]||0) / 2;
        const issues = [hr.deworming.status!=="done"&&`Deworming ${hr.deworming.status}`, hr.fleaTick.status!=="done"&&`Flea/tick ${hr.fleaTick.status}`].filter(Boolean);
        return { score:avg, detail:issues.length ? issues.join(", ") : "All current", drag:avg<0.5 };
    }},
    { key:"conditions", label:"Condition Mgmt", icon:"🦴", weight:20, calc:() => {
        if (!hr.conditions.length) return { score:1, detail:"No active conditions", drag:false };
        const meds = hr.conditions.flatMap(c=>c.medications);
        const avg = meds.map(m=>m.refillStatus==="urgent"?0.2:m.refillStatus==="upcoming"?0.7:1).reduce((a,b)=>a+b,0) / meds.length;
        const urgent = meds.filter(m=>m.refillStatus==="urgent");
        return { score:avg, detail:urgent.length ? `${urgent.map(m=>m.name.split(" ")[0]).join(", ")} refill critical` : "Medications on track", drag:avg<0.5 };
    }},
    { key:"nutrition", label:"Nutrition", icon:"🥣", weight:20, calc:() => {
        const gaps = hr.nutrition.breedGaps;
        const avg = gaps.map(g=>PRIORITY_SCORE[g.priority]||0).reduce((a,b)=>a+b,0) / gaps.length;
        const critical = gaps.filter(g=>g.priority==="urgent"||g.priority==="high");
        return { score:avg, detail:critical.length ? `${critical.map(g=>g.nutrient).join(", ")} ${critical.length===1?"gap":"gaps"}` : "Diet balanced", drag:avg<0.5 };
    }},
    { key:"grooming", label:"Grooming", icon:"🛁", weight:10, calc:() => {
        const avg = hr.grooming.map(g=>CARE_SCORE[g.status]||0).reduce((a,b)=>a+b,0) / hr.grooming.length;
        const overdue = hr.grooming.filter(g=>g.status==="overdue").length;
        return { score:avg, detail:overdue ? `${overdue} overdue` : "All current", drag:avg<0.4 };
    }},
    { key:"checkups", label:"Checkups", icon:"🩺", weight:5, calc:() => {
        const avg = hr.checkups.map(c=>CARE_SCORE[c.status]||0).reduce((a,b)=>a+b,0) / hr.checkups.length;
        return { score:avg, detail:avg>=0.7?"On schedule":"Overdue", drag:avg<0.4 };
    }},
  ];

  const breakdown = categories.map(cat => {
    const { score, detail, drag } = cat.calc();
    return { ...cat, score, weighted:score * cat.weight, detail, drag };
  });

  const total = Math.round(breakdown.reduce((a,b)=>a+b.weighted, 0));
  return {
    total,
    label:      total>=85?"Excellent":total>=65?"Good":total>=45?"Fair":"Poor",
    labelColor: total>=85?"#34C759":total>=65?"#FF9500":"#FF3B30",
    ringColor:  total>=85?"#34C759":total>=65?"#FF9500":"#FF3B30",
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
        <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>How often should Bruno do this?</div>
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
                    <div style={{fontWeight:600,marginBottom:6}}>🤖 Analysing Bruno's records & nutrition...</div>
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
      <div style={{color:"white",fontFamily:"'Fraunces',serif",fontSize:26,fontWeight:700,marginBottom:8,textAlign:"center"}}>Analysing Bruno's Profile</div>
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

  // Editable diet state
  const [dietRows, setDietRows] = useState([
    { id:"d1", type:"packaged",  icon:"🥣", label:"Royal Canin Golden Retriever Adult", detail:"Dry kibble · 280g × 2/day" },
    { id:"d2", type:"homemade",  icon:"🥗", label:"Boiled chicken breast",             detail:"100g · 3x/week" },
    { id:"d3", type:"homemade",  icon:"🥗", label:"Steamed carrots",                   detail:"50g · Daily" },
    { id:"d4", type:"homemade",  icon:"🥗", label:"Brown rice",                        detail:"80g · 2x/week" },
  ]);
  const [editDietRow, setEditDietRow] = useState(null); // {id, label, detail} | null
  const [editDietForm, setEditDietForm] = useState({label:"", detail:""});

  const [vaccineState, setVaccineState] = useState({
    "9in1":        { lastGiven:"12/06/2023", freqMonths:12 },
    "rabies":      { lastGiven:"20/06/2023", freqMonths:12 },
    "kennelcough": { lastGiven:null,         freqMonths:12, reminder:false },
    "covid":       { lastGiven:null,         freqMonths:12, reminder:false },
  });
  const [editingVaxDate, setEditingVaxDate] = useState(null);
  const [vaxDateInput, setVaxDateInput]     = useState("");
  const [vaxFreqModal, setVaxFreqModal]     = useState(null);

  const [dwLastDone,  setDwLastDone]  = useState(mockPetData.healthRecords.deworming.lastDone);
  const [ftLastDone,  setFtLastDone]  = useState(mockPetData.healthRecords.fleaTick.lastDone);
  const [editingCareDate, setEditingCareDate] = useState(null);
  const [careDateInput,   setCareDateInput]   = useState("");

  const [periodicDates, setPeriodicDates] = useState({ "bath-nail":"10/01/2024", "anal-gland":null });
  const [editingGroomDate, setEditingGroomDate] = useState(null);
  const [groomDateInput,   setGroomDateInput]   = useState("");

  const [openRemId,       setOpenRemId]       = useState(null);
  const [orderedRem,      setOrderedRem]      = useState([]);
  const [openDocSection,  setOpenDocSection]  = useState(null);

  const [contacts, setContacts] = useState([
    { id:"ct1", type:"vet",      icon:"🩺", name:"Dr. Meera Nair",      clinic:"Paws & Claws Clinic, Bandra", phone:"+91 98200 11234", note:"Managing hip dysplasia" },
    { id:"ct2", type:"groomer",  icon:"✂️", name:"Snip & Shine Grooming", clinic:"Link Road, Andheri West",    phone:"+91 99300 55678", note:"Monthly bath & trim" },
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
    "chk-xray":         { freq:1, unit:"year",  reminder:true  },
    "chk-urine":        { freq:1, unit:"year",  reminder:false },
    "chk-fecal":        { freq:1, unit:"year",  reminder:false },
  });

  const [checkupDates, setCheckupDates] = useState({
    "chk-vet":   "15/03/2023",
    "chk-blood": "10/09/2023",
    "chk-xray":  "10/09/2023",
    "chk-urine": null,
    "chk-fecal": null,
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
      subtext: lastDone ? `Last: ${lastDone}${nextDue ? `  ·  Next: ${nextDue}` : ""}` : "No record found",
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
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Bruno's diet is <strong style={{color:"#FF9500"}}>moderate</strong> — base nutrition covered but has gaps needing attention.</div>
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
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Add a joint health supplement + Vitamin E & D to Bruno's daily routine.</div>
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

              {[["Name / Clinic name","name","Dr. Meera Nair"],["Address / Location","clinic","Paws & Claws Clinic, Bandra"],["Phone number","phone","+91 98200 00000"],["Note (optional)","note","e.g. Managing hip dysplasia"]].map(([lbl,key,ph])=>(
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
      const sub = v.lastGiven ? `Given: ${v.lastGiven}${v.nextDue?`  ·  Next: ${v.nextDue}`:""}` : isMandatory?"No record":"Not given yet";
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

        {/* Annual Health Checkups */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #8E8E9344",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          {(()=>{
            const checkupItems = [
              { id:"chk-vet",   icon:"🩺", name:"Vet Visit (Annual Wellness)", note:"Full physical exam — weight, joints, coat, ears, teeth",           optional:false },
              { id:"chk-blood", icon:"🩸", name:"Blood Work (CBC / Chemistry)",  note:"Screens for anaemia, organ function & infection markers",           optional:false },
              { id:"chk-xray",  icon:"🦴", name:"X-Ray (Hip)",                   note:"Hip dysplasia follow-up — done alongside diagnosis",                optional:false },
              { id:"chk-urine", icon:"💧", name:"Urinalysis",                    note:"Kidney & urinary tract health check",                               optional:true  },
              { id:"chk-fecal", icon:"🔬", name:"Fecal Analysis",                note:"Screens for intestinal parasites beyond what deworming covers",     optional:true  },
            ];
            const doneCount = checkupItems.filter(c=>checkupDates[c.id]).length;
            const totalRequired = checkupItems.filter(c=>!c.optional).length;
            const doneRequired  = checkupItems.filter(c=>!c.optional && checkupDates[c.id]).length;
            const pct = Math.round((doneRequired/totalRequired)*100);
            const barColor = pct===100?"#34C759":pct>=50?"#FF9500":"#FF3B30";
            const statusLabel = pct===100?"Up to Date":pct===0?"No Record":"In Progress";
            const statusColor = pct===100?"#34C759":pct===0?"#8E8E93":"#FF9500";
            const statusBg    = pct===100?"#F0FFF4":pct===0?"#F2F2F7":"#FFF6ED";
            return (
              <>
                <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:6}}>
                  <div style={{width:44,height:44,borderRadius:12,background:"#F2F2F7",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>🩺</div>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700,fontSize:15}}>Annual Health Checkups</div>
                    <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Vet visit, blood work, imaging & more</div>
                  </div>
                  <div style={{background:statusBg,color:statusColor,borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>{statusLabel}</div>
                </div>

                {/* Progress bar */}
                <div style={{marginBottom:10}}>
                  <div style={{display:"flex",justifyContent:"space-between",fontSize:11,color:"#8E8E93",marginBottom:4}}>
                    <span>{doneRequired}/{totalRequired} required completed</span>
                    <span style={{fontWeight:700,color:barColor}}>{pct}%</span>
                  </div>
                  <div style={{height:6,borderRadius:3,background:"#F2F2F7",overflow:"hidden"}}>
                    <div style={{height:"100%",borderRadius:3,background:barColor,width:`${pct}%`,transition:"width 0.5s ease"}}/>
                  </div>
                </div>

                <div style={{background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:8,padding:"6px 10px",marginBottom:10,fontSize:11,color:"#8B5E00",lineHeight:1.4}}>
                  ℹ️ Annual panels catch thyroid dysfunction, anaemia & organ changes before symptoms appear — critical for Goldens.
                </div>

                <div style={{display:"flex",flexDirection:"column",gap:8,marginBottom:10}}>
                  {checkupItems.map((d)=>{
                    const last = checkupDates[d.id];
                    const nextDue = last ? addMonths(last, 12) : null;
                    const diff = nextDue ? diffDaysFromToday(nextDue) : null;
                    const status = !last ? (d.optional?"optional":"missing") : diff < 0 ? "overdue" : diff <= 60 ? "upcoming" : "done";
                    const c  = status==="done"?"#34C759":status==="overdue"?"#FF3B30":status==="upcoming"?"#FF9500":"#8E8E93";
                    const bg = status==="done"?"#F0FFF4":status==="overdue"?"#FFF0F0":status==="upcoming"?"#FFF6ED":"#F2F2F7";
                    const lbl= status==="done"?"Done":status==="overdue"?"Overdue":status==="upcoming"?"Due Soon":d.optional?"Optional":"No Record";
                    return (
                      <div key={d.id} style={{background:"#FAFAF9",borderRadius:10,border:`1px solid ${c}22`,overflow:"hidden"}}>
                        <div style={{display:"flex",alignItems:"center",gap:10,padding:"9px 10px"}}>
                          <div style={{fontSize:18,flexShrink:0}}>{d.icon}</div>
                          <div style={{flex:1,minWidth:0}}>
                            <div style={{fontSize:12,fontWeight:600,color:"#1A1A1A"}}>
                              {d.name}
                              {d.optional&&<span style={{fontSize:10,color:"#8E8E93",fontWeight:400,marginLeft:4}}>(Optional)</span>}
                            </div>
                            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>
                              {last ? `Last: ${last}${nextDue?` · Next: ${nextDue}`:""}` : d.note}
                            </div>
                          </div>
                          <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
                            <div style={{background:bg,color:c,borderRadius:20,padding:"3px 9px",fontSize:10,fontWeight:700}}>{lbl}</div>
                            <button onClick={()=>{setEditingCheckupId(d.id);setCheckupDateInput(last||"");}}
                              style={{background:"#F2EDE8",border:"none",borderRadius:8,padding:"4px 8px",fontSize:11,color:"#555",cursor:"pointer",fontWeight:600}}>✎</button>
                          </div>
                        </div>
                        <div style={{borderTop:"1px solid #F0EDE8"}}>
                          <ReminderBar id={d.id} settings={itemSettings} setSettings={setItemSettings} onFreqClick={setFreqModal}/>
                        </div>
                      </div>
                    );
                  })}
                  <AddRow label="Add checkup record" onClick={()=>{ setAddForm({}); setAddSheet({type:"diagnostic"}); }}/>
                </div>
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
            { date:"15 Mar 2022", weight:3.2,  note:"First vet visit — puppy weight" },
            { date:"10 Sep 2022", weight:14.5, note:"6-month checkup" },
            { date:"15 Mar 2023", weight:28.1, note:"1-year wellness exam" },
            { date:"10 Sep 2023", weight:31.4, note:"Hip dysplasia diagnosis visit" },
            { date:"10 Jan 2024", weight:32.8, note:"Grooming visit — weighed on scale" },
          ];
          const latest = entries[entries.length-1];
          const prev    = entries[entries.length-2];
          const diff    = (latest.weight - prev.weight).toFixed(1);
          const trend   = diff > 0 ? "up" : diff < 0 ? "down" : "stable";
          const tColor  = trend==="up"?"#FF9500":trend==="down"?"#34C759":"#007AFF";
          const tIcon   = trend==="up"?"↑":trend==="down"?"↓":"→";
          const ideal   = { min:27, max:34 };
          const inRange = latest.weight >= ideal.min && latest.weight <= ideal.max;
          const max = Math.max(...entries.map(e=>e.weight)) * 1.1;
          return (
            <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #007AFF33",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
              <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
                <div style={{width:44,height:44,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>⚖️</div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:700,fontSize:15}}>Weight Log</div>
                  <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Ideal range for Golden: {ideal.min}–{ideal.max} kg</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontWeight:800,fontSize:20,color:"#1A1A1A",lineHeight:1}}>{latest.weight} <span style={{fontSize:12,fontWeight:500,color:"#8E8E93"}}>kg</span></div>
                  <div style={{fontSize:11,fontWeight:700,color:tColor}}>{tIcon} {Math.abs(diff)} kg since last</div>
                </div>
              </div>

              {/* Status pill */}
              <div style={{background:inRange?"#F0FFF4":"#FFF6ED",border:`1px solid ${inRange?"#34C75944":"#FF950044"}`,borderRadius:8,padding:"6px 10px",marginBottom:12,fontSize:11,color:inRange?"#1A6B2A":"#8B5E00",fontWeight:600}}>
                {inRange?"✅ Weight is within healthy range for Bruno's breed & age":"⚠️ Weight slightly above ideal — monitor closely given hip dysplasia"}
              </div>

              {/* Sparkline bar chart */}
              <div style={{display:"flex",alignItems:"flex-end",gap:6,height:60,marginBottom:8}}>
                {entries.map((e,i)=>{
                  const h = Math.round((e.weight/max)*60);
                  const isLast = i===entries.length-1;
                  return (
                    <div key={i} style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",gap:3}}>
                      <div style={{fontSize:9,color:isLast?"#1A1A1A":"#AEAEB2",fontWeight:isLast?700:400}}>{e.weight}</div>
                      <div style={{width:"100%",height:h,borderRadius:"4px 4px 0 0",background:isLast?"#007AFF":"#007AFF33",transition:"height 0.4s ease"}}/>
                    </div>
                  );
                })}
              </div>
              <div style={{display:"flex",justifyContent:"space-between"}}>
                {entries.map((e,i)=>(
                  <div key={i} style={{flex:1,textAlign:"center",fontSize:9,color:"#AEAEB2"}}>{e.date.split(" ")[2]?.slice(2)||e.date.split(" ")[1]}</div>
                ))}
              </div>

              {/* Log table */}
              <div style={{marginTop:12,display:"flex",flexDirection:"column",gap:4}}>
                {[...entries].reverse().map((e,i)=>(
                  <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"7px 10px",background:i===0?"#F0F6FF":"#FAFAF9",borderRadius:8,border:i===0?"1px solid #007AFF22":"1px solid #F0EDE8"}}>
                    <div style={{fontSize:11,color:"#8E8E93",width:70,flexShrink:0}}>{e.date.split(" ").slice(0,2).join(" ")}</div>
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
          <div style={{fontWeight:700,fontSize:14,marginBottom:12}}>🔔 Order reminders</div>
          {[
            {icon:"🥣",label:"Royal Canin Golden Retriever Adult",sub:"Monthly reorder",id:"nutrition"},
            {icon:"🐟",label:"Salmon Oil Omega-3",sub:"Monthly supplement",id:"omega3"},
          ].map((item,i)=>{
            const s=itemSettings[item.id]||{freq:1,unit:"month",reminder:false};
            return (
              <div key={item.id} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 0",borderTop:i===0?"none":"1px solid #F0EDE8"}}>
                <div style={{width:36,height:36,borderRadius:10,background:"#F7F4F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>{item.icon}</div>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{item.label}</div>
                  <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>{item.sub}</div>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
                  <div onClick={()=>setFreqModal({id:item.id,freq:s.freq,unit:s.unit,isItem:true})}
                    style={{display:"inline-flex",alignItems:"center",gap:3,background:s.reminder?"#EFF6FF":"#F2F2F7",color:s.reminder?"#007AFF":"#AEAEB2",borderRadius:20,padding:"3px 9px",fontSize:11,fontWeight:600,cursor:"pointer"}}>
                    🔁 {freqLabel(s.freq,s.unit)} <span style={{fontSize:10,opacity:0.7}}>✎</span>
                  </div>
                  <Toggle on={s.reminder} onToggle={()=>setItemSettings(prev=>({...prev,[item.id]:{...prev[item.id],reminder:!prev[item.id].reminder}}))}/>
                </div>
              </div>
            );
          })}
          <button onClick={()=>onCart("c13")}
            style={{width:"100%",marginTop:12,background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"11px",fontSize:13,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:6}}>
            🛒 Order Now
          </button>
        </div>

        {/* Nutrition insight summary */}
        <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #D4480033",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
            <div style={{width:38,height:38,borderRadius:10,background:"#FFF3EE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>🐾</div>
            <div style={{fontWeight:700,fontSize:14,color:"#1A1A1A"}}>Nutrition note</div>
          </div>
          <div style={{background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#8B5E00",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>Overall diet</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Bruno's diet is <strong style={{color:"#FF9500"}}>moderate</strong> — good base, a few gaps to address.</div>
          </div>
          <div style={{background:"#F0F6FF",border:"1px solid #007AFF33",borderRadius:10,padding:"8px 11px",marginBottom:7}}>
            <div style={{fontSize:10,fontWeight:700,color:"#005BBB",textTransform:"uppercase",letterSpacing:0.4,marginBottom:5}}>What to improve</div>
            {NUTRITION_IMPROVE.map((item,i)=>(
              <div key={i} style={{display:"flex",alignItems:"flex-start",gap:7,marginBottom:i===NUTRITION_IMPROVE.length-1?0:5}}>
                <div style={{width:6,height:6,borderRadius:"50%",background:item.dot,flexShrink:0,marginTop:4}}/>
                <span style={{fontSize:12,color:"#333",lineHeight:1.4}}>{item.text}</span>
              </div>
            ))}
          </div>
          <div style={{background:"#F0FFF4",border:"1px solid #34C75933",borderRadius:10,padding:"8px 11px",marginBottom:14}}>
            <div style={{fontSize:10,fontWeight:700,color:"#1A6B2A",textTransform:"uppercase",letterSpacing:0.4,marginBottom:2}}>Our recommendation</div>
            <div style={{fontSize:12,color:"#3A3A3A",lineHeight:1.5}}>Add glucosamine + Vitamin E & D supplements to Bruno's daily routine.</div>
          </div>
        </div>

        {/* Combined calorie + nutrition analysis */}
        <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #FF3B3044",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
          <div style={{background:"#FFF0F0",padding:"14px 16px",borderBottom:"1px solid #F0EDE8"}}>
            <div style={{display:"flex",alignItems:"center",gap:10}}>
              <div style={{flex:1}}>
                <div style={{fontWeight:800,fontSize:15,color:"#1A1A1A",letterSpacing:-0.2}}>Nutrition breakdown</div>
                <div style={{fontSize:11,color:"#8E8E93",marginTop:2}}>Calories · macros · vitamins · minerals</div>
              </div>
              <div style={{background:"white",color:"#FF3B30",borderRadius:20,padding:"4px 12px",fontSize:11,fontWeight:700,boxShadow:"0 1px 4px rgba(255,59,48,0.15)"}}>Gaps found</div>
            </div>
          </div>
          <div style={{padding:16}}>
            {/* Calories */}
            <div style={{marginBottom:14}}>
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:8}}>
                <div style={{display:"flex",alignItems:"center",gap:6}}><span style={{fontSize:15}}>🔥</span><span style={{fontWeight:700,fontSize:12,color:"#555",textTransform:"uppercase",letterSpacing:0.4}}>Calories</span></div>
                <div style={{background:calBg,color:calC,borderRadius:20,padding:"2px 9px",fontSize:10,fontWeight:700}}>{calLbl}</div>
              </div>
              <div style={{display:"flex",justifyContent:"space-between",fontSize:11,color:"#8E8E93",marginBottom:4}}>
                <span>Current: <strong style={{color:"#1A1A1A"}}>{calActual} kcal/day</strong></span>
                <span>Target: <strong style={{color:"#1A1A1A"}}>{calTarget} kcal/day</strong></span>
              </div>
              <div style={{height:8,background:"#F2F2F7",borderRadius:4,overflow:"hidden",marginBottom:4}}>
                <div style={{height:"100%",width:`${Math.min(calPct,100)}%`,background:calC,borderRadius:4,transition:"width 0.8s ease"}}/>
              </div>
              <div style={{fontSize:11,color:calC,fontWeight:600}}>{calDiff<0?`${Math.abs(calDiff)} kcal below target — consider increasing portions`:calDiff>0?`${calDiff} kcal above target — monitor weight`:"Calorie intake well-balanced"}</div>
            </div>

            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:14}}>
              <div style={{flex:1,height:1,background:"#F0EDE8"}}/>
              <div style={{fontSize:10,fontWeight:700,color:"#AEAEB2",textTransform:"uppercase",letterSpacing:0.5}}>Detailed analysis</div>
              <div style={{flex:1,height:1,background:"#F0EDE8"}}/>
            </div>
            <div style={{fontSize:11,color:"#8B5E00",background:"#FFF6ED",border:"1px solid #FF950044",borderRadius:10,padding:"7px 10px",marginBottom:12}}>
              💡 Analysis based on Golden Retriever breed profile + Bruno's hip dysplasia
            </div>

            {/* Macros */}
            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Macronutrients</div>
            <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:14}}>
              {visibleMacros.map((m,i)=>{
                const c=m.status==="ok"?"#34C759":m.status==="low"?"#FF9500":"#FF3B30";
                const bg=m.status==="ok"?"#F0FFF4":m.status==="low"?"#FFF6ED":"#FFF0F0";
                const lbl=m.status==="ok"?"Adequate":m.status==="low"?"Low":"High";
                const barPct=Math.min((m.actual/Math.max(m.target,m.actual))*100,100);
                const tgtPct=Math.min((m.target/Math.max(m.target,m.actual))*100,100);
                return (
                  <div key={i} style={{padding:"9px 10px",background:"#FAFAF9",borderRadius:10,border:`1px solid ${c}22`}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:5}}>
                      <span style={{fontSize:15}}>{m.icon}</span>
                      <span style={{fontWeight:600,fontSize:13,flex:1}}>{m.name}</span>
                      <span style={{fontSize:11,color:"#8E8E93"}}>{m.actual}{m.unit} / {m.target}{m.unit}</span>
                      <div style={{background:bg,color:c,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>{lbl}</div>
                    </div>
                    <div style={{height:5,background:"#EBEBEB",borderRadius:3,position:"relative"}}>
                      <div style={{height:"100%",width:`${barPct}%`,background:c,borderRadius:3}}/>
                      <div style={{position:"absolute",top:-2,left:`${tgtPct}%`,width:2,height:9,background:"#555",borderRadius:1,opacity:0.25}}/>
                    </div>
                    <div style={{fontSize:10,color:"#AEAEB2",marginTop:3}}>{m.note}</div>
                  </div>
                );
              })}
            </div>

            {/* Vitamins */}
            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Vitamins</div>
            <div style={{padding:"10px 12px",background:"#FAFAF9",borderRadius:10,border:`1px solid ${vitaminOverall}22`,marginBottom:14}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:vitaminGaps.length?8:0}}>
                <span style={{fontSize:16}}>🧪</span><span style={{fontWeight:600,fontSize:13,flex:1}}>Vitamins</span>
                <div style={{background:vitaminBg,color:vitaminOverall,borderRadius:20,padding:"2px 8px",fontSize:10,fontWeight:700}}>{vitaminLbl}</div>
              </div>
              {vitaminGaps.length>0 && (
                <div style={{display:"flex",flexDirection:"column",gap:4}}>
                  {vitaminGaps.map((v,i)=>(
                    <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"6px 8px",background:v.status==="Missing"?"#FFF0F0":"#FFF6ED",borderRadius:8}}>
                      <div style={{width:6,height:6,borderRadius:"50%",background:v.status==="Missing"?"#FF3B30":"#FF9500",flexShrink:0}}/>
                      <span style={{fontSize:12,fontWeight:600,flex:1}}>{v.name}</span>
                      <span style={{fontSize:10,color:"#007AFF"}}>→ {v.supplement} · {v.price}</span>
                    </div>
                  ))}
                  {NUTRITION_VITAMINS.filter(v=>v.status==="Adequate").map((v,i)=>(
                    <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"4px 8px"}}>
                      <div style={{width:6,height:6,borderRadius:"50%",background:"#34C759",flexShrink:0}}/>
                      <span style={{fontSize:11,color:"#8E8E93",flex:1}}>{v.name}</span>
                      <span style={{fontSize:10,color:"#34C759",fontWeight:600}}>Adequate</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Minerals */}
            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Minerals</div>
            <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:14}}>
              {[...NUTRITION_MINERALS].sort((a,b)=>priorityRank[a.priority]-priorityRank[b.priority]).map((m,i)=><NutrientRow key={i} {...m}/>)}
            </div>

            {/* Other nutrients */}
            <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Other key nutrients</div>
            <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:14}}>
              {[...NUTRITION_OTHERS].sort((a,b)=>priorityRank[a.priority]-priorityRank[b.priority]).map((m,i)=><NutrientRow key={i} {...m}/>)}
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
          💡 Frequencies are breed-adjusted for Golden Retrievers. Tap the frequency pill to customise.
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
              const subtext = lastDone ? `Last: ${lastDone}${nextDue?`  ·  Next: ${nextDue}`:""}` : "No record";
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
    const [open, setOpen] = useState(false);
    const timeline = [
      { date:"10 Sep 2023", type:"diagnostic", icon:"🦴", title:"Hip X-Ray", detail:"Mild hip dysplasia confirmed. Dr. Meera Nair, Bandra.", tag:"Diagnosis" },
      { date:"10 Sep 2023", type:"vet",         icon:"🩺", title:"Vet Visit — Dr. Meera Nair", detail:"Reviewed X-ray. Started Meloxicam 1mg once daily + Omega-3.", tag:"Vet Visit" },
      { date:"15 Mar 2024", type:"vet",         icon:"🩺", title:"Annual Wellness Exam due", detail:"Due since Mar 2024. Not yet completed — book recommended.", tag:"Overdue" },
      { date:"10 Apr 2024", type:"diagnostic",  icon:"🦿", title:"Mobility Assessment due", detail:"Scheduled follow-up for hip dysplasia. Not yet completed.", tag:"Upcoming" },
      { date:"10 Sep 2024", type:"diagnostic",  icon:"🦴", title:"X-Ray Follow-up due", detail:"Annual hip X-ray review. Scheduled with Dr. Meera Nair.", tag:"Upcoming" },
    ];
    const tagColors = { "Diagnosis":"#007AFF", "Vet Visit":"#34C759", "Treatment":"#FF9500", "Grooming":"#8E44AD", "Overdue":"#FF3B30", "Upcoming":"#FF9500" };
    return (
      <div style={{background:"white",borderRadius:16,overflow:"hidden",border:"1.5px solid #8E8E9333",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        <div onClick={()=>setOpen(o=>!o)} style={{padding:"14px 16px",display:"flex",alignItems:"center",gap:12,cursor:"pointer"}}>
          <div style={{width:44,height:44,borderRadius:12,background:"#F7F4F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📅</div>
          <div style={{flex:1}}>
            <div style={{fontWeight:700,fontSize:15}}>Management History</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Vet visits · diagnostics · treatments · last 2 years</div>
          </div>
          <div style={{fontSize:13,color:"#C7C7CC",transform:open?"rotate(180deg)":"none",transition:"transform 0.2s"}}>▾</div>
        </div>
        {open && (
          <div style={{borderTop:"1px solid #F0EDE8",padding:"4px 16px 16px"}}>
            {timeline.map((ev,i)=>(
              <div key={i} style={{display:"flex",gap:12,paddingTop:14,position:"relative"}}>
                {/* Vertical line */}
                {i < timeline.length-1 && <div style={{position:"absolute",left:15,top:30,bottom:-14,width:2,background:"#F0EDE8"}}/>}
                <div style={{width:30,height:30,borderRadius:"50%",background:tagColors[ev.tag]+"18",border:`2px solid ${tagColors[ev.tag]}44`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:14,flexShrink:0,zIndex:1}}>{ev.icon}</div>
                <div style={{flex:1,paddingBottom:i < timeline.length-1 ? 0 : 0}}>
                  <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:2,flexWrap:"wrap"}}>
                    <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{ev.title}</div>
                    <div style={{background:tagColors[ev.tag]+"18",color:tagColors[ev.tag],borderRadius:20,padding:"1px 7px",fontSize:10,fontWeight:700}}>{ev.tag}</div>
                  </div>
                  <div style={{fontSize:11,color:"#8E8E93",marginBottom:2}}>{ev.date}</div>
                  <div style={{fontSize:12,color:"#555",lineHeight:1.4}}>{ev.detail}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const ConditionsPdfCard = () => {
    const [generating, setGenerating] = useState(false);
    const [done, setDone]             = useState(false);
    return (
      <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #1A1A1A22",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
          <div style={{width:44,height:44,borderRadius:12,background:"#F7F4F0",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📄</div>
          <div style={{flex:1}}>
            <div style={{fontWeight:700,fontSize:15}}>Complete Health Analysis</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Download full PDF record for vet or insurance</div>
          </div>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:5,marginBottom:14}}>
          {[
            {icon:"🩺",label:"Vet visits & exams"},
            {icon:"🔬",label:"Diagnostics & imaging"},
            {icon:"💊",label:"Medications & dosage"},
            {icon:"🦴",label:"Conditions & diagnosis"},
            {icon:"📅",label:"Treatment chronology"},
            {icon:"⚖️",label:"Weight history"},
          ].map((r,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:6,padding:"5px 8px",background:"#F7F4F0",borderRadius:8}}>
              <span style={{fontSize:13}}>{r.icon}</span>
              <span style={{fontSize:11,color:"#555",fontWeight:500}}>{r.label}</span>
            </div>
          ))}
        </div>
        {done ? (
          <div style={{background:"#F0FFF4",border:"1px solid #34C75944",borderRadius:12,padding:"12px 14px",display:"flex",alignItems:"center",gap:10}}>
            <span style={{fontSize:20}}>✅</span>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:13,color:"#1A6B2A"}}>Bruno_Complete_Health.pdf ready</div>
              <div style={{fontSize:11,color:"#34C759",marginTop:2}}>Saved to your downloads</div>
            </div>
            <button onClick={()=>setDone(false)} style={{background:"none",border:"none",color:"#AEAEB2",fontSize:11,cursor:"pointer",padding:0}}>↺</button>
          </div>
        ) : (
          <button onClick={()=>{setGenerating(true);setTimeout(()=>{setGenerating(false);setDone(true);},2200);}}
            disabled={generating}
            style={{width:"100%",background:generating?"#F2EDE8":"#1A1A1A",color:generating?"#D44800":"white",border:"none",borderRadius:12,padding:"12px",fontSize:14,fontWeight:700,cursor:generating?"default":"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:8,transition:"all 0.2s"}}>
            {generating ? <><span style={{animation:"pulse 1s infinite"}}>⏳</span> Generating…</> : <>📥 Download PDF</>}
          </button>
        )}
      </div>
    );
  };

  const renderConditionsTab = () => (
    <div style={{display:"flex",flexDirection:"column",gap:12,animation:"slideUp 0.4s ease"}}>
      {pet.healthRecords.conditions.map((cond,i)=>(
        <div key={i} style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #007AFF",boxShadow:"0 2px 12px rgba(0,122,255,0.1)"}}>
          <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
            <div style={{width:44,height:44,borderRadius:12,background:"#F0F6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22}}>{cond.icon}</div>
            <div style={{flex:1}}>
              <div style={{fontWeight:700,fontSize:15}}>{cond.name}</div>
              <div style={{fontSize:12,color:"#8E8E93"}}>Diagnosed {cond.diagnosedOn} · {cond.managedBy}</div>
            </div>
            <Badge label="MANAGED" color="#007AFF" bg="#F0F6FF"/>
          </div>
          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:8}}>Current medications</div>
          {cond.medications.map((med,j)=>{
            const ms=ST_CFG[med.refillStatus]||ST_CFG.upcoming;
            return (
              <div key={j} style={{background:med.refillStatus==="urgent"?"#FFF0F0":"#F7F4F0",borderRadius:10,padding:"10px 12px",marginBottom:6}}>
                <div style={{display:"flex",alignItems:"center",gap:10}}>
                  <div style={{fontSize:16}}>💊</div>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:600,fontSize:13}}>{med.name}</div>
                    <div style={{fontSize:11,color:"#8E8E93"}}>{med.dose}</div>
                  </div>
                  <div style={{textAlign:"right"}}>
                    <div style={{fontSize:10,color:ms.color,fontWeight:700}}>Refill {med.refillDue}</div>
                    <Badge label={ms.label} color={ms.color} bg={ms.bg}/>
                  </div>
                </div>
                <ReminderBar id={j===0?"meloxicam":"omega3"} settings={itemSettings} setSettings={setItemSettings} onFreqClick={setFreqModal}/>
              </div>
            );
          })}
          <AddRow label="Add medication" onClick={()=>{ setAddForm({}); setAddSheet({type:"medication"}); }}/>
          {cond.medications.some(m=>m.refillStatus==="urgent"||m.refillStatus==="upcoming") && (
            <button onClick={()=>onCart("c3")}
              style={{width:"100%",marginTop:10,background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
              🔄 Order Medications
            </button>
          )}

          <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,margin:"14px 0 8px"}}>Monitoring checkups</div>
          {cond.monitoringChecks.map((chk,j)=>{
            const cs=ST_CFG[chk.status];
            return (
              <div key={j} style={{borderTop:j===0?"none":"1px solid #F0EDE8",paddingTop:j===0?0:8,marginTop:j===0?0:8}}>
                <div style={{display:"flex",alignItems:"center",gap:10,padding:"8px 0"}}>
                  <div style={{fontSize:16}}>🩺</div>
                  <div style={{flex:1,fontSize:13,fontWeight:500}}>{chk.name}</div>
                  <div style={{textAlign:"right"}}>
                    <div style={{fontSize:11,color:"#8E8E93"}}>{chk.nextDue}</div>
                    <Badge label={cs.label} color={cs.color} bg={cs.bg}/>
                  </div>
                </div>
                <ReminderBar id={j===0?"xray":"mobility"} settings={itemSettings} setSettings={setItemSettings} onFreqClick={setFreqModal}/>
              </div>
            );
          })}
          <button onClick={()=>onCart("c14")}
            style={{width:"100%",marginTop:12,background:"#D44800",color:"white",border:"none",borderRadius:10,padding:"10px",fontSize:13,fontWeight:700,cursor:"pointer"}}>
            📅 Book Tests
          </button>

          {/* PetCircle Recommendations — beyond what the vet has already noted */}
          {(() => {
            const recItems = [
              { icon:"🔬", title:"Annual Thyroid Panel (T3/T4)", reason:"Goldens on long-term Meloxicam are at higher risk of hypothyroidism. A baseline thyroid screen is not yet on record.", cartId:"c14", priority:"high" },
            ];
            const pColors = { urgent:"#FF3B30", high:"#FF9500", medium:"#007AFF" };
            const pBg     = { urgent:"#FFF0F0", high:"#FFF6ED", medium:"#F0F6FF" };
            const pLabel  = { urgent:"URGENT", high:"RECOMMENDED", medium:"SUGGESTED" };
            return (
              <div style={{marginTop:14}}>
                <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:10}}>
                  <div style={{width:20,height:20,borderRadius:6,background:"#D44800",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11}}>🐾</div>
                  <div style={{fontSize:11,fontWeight:700,color:"#D44800",textTransform:"uppercase",letterSpacing:0.6}}>PetCircle Recommendations</div>
                </div>
                <div style={{display:"flex",flexDirection:"column",gap:8}}>
                  {recItems.map((rec,k)=>(
                    <div key={k} style={{background:pBg[rec.priority],border:`1px solid ${pColors[rec.priority]}22`,borderRadius:10,padding:"10px 12px"}}>
                      <div style={{display:"flex",alignItems:"flex-start",gap:10}}>
                        <div style={{fontSize:18,flexShrink:0,marginTop:1}}>{rec.icon}</div>
                        <div style={{flex:1,minWidth:0}}>
                          <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:3,flexWrap:"wrap"}}>
                            <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>{rec.title}</div>
                            <div style={{background:pColors[rec.priority]+"22",color:pColors[rec.priority],borderRadius:20,padding:"1px 7px",fontSize:10,fontWeight:700,flexShrink:0}}>{pLabel[rec.priority]}</div>
                          </div>
                          <div style={{fontSize:11,color:"#555",lineHeight:1.45,marginBottom:rec.cartId?8:0}}>{rec.reason}</div>
                          {rec.cartId && (
                            <button onClick={()=>onCart(rec.cartId)}
                              style={{background:pColors[rec.priority],color:"white",border:"none",borderRadius:8,padding:"6px 12px",fontSize:11,fontWeight:700,cursor:"pointer"}}>
                              Order Now →
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      ))}
      <button style={{background:"white",border:"1.5px dashed #C7C7CC",borderRadius:14,padding:16,display:"flex",alignItems:"center",gap:12,cursor:"pointer",width:"100%"}}>
        <div style={{width:40,height:40,borderRadius:12,background:"#F2F2F7",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20}}>➕</div>
        <div><div style={{fontWeight:600,fontSize:14,color:"#333"}}>Add Another Condition</div><div style={{fontSize:12,color:"#8E8E93"}}>Diabetes, allergies, skin conditions & more</div></div>
      </button>

      {/* Last Vet Visit for condition manager */}
      <div style={{background:"white",borderRadius:16,padding:16,border:"1.5px solid #34C75933",boxShadow:"0 1px 6px rgba(0,0,0,0.06)"}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
          <div style={{width:44,height:44,borderRadius:12,background:"#F0FFF4",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>🩺</div>
          <div style={{flex:1}}>
            <div style={{fontWeight:700,fontSize:15}}>Last Vet Visit</div>
            <div style={{fontSize:11,color:"#AEAEB2",marginTop:1}}>Managing vet · condition follow-up</div>
          </div>
          <div style={{background:"#FFF6ED",color:"#FF9500",borderRadius:20,padding:"4px 11px",fontSize:11,fontWeight:700}}>Due Soon</div>
        </div>
        <div style={{display:"flex",flexDirection:"column",gap:8}}>
          <div style={{display:"flex",gap:12,padding:"10px 12px",background:"#FAFAF9",borderRadius:10,border:"1px solid #F0EDE8"}}>
            <div style={{width:38,height:38,borderRadius:10,background:"#F0FFF4",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>👩‍⚕️</div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontWeight:600,fontSize:13,color:"#1A1A1A"}}>Dr. Meera Nair</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>Paws & Claws Clinic · Bandra</div>
              <div style={{fontSize:11,color:"#8E8E93",marginTop:1}}>Hip Dysplasia — managing since Sep 2023</div>
            </div>
          </div>
          <div style={{display:"flex",gap:8}}>
            <div style={{flex:1,background:"#F7F4F0",borderRadius:10,padding:"9px 12px"}}>
              <div style={{fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.4,marginBottom:3}}>Last Visit</div>
              <div style={{fontSize:13,fontWeight:600,color:"#1A1A1A"}}>10 Sep 2023</div>
              <div style={{fontSize:11,color:"#FF9500",fontWeight:600,marginTop:2}}>6+ months ago</div>
            </div>
            <div style={{flex:1,background:"#FFF6ED",borderRadius:10,border:"1px solid #FF950033",padding:"9px 12px"}}>
              <div style={{fontSize:10,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.4,marginBottom:3}}>Next Due</div>
              <div style={{fontSize:13,fontWeight:600,color:"#1A1A1A"}}>10 Mar 2024</div>
              <div style={{fontSize:11,color:"#FF3B30",fontWeight:600,marginTop:2}}>Overdue</div>
            </div>
          </div>
          <div style={{background:"#F0F6FF",borderRadius:10,padding:"10px 12px",fontSize:12,color:"#007AFF",lineHeight:1.5}}>
            📋 Vet Notes: Avoid high-impact activities. Swimming recommended.
          </div>
        </div>
      </div>

      {/* ── MANAGEMENT CHRONOLOGY ──────────────────────────────────────── */}
      <ConditionsChronology/>

      {/* ── COMPLETE HEALTH SUMMARY PDF ───────────────────────────────── */}
      <ConditionsPdfCard/>
    </div>
  );

  return (
    <div style={{minHeight:"100vh",background:"#F7F4F0",fontFamily:"'DM Sans',sans-serif"}}>
      {/* Header */}
      <div style={{background:"linear-gradient(135deg,#D44800 0%,#FF9A6C 100%)",padding:"20px 20px 24px",position:"relative",overflow:"hidden"}}>
        <div style={{position:"absolute",top:-40,right:-40,width:200,height:200,borderRadius:"50%",background:"rgba(255,255,255,0.04)"}}/>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:14,position:"relative"}}>
          <Avatar name="Bruno" size={48} imgSrc={petImg} onImgChange={onPetImgChange}/>
          <div style={{flex:1}}>
            <div style={{color:"white",fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900,lineHeight:1}}>Bruno</div>
            <div style={{color:"rgba(255,255,255,0.7)",fontSize:12}}>Golden Retriever · 3 yrs · Mumbai</div>
            <div style={{color:"rgba(255,255,255,0.55)",fontSize:11,marginTop:1}}>Parent: Priya Sharma</div>
          </div>
        </div>
        <div onClick={onCart} style={{background:"transparent",border:"1px solid rgba(255,255,255,0.8)",borderRadius:12,padding:"10px 14px",display:"flex",alignItems:"center",gap:10,position:"relative",cursor:"pointer"}}>
          <div style={{width:36,height:36,borderRadius:10,background:"white",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0,position:"relative"}}>
            ⚡
            <div style={{position:"absolute",top:-5,right:-5,width:16,height:16,borderRadius:"50%",background:"#FF3B30",display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,fontWeight:700,color:"white"}}>5</div>
          </div>
          <div style={{flex:1}}>
            <div style={{color:"white",fontWeight:700,fontSize:13}}>5 Actions Due</div>
            <div style={{color:"rgba(255,255,255,0.65)",fontSize:11}}>Medicines · Vet visits · Supplements · Grooming</div>
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
        const labels = { "chk-vet":"Vet Visit", "chk-blood":"Blood Work", "chk-xray":"X-Ray (Hip)", "chk-urine":"Urinalysis", "chk-fecal":"Fecal Analysis" };
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
          <div style={{fontFamily:"'Fraunces',serif",fontSize:22,fontWeight:900}}>Bruno's Action Plan</div>
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
            <div style={{color:"#8E8E93"}}>Bruno's care is up to date here.</div>
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
    { id:"a1", name:"Priya Sharma", line:"Mumbai 400001", tag:"Home", selected:true },
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
          <div style={{fontSize:13,color:"#555"}}>{inCart.length} items for Bruno</div>
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
            <div style={{fontSize:12,color:"#8E8E93",marginBottom:20}}>Delivery details for Bruno's order</div>
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              <div>
                <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Full name</div>
                <input value={addrForm.name} onChange={e=>setAddrForm(f=>({...f,name:e.target.value}))} placeholder="e.g. Priya Sharma" style={inputStyle}/>
              </div>
              <div>
                <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.5,marginBottom:6}}>Address & pincode</div>
                <input value={addrForm.line} onChange={e=>setAddrForm(f=>({...f,line:e.target.value}))} placeholder="e.g. Mumbai 400001" style={inputStyle}/>
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
        <div style={{fontFamily:"'Fraunces',serif",fontSize:18,fontWeight:900}}>Bruno's Care Orders</div>
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
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,margin:"4px 0 2px",paddingLeft:2}}>🚨 Urgent for Bruno</div>
        {urgentItems.map(item=>(
          <CartItem key={item.id} item={item} inCart={!!cart[item.id]} qty={qtys[item.id]} onToggle={()=>toggleCart(item.id)} onQtyChange={v=>setQty(item.id,v)}/>
        ))}
        <div style={{fontSize:11,fontWeight:700,color:"#8E8E93",textTransform:"uppercase",letterSpacing:0.6,margin:"8px 0 2px",paddingLeft:2}}>✨ Recommended for Bruno</div>
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
