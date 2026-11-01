# Return-visit boosters: head-start card, "Ime don land!", "When you go come back?"

Three small features that make the next visit more likely. They come from research on loyalty
cards, being remembered, and making plans. Each is built on the existing stamp card (plates,
6-hour rule, jara) and none changes the jara rules. They were built in this order: Feature 2,
then 1, then 3.

## Feature 2: Head-start card

**Idea.** Every new card starts with 2 gift stamps, so it reads (real plates + 2) / (6 + 2).
The jara still comes after 6 real plates.

**Why.** In a car-wash study, 34% of customers finished a card that started with 2 free stamps,
against 19% on an empty card, with the same number of purchases needed (Nunes & Drèze, "The
Endowed Progress Effect", Journal of Consumer Research, 2006). It works best when people get a
reason, so the gift is labelled: "Welcome gift: 2 stamps on us 🎁".

**Behaviour it encourages.** Finishing the card: it feels already started.

### Acceptance criteria
- New per-stand setting `HEAD_START_STAMPS: int = 2` (0 turns it off; the stand view sends it,
  clamped to 0–10). On by default: it costs the vendor nothing.
- Display only: the jara logic and the 6-hour rule are unchanged (tested: the jara still comes
  on the 6th real plate).
- The own card shows `PLATE (real + 2)/(6 + 2)` with 8 stamps: the 2 gift stamps in Blush with a
  dashed Pepper ring and a 🎁, real plates in Pepper, the last stamp marked J. Under it: "Welcome
  gift: 2 stamps on us 🎁". "Free extra on plate 8".
- Every new card gets it, including right after each jara (the card goes back to 2/8).
- Updated everywhere the customer sees their card count: the plate card (landing page, counted
  screen, "NEXT PLATE" wait screen), the first-plate screen ("Your card starts at 2 of 8"), the
  counted-plate bubbles, the jara screen ("8 OF 8 PLATES", "Done, start my new card"), the surprise
  jara line, the Plate Ajo stamp line, the delete sheet, and the Prize Wheel's "plate N" texts.
  `LastPlates.tsx` shows leftover food ("Only 12 plates left tonight"), not the card, so it is
  unchanged.
- "Just ONE more plate!" (and the "1 more! 🔥" pill) still fires on real plate 5, shown as 7/8.
- Lunch Crew cards are unchanged (no gift stamps). The vendor dashboard keeps real plates.

## Feature 1: "Ime don land!" (regular-arrived alert for staff)

**Idea.** When a customer's plate is counted, the vendor dashboard shows them at the top in a
live "Who's here now" card, so staff can greet regulars by name, in person.

**Why.** In Toast's 2026 survey of US diners, 48% valued being remembered by staff, against 22%
who preferred points. Being greeted by name is the warmest reward a stand can give, and it is
free.

**Behaviour it encourages.** Coming back to the place where people know you.

### Acceptance criteria
- Every counted plate (QR scan or "Use 1 prepaid plate", one path: `plates.count_visit`) records
  an Arrival: the customer's nth plate at the stand and when they last came.
- "Who's here now" (at the top of the dashboard, refreshed every 10 seconds) lists customers counted
  in the last `ARRIVAL_WINDOW_MINUTES` (90), newest first, one entry per customer:
  - first name, or "A regular" when no name was given;
  - "9th visit", or "New face: first plate 👋" for a first-timer;
  - when they last came ("3 days ago");
  - jara status: "next plate is jara!" or "has a jara code";
  - a greeting in the stand's voice, e.g. "Ime! Welcome back o! 🙌" ("Our regular!" from the 5th
    visit);
  - their usual, only if the customer chose to share it.
- "Greeted ✓" saves `greeted_at`, so greeting can be measured.
- Optional phone ping, "Ping me when regulars arrive": web push (the existing VAPID keys and
  `public/sw.js`) to the vendor's phones that turned it on. Only for returning customers, at most
  once per visit (`pinged_at`). The dashboard card works without it. No SMS.
- "Their usual" is never taken from the chat or ChatMemory. The customer turns on "Let <stand>
  know my usual" (off by default) and picks a menu item; only then does it show to staff.
  Turning it off, or "Delete my data", removes it.
- Privacy: staff see a first name only if the customer gave it, never a phone number, never the
  chat.
- "Delete my data" removes the customer's arrivals and usual.

## Feature 3: "When you go come back?" (plan the next visit)

**Idea.** After a plate is counted, the character asks when the customer will come back: a day
and a time, both required. The customer gets a calendar entry and a reminder, and the vendor sees
who plans to come today.

