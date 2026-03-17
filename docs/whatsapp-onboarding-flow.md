# WhatsApp Onboarding Flow & AI Processing Animation

## 1. Conversation Flow

The onboarding follows a sequential WhatsApp conversation between the bot and pet parent:

| # | Sender | Message |
|---|--------|---------|
| 1 | Bot | "Welcome to PetCircle! 🐾 I'm your pet health assistant. I'll help you track vaccinations, medications, and preventive care — all through WhatsApp." |
| 2 | User | "Let's go!" |
| 3 | Bot | "Great! First, send me a photo of your pet and their name." |
| 4 | User | [Photo + name, e.g., "Bruno"] |
| 5 | Bot | "Hi Bruno! 🐶 Now tell me: breed, date of birth, and gender." |
| 6 | User | "Golden Retriever, 15 March 2021, Male" |
| 7 | Bot | "Got it! What's your pincode? This helps me find nearby vets and services." |
| 8 | User | "560001" |
| 9 | Bot | "What packaged food does Bruno eat? Include brand, type, and how much per day." |
| 10 | User | "Royal Canin Golden Retriever Adult, dry kibble, 280g twice a day" |
| 11 | Bot | "Does Bruno eat any homemade food?" |
| 12 | User | "Yes - boiled chicken + rice + carrots, once a day" |
| 13 | Bot | "Any supplements or medications Bruno takes regularly?" |
| 14 | User | "Salmon oil omega-3 daily, Meloxicam 7.5mg daily for hip dysplasia" |
| 15 | Bot | "Now upload Bruno's health records - vaccination cards, prescriptions, lab reports. You can send up to 10 files (JPEG, PNG, or PDF, max 10MB each)." |
| 16 | User | [Uploads 3 files] |
| 17 | Bot | "Processing Bruno's records... ⏳" |
| 18 | Bot | "✅ Bruno's profile is ready! Here's your dashboard: [link]" |

## 2. AI Processing Animation

When records are being processed, the dashboard shows a full-screen animation:

### Visual Design
- **Background**: Dark (#0A0A0A)
- **Progress ring**: 140px diameter, 8px stroke, brand color (#D44800)
- **Percentage**: Large white text inside ring

### Processing Steps (shown as checklist)
1. ✅ Reading vaccination card
2. ✅ Parsing deworming record
3. ✅ Extracting hip dysplasia report
4. ✅ Analysing nutrition label
5. ✅ Identifying breed-specific gaps
6. ⏳ Calculating next due dates
7. ⬜ Mapping WhatsApp reminder schedule
8. ⬜ Building supplement recommendations
9. ⬜ Profile ready

Each step transitions from ⬜ (pending) → ⏳ (processing) → ✅ (complete) with a green checkmark animation. The progress ring fills proportionally.

## 3. Data Fields Collected

| Field | Source | Example |
|-------|--------|---------|
| name | User message | "Bruno" |
| photo | User upload | pet_photo.jpg |
| breed | User message | "Golden Retriever" |
| dob | User message | "15 March 2021" |
| gender | User message | "Male" |
| pincode | User message | "560001" |
| currentFood.brand | User message | "Royal Canin Golden Retriever Adult" |
| currentFood.type | User message | "Dry kibble" |
| currentFood.portion | User message | "280g x 2/day" |
| homemadeItems | User message | "Boiled chicken + rice + carrots" |
| supplements | User message | "Salmon oil omega-3" |
| medications | User message | "Meloxicam 7.5mg" |
| healthRecords | User uploads | vaccination card, prescriptions, reports |

## 4. WhatsApp Reminder Templates

Five reminder types are sent via WhatsApp template messages:

### 4.1 Deworming Upcoming (7 days before)
- **Status**: Upcoming (color: #FF9500)
- **Title**: "🪱 Bruno's Deworming Due Soon"
- **Body**: "Bruno's next deworming dose is due in 7 days (March 22). Milbemax tablet — keep him protected against intestinal parasites."
- **Actions**: [Order Milbemax] [Set Reminder]

### 4.2 Vaccine Upcoming (7 days before)
- **Status**: Upcoming (color: #FF9500)
- **Title**: "💉 DHPPiL Booster Due Soon"
- **Body**: "Bruno's annual DHPPiL booster is due in 5 days (March 20). Book a vet visit to keep his core protection current."
- **Actions**: [Book Vet Visit] [Set Reminder]

### 4.3 Supplement Refill
- **Status**: Upcoming (color: #FF9500)
- **Title**: "🫙 Omega-3 Supplement Refill"
- **Body**: "Bruno's Zesty Paws Salmon Oil supply runs out in ~5 days. Reorder to maintain joint health support for his hip dysplasia."
- **Actions**: [Reorder Now] [Remind Later]

### 4.4 Deworming Due Today
- **Status**: Due (color: #D44800)
- **Title**: "🪱 Deworming Due Today"
- **Body**: "Bruno's Milbemax deworming dose is due today. Give the tablet with food for best absorption."
- **Actions**: [Mark as Done ✓] [Order Milbemax]

### 4.5 Deworming Overdue
- **Status**: Overdue (color: #FF3B30)
- **Title**: "⚠️ Deworming Overdue"
- **Body**: "Bruno's deworming is now 3 days overdue. Intestinal parasites can cause weight loss and digestive issues. Please give his Milbemax dose today."
- **Actions**: [Mark as Done ✓] [Order Milbemax]

## 5. Reminder Schedule Logic

The WhatsApp reminder engine follows this lifecycle for each preventive item:

| Timing | Action | Message Type |
|--------|--------|--------------|
| 1 week before due date | Send UPCOMING reminder | Informational + action buttons |
| Due date (9:00 AM IST) | Send DUE TODAY reminder | Action required |
| No action after due date | Send OVERDUE follow-up every 7 days | Escalating urgency |
| User marks as done | Stop series, schedule next cycle | Confirmation sent |
| Condition medications | Separate refill series per medication | Based on frequency + last refill date |

### Engine Rules
- Daily cron at 8:00 AM IST via GitHub Actions
- Stateless execution — queries DB for due items each run
- No duplicate reminders — deduplication enforced at DB level
- Single retry on WhatsApp API failure
- All messages logged to message_logs table
- Rate limit: max 20 messages/minute per phone number
