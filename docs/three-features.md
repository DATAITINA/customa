# Plate Ajo, Pot Alert, Lunch Crew

Three features that give customers a real reason to come back to a stand. They come from the
product validation (Oct 2026) and are built on the existing stamp card (plates, 6-hour rule, jara).
Each one is off until the vendor turns it on from the dashboard, so a stand that ignores them
works exactly as before.

## 1. Plate Ajo: lock today's price

**Idea.** A customer prepays the vendor for 5 or 10 plates of one menu item at today's menu
price. The money goes straight to the vendor's own bank account by transfer; Customa never holds
money, it only keeps the count. Each visit the customer uses one prepaid plate.

**Problem it solves.** Food prices rise almost monthly (food inflation 20.31% year on year,
July 2026, NBS), so the customer beats price rises; the vendor gets cash up front for the
market run. Prepaid plates are real purchases (the vendor confirmed the transfer), which also
fixes "a plate is a scan, not a purchase".

**Behaviour it encourages.** Coming back to use plates already paid for.

### Acceptance criteria
- The vendor turns Plate Ajo on and enters bank name, account number and account name. Without
  all three, customers do not see it.
- A customer (after their first counted plate) picks a menu item and 5 or 10 plates, sees the
  total at today's price and the vendor's account, sends the transfer outside Customa, then taps
  "I have sent it" with the name on the transfer. The price is taken from the menu on the server,
  never from the client.
- The bundle shows as "waiting for the vendor to confirm" until the vendor confirms or rejects it
  on the dashboard. One pending bundle per customer at a time.
- Once confirmed, the customer sees "N plates left at ₦price". The locked price never changes, even
  if the vendor changes the menu price later.
- At the stand the customer taps "Use 1 prepaid plate". The plate count goes down by one and a
  large confirmation screen shows the item, the time and "plate X of N" for the vendor to see. A
  second use within 60 seconds is refused (double tap protection).
- Using a prepaid plate also counts a stamp toward the jara when the 6-hour rule allows it.
- The vendor dashboard lists pending transfers (confirm or reject), active bundles with plates
  left, and today's prepaid plates served.
- "Delete my data" is refused while the customer still has prepaid plates, with a clear message.
- Everything survives a refresh (stored in the database).

## 2. Pot Alert: "your afang don ready"

**Idea.** A customer taps "Tell me when ___ is ready" for dishes on the menu and leaves a WhatsApp
number. When a pot is ready, the vendor taps the dish on the dashboard; the stand page shows
"Afang is ready now" and the vendor gets a one-tap WhatsApp button for each waiting customer plus
a ready-made message for WhatsApp Status.

**Problem it solves.** Customers walk over and find their soup finished, or never hear that it is
ready. Vendors cook without knowing demand. The old "last plates" banner reached only people
already on the page.

**Behaviour it encourages.** Coming when the food the customer wants is hot.

**Honest limit.** Customa does not send WhatsApp messages by itself (that needs a paid WhatsApp
Business API account). The vendor sends them from their own WhatsApp with one tap per customer.

### Acceptance criteria
- The vendor turns Pot Alert on. When it is off, customers do not see it.
- A customer picks one or more menu dishes and enters a Nigerian phone number (0803..., +234...),
  agreeing that the vendor may message them on WhatsApp. They can change or remove their dishes.
- The vendor dashboard shows how many customers are waiting for each dish.
- The vendor taps "Ready now" on a dish (optionally with plates left). The stand page shows a
  "ready now" banner to everyone for 3 hours or until the vendor ends it.
- After tapping ready, the vendor sees each waiting customer's first name with a WhatsApp button
  that opens a chat with a prefilled message and the stand link, and a "copy for Status" message.
- Phone numbers are visible only to the stand's vendor, never to other customers.
- "Delete my data" removes the customer's dishes and number.

## 3. Lunch Crew: ajo rotation for jara

**Idea.** 3 to 6 people (colleagues, classmates) share one card at a stand. Every member's plate
counts toward the crew card, and each crew jara goes to the next member in line, like an ajo
payout.

**Problem it solves.** One person alone waits six visits for a reward; a crew gets there together
and returns as a ritual. It costs the vendor the same: one jara per six plates.

**Behaviour it encourages.** Coming back with and for each other.

### Acceptance criteria
- The vendor turns Lunch Crew on. When it is off, customers do not see it and nobody's plates go
  to a crew.
- A customer (after their first counted plate) creates a crew with a name and gets an invite link
  to share on WhatsApp. Someone opening the link and counting a plate is offered "Join <crew>".
- Up to 6 members. A customer belongs to at most one crew per stand. Members can leave.
- While in a crew, each member's counted plate adds to the crew card (1 to 6). The 6-hour rule is
  still per person.
- Every 6th crew plate issues a jara to the member whose turn it is (join order, rotating). The
  person who scanned sees whose jara it is; the winner sees their code on their own page.
- A customer's unredeemed jara codes are shown on their stand page, so a code is never lost.
- The vendor dashboard lists crews with members and whose turn is next.
- "Delete my data" removes the customer from their crew.

## Shared rules
- Feature switches and Plate Ajo bank details are per-stand settings (no new columns on old
  tables).
- New tables only; migrations are in `backend/scripts/migrations/2026-10-11_*.sql` and must be run
  on Neon before deploying the backend.
- No fake data or social proof. Every number shown is read from the database.
