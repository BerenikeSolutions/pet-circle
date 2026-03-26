# PetCircle — WhatsApp Templates for Meta

## How to create each template in Meta Business Manager
1. Go to **WhatsApp Manager → Message Templates → Create Template**
2. Set the **Template Name** exactly as shown (lowercase, underscores)
3. Select **Language: English**
4. Select the **Category** listed for each template
5. Paste the **Body Text** — variables must be `{{1}}`, `{{2}}` etc.
6. Fill in the **Sample Variables** from the examples provided
7. Add **Quick Reply buttons** where indicated — set the button **Payload** exactly as shown (the backend routes on these values)
8. Submit for review

> **Buttons:** The 4 reminder templates require Quick Reply buttons embedded in the template itself (Meta template buttons). All other templates have no buttons — the conflict template sends buttons as a separate interactive message after the template.

---

## Group 1 — Reminders (Category: Utility)

---

### `petcircle_reminder_t7_v1`
**Sent:** 7 days before due date

**Body:**
```
Hi {{1}}! A quick heads-up from PetCircle 🐾

{{2}}'s {{3}} is coming up on {{4}}.

We'll remind you again on the due date, but if it's already done, just let us know below!
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Priya |
| `{{2}}` | Bruno |
| `{{3}}` | Rabies Vaccine · DHPPi |
| `{{4}}` | 02 Apr 2026 |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Already Done | `REMINDER_ALREADY_DONE` |
| Remind Me Later | `REMINDER_SNOOZE_7` |

---

### `petcircle_reminder_due_v1`
**Sent:** On the due date

**Body:**
```
Hi {{1}}, today is the day! 🐾

{{2}}'s {{3}} is due today.

Please let us know once it's done so we can update the health record and schedule the next one.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Priya |
| `{{2}}` | Bruno |
| `{{3}}` | Rabies Vaccine · DHPPi |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Done — Log It | `REMINDER_DONE` |
| Remind Me Later | `REMINDER_SNOOZE_7` |
| Order Now | `REMINDER_ORDER_NOW` |

---

### `petcircle_reminder_d3_v1`
**Sent:** 3 days after due date (if no response)

**Body:**
```
Hi {{1}}, just checking in on {{2}} 🐾

We haven't heard back about {{3}}, which was due on {{4}}.

Did it get done? Tap below to log it or let us know if you need to reschedule.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Priya |
| `{{2}}` | Bruno |
| `{{3}}` | Rabies Vaccine · DHPPi |
| `{{4}}` | 02 Apr 2026 |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Still Pending | `REMINDER_STILL_PENDING` |
| Schedule | `REMINDER_SCHEDULE` |
| Cancel | `REMINDER_CANCEL` |

---

### `petcircle_reminder_overdue_v1`
**Sent:** 7+ days past due, repeats monthly

**Body:**
```
Hi {{1}}, a gentle nudge from PetCircle 🐾

{{2}}'s {{3}} is now {{4}} days overdue.

{{5}}

We're here to help you stay on track. Tap below to log it as done, snooze, or reschedule.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Priya |
| `{{2}}` | Bruno |
| `{{3}}` | Rabies Vaccine |
| `{{4}}` | 14 |
| `{{5}}` | Labradors are at higher risk of parvovirus without timely vaccination. A quick vet visit now can prevent serious illness. |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Still Pending | `REMINDER_STILL_PENDING` |
| Schedule | `REMINDER_SCHEDULE` |
| Cancel | `REMINDER_CANCEL` |

---

## Group 2 — Nudges (Category: Marketing)

---

### `petcircle_nudge_va_personal_v1`
**Used for:** Level 0 value-add tips · Level 1 value_add · Level 2 GPT-personalized insights

**Body:**
```
Hi! Here's something worth knowing for {{1}} 🐾

{{2}}

Reply anytime to ask a question about {{3}}'s health.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Bruno |
| `{{2}}` | Labradors are prone to obesity — keeping Bruno's meals measured and walks consistent after age 2 makes a big difference in joint health long-term. |
| `{{3}}` | Bruno |

---

### `petcircle_nudge_engagement_v1`
**Used for:** Level 1 engagement-only messages

**Body:**
```
🐾 A quick note from PetCircle

{{1}}

{{2}}

We are here to help you.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Most pet parents don't realise that dental hygiene is one of the top 3 causes of vet visits in dogs. |
| `{{2}}` | A simple monthly teeth check can catch issues before they become costly. |