**Why.** People who wrote down a date AND a time for a flu shot were more likely to get it
(Milkman, Beshears, Choi, Laibson & Madrian, PNAS 2011). For the vendor, knowing who is coming
helps cook the right amount: leftover food is their real problem.

**Behaviour it encourages.** Following through on a concrete plan.

### Acceptance criteria
- After a counted plate: "When you go come back?" with day chips (Today, Tomorrow, then the next 6
  days as "Thu 16") and time chips (Morning 7–11am, Lunch 11am–3pm, Evening 3–9pm, Nigeria time).
  A time already over today is not offered. Both are required ("Make it a plan" stays disabled).
- One active plan per customer per stand; the customer can change or cancel it.
- Confirmation in the character's voice: "Deal! I go dey expect you Thursday for lunch 🙌". It is
  a plan, never a reservation: the screens say "A plan, not a booking" and never say the vendor is
  holding food.
- "Add to my calendar": an `.ics` file (free, works on iPhone and Android) with a 1-hour alarm.
- A reminder about 1 hour before the time slot: by web push if the customer turned alerts on at
  this stand; by SMS only if they already agreed to texts there and the stand turned on
  `PLAN_SMS_REMINDERS` (default off, because texts cost money). SMS: plain text, ≤ 160 characters,
  no emoji.
- The scheduler: `GET /api/v1/cron/plan-reminders` with `Authorization: Bearer <CRON_SECRET>`
  (refused without the secret). It claims each reminder by setting `reminder_sent_at` before
  sending, so a reminder never goes twice, even if two runs overlap. It also marks plans whose slot
  is over as missed. It runs every 15 minutes from GitHub Actions
  (`.github/workflows/plan-reminders.yml`), because Vercel's Hobby plan only allows daily cron
  jobs; on a Vercel Pro plan the same endpoint can be a Vercel Cron instead.
- A plate counted during the planned day and slot (30 minutes' grace either side) keeps the plan:
  "You keep your word! 🙌". A missed plan is never a guilt trip: next visit, "No wahala, life
  happen 😄", and a new plan is offered.
- Vendor dashboard: "Coming today: 7 (lunch 4 · evening 3)" with first names where given (✓ once
  they came), and "Plans kept this week: 5 of 8" (plans in the last 7 days whose time is over).
- "Delete my data" removes the customer's plans.

## Measuring
- The dashboard shows one number: **% of customers who came back within 14 days**, from real
  visits only. A customer counts once their first plate at the stand is 14 days old; they came back
  if they had another plate within 14 days of the first. Until anyone is 14 days in, it shows "–".
- Before/after: the API also returns weekly cohorts (customers by the week of their first plate,
  and how many came back within 14 days), and every new row is timestamped (arrivals with
  `greeted_at`, plans with their outcome), so the weeks before and after these features went live
  can be compared. Write the deploy date here when the backend goes live: ______.

## Shared rules
- Per-stand settings in `CustomaSettings`: `HEAD_START_STAMPS`, `ARRIVAL_WINDOW_MINUTES`,
  `PLAN_SMS_REMINDERS`. App setting: `CRON_SECRET`.
- New tables only, no new columns on old tables. Migrations (run on Neon before deploying the
  backend, in order; each is safe to run twice):
  - `backend/scripts/migrations/2026-10-16_regulars.sql`: `arrival`, `customerusual`,
    `vendorpushsubscription`;
  - `backend/scripts/migrations/2026-10-17_visit_plans.sql`: `visitplan`.
  - Feature 2 needs no migration.
- No fake data or social proof: every number shown is read from the database.
- Code: `backend/app/services/{regulars,visit_plans,insights}.py`,
  `backend/app/api/api_v1/endpoints/{regulars,visit_plans}.py`,
  `frontend/src/features/{regulars,visitPlans}/`; the head-start card is in
  `frontend/src/pages/CustomerPage.tsx` (`PlateCard`, `giftStamps` in `api.ts`).
  Tests: `backend/app/tests/api/api_v1/test_{regulars,visit_plans}.py` and
  `test_stand_experience.py::test_head_start_card_is_display_only`.

## Setup
1. Run the two migrations above on Neon.
2. Backend environment (Vercel, customa-api): `CRON_SECRET` (a long random string). Redeploy.
3. GitHub repository secrets: `CUSTOMA_API_URL` (`https://customa-api.vercel.app/api/v1`) and
   `CRON_SECRET` (the same value). GitHub runs the schedule from the default branch, so reminders
   start once this is merged there.
4. Optional, per stand: `PLAN_SMS_REMINDERS` (needs Termii, see docs/scan-and-alerts.md).
