# Customer card recovery: the card follows the customer, not the browser

## The problem
A customer is known by a secret key saved in one browser's storage (`customa:customer:<stand>`,
sent as `X-Customer-Key`). Anything with other storage has no key, so the customer looked new and
their card was empty. That covers:
- another browser;
- an in-app browser (WhatsApp, Instagram, a QR scanner app);
- a private tab;
- the iPhone Home Screen app (separate storage from Safari);
- cleared browser data.

## What the customer sees
- **"💾 Save your card so you never lose it"** opens right after their first plate. It's optional;
  "Not now" closes it, and it stays on the card as a button. They type their phone number and
  pick a 4-digit PIN. Afterwards the card shows only "Card saved to 0803 ••• 4521"
  ("Change" updates the number or PIN).
- **"Already have a card? Get it back"** is at the top of the welcome screen, and on the card screen
  when the browser has no card. They type the number and PIN, and this browser gets its own key for
  the same card: every plate, jara, crew card, plan, prize, payment and chat memory stays. If they
  came from a fresh QR scan, the plate is counted on their real card right away (the 6-hour rule
  still decides).
- **Forgot the PIN:** when the stand can send texts (Termii set up), "Forgot your PIN? Text me a code"
  sends a 6-digit code, valid for 10 minutes and usable once.
- **Customers who never save a card** keep working exactly as before.

## Proof of ownership: why a PIN, plus SMS when available
MSFLib has no OTP, phone-verification or messaging module (checked: msflib-auth and msflib-account
handle vendor email/password logins and password-reset tokens). Customa's SMS (Termii) is off on
most stands because texts cost money, so SMS can't be the only proof. A 4-digit PIN chosen when
linking:
- works everywhere for free, offline from any SMS provider;
- is quick on a cheap Android phone.

When texts are on, the SMS code is a second way in for a forgotten PIN. A vendor-confirms flow
was not chosen: it needs the vendor's attention at a busy moment, and a stranger could stand in
line and claim to be someone.

## Security
- **The number is never stored.** Only a keyed hash (HMAC-SHA256 with `SECRET_KEY` and the stand)
  is kept for lookup, plus a masked form for display.
- **PINs and codes are hashed** with bcrypt (`msflib.core.security.get_password_hash`), after a
  pepper with `SECRET_KEY`, so a copy of the database alone can't be used to try all 10,000 PINs.
  Weak PINs (0000, 1234, 1111...) are refused.
- **Never reveals whether a number has a card.** An unknown number gets:
  - the same answer and status as a wrong PIN;
  - the same timing (a dummy bcrypt check);
  - the same lockouts;
  - the same "a code is on its way" for SMS.
- **Lockout:** 5 wrong tries for a number lock it for 30 minutes, and 15 in 24 hours lock it for the
  day. Each IP is limited to 20 wrong tries an hour across all numbers, so nobody can try one PIN on
  many numbers. SMS codes: at most 3 per number per hour.
- **Every attempt is logged** in `recoveryattempt`: link, PIN, SMS sent, code; ok, wrong, locked,
  limited, taken. It stores only hashes of the number and IP.
- **No takeover:** a number links to one card per stand. Linking someone else's number is refused and
  never moves it. A recovered browser gets a new random key; it never sees another browser's key.
- **Anti-cheat unchanged:**
  - one plate per window per customer, and only with the QR scan code;
  - all browsers of one customer share the window;
  - a browser that counted a plate on a new card, then recovered the real card, still waits out
    the window (`came_from_customer_id`, checked in `plates.count_visit`).
- **Vendor:** a small 💾 next to customers who saved their card. The number is never shown.
- **"Delete my data"** removes the number link, the extra keys and SMS codes, and clears the
  customer from the log.

## Setup
1. Run the migration on Neon before deploying the backend:
   `backend/scripts/migrations/2026-10-19_card_recovery.sql` (new tables only; safe to run twice).
2. `SECRET_KEY` (backend, Vercel) must be set and stay the same. It's already needed for vendor
   logins. Changing it makes saved numbers and PINs unusable; customers would have to save again.
3. Optional, for SMS codes: `TERMII_API_KEY`, `TERMII_SENDER_ID` (`TERMII_BASE_URL`, `TERMII_CHANNEL`),
   the same settings as text alerts; see `docs/scan-and-alerts.md`.
4. Per stand (workspace-config, `CUSTOMA` namespace): `CARD_RECOVERY_ENABLED` (default on).

Never commit keys: they live in Vercel's environment variables and your local `.env`.

## Code
- `backend/app/models/card_recovery.py`: tables (MSFLib `ModelBase`).
- `backend/app/actions/card_recovery.py`: MSFLib `ModelAction`s.
- `backend/app/services/card_recovery.py`: the rules (link, recover, SMS, lockouts, window guard).
- `backend/app/api/api_v1/endpoints/card_recovery.py`: routes:
  - `GET /public/{stand}/card`;
  - `PUT|DELETE /public/{stand}/card/phone`;
  - `POST /public/{stand}/card/recover/code`;
  - `POST /public/{stand}/card/recover`.
- `CustomerAction.get_by_key`: also accepts a recovered browser's key. Every feature works with it
  unchanged, including the Home Screen app start URL.
- `frontend/src/features/cardRecovery/`: `SaveCard`, `RecoverCard`.
- Tests: `backend/app/tests/api/api_v1/test_card_recovery.py`.