---

### `petcircle_nudge_breed_v1`
**Used for:** Level 1 breed-only messages

**Body:**
```
🐾 Did you know this about {{1}}?

{{2}}

PetCircle is here for you.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Labradors |
| `{{2}}` | Labs are one of the most food-motivated breeds, which makes portion control and treat discipline especially important as they age. |

---

### `petcircle_nudge_breed_data_v1`
**Used for:** Level 2 breed + missing health data messages

**Body:**
```
🐾PetCircle has a Health update for {{1}} who is a {{5}}

{{2}}

Health area: {{3}}

{{4}}

We are here to help.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Bruno |
| `{{2}}` | We noticed Bruno doesn't have a deworming record on file. Labs who spend time outdoors should be dewormed every 3 months. |
| `{{3}}` | Deworming |
| `{{4}}` | Tap to log a record or ask us anything. |
| `{{5}}` | Labrador |

---

## Group 3 — Transactional (Category: Utility)

---

### `petcircle_conflict_v1`
**Sent:** When an uploaded document has a date that conflicts with an existing record

**Body:**
```
Hi! We found a date conflict for {{1}}'s {{2}}.

Existing record: {{3}}
Newly uploaded: {{4}}

Which date should we keep? Reply below to choose.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Bruno |
| `{{2}}` | Rabies Vaccine |
| `{{3}}` | 15 Jan 2026 |
| `{{4}}` | 20 Jan 2026 |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Keep Existing | `CONFLICT_KEEP_EXISTING` |
| Use New | `CONFLICT_USE_NEW` |

> **Note:** Buttons are now embedded in the template. No separate interactive message is sent after the template.

---

### `birthday_celebration_v1`
**Sent:** On the pet's birthday each year (Category: Marketing)

**Body:**
```
🎂 Happy Birthday, {{1}}!

Today, {{2}}, is a very special day — wishing your furry companion a year full of good health, great walks, and plenty of treats!

From all of us at PetCircle 🐾
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Bruno |
| `{{2}}` | 26 Mar 2026 |

---

### `order_fulfillment_check_v1`
**Sent:** To the admin phone number when a customer places an order

**Body:**
```
New PetCircle order received!

Customer: {{1}}
Phone: {{2}}
Pet: {{3}}
Category: {{4}}
Items: {{5}}
Order ID: {{6}}

Please process and confirm delivery with the customer.
```

**Sample Variables:**
| Variable | Example |
|----------|---------|
| `{{1}}` | Priya Sharma |
| `{{2}}` | 919876543210 |
| `{{3}}` | Bruno |
| `{{4}}` | Food Order |
| `{{5}}` | Royal Canin Labrador Adult 3kg x 2 |
| `{{6}}` | a3f2c1d0-... |

**Quick Reply Buttons** (add in Meta template builder):
| Button Title | Payload |
|---|---|
| Yes, fulfilled | `ORDER_FULFILL_YES` |
| No, order cancelled | `ORDER_FULFILL_NO` |

---

## Summary Checklist

| Template Name | Category | Variables | Buttons in Meta | Status |
|---|---|---|---|---|
| `petcircle_reminder_t7_v1` | Utility | 4 | 2 (Already Done, Remind Me Later) | ☐ |
| `petcircle_reminder_due_v1` | Utility | 3 | 3 (Done — Log It, Remind Me Later, Order Now) | ☐ |
| `petcircle_reminder_d3_v1` | Utility | 4 | 3 (Still Pending, Schedule, Cancel) | ☐ |
| `petcircle_reminder_overdue_v1` | Utility | 5 | 3 (Still Pending, Schedule, Cancel) | ☐ |
| `petcircle_nudge_va_personal_v1` | Marketing | 3 | None | ☐ |
| `petcircle_nudge_engagement_v1` | Marketing | 2 | None | ☐ |
| `petcircle_nudge_breed_v1` | Marketing | 2 | None | ☐ |
| `petcircle_nudge_breed_data_v1` | Marketing | 5 | None | ☐ |
| `petcircle_conflict_v1` | Utility | 4 | 2 (Keep Existing, Use New) | ☐ |
| `birthday_celebration_v1` | Marketing | 2 | None | ☐ |
| `order_fulfillment_check_v1` | Utility | 6 | 2 (Yes fulfilled, No cancelled) | ☐ |
