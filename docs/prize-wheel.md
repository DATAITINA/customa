# Prize Wheel

On plate 6 the jara becomes a spin on the vendor's wheel of food prizes. The customer spins,
wins one of the vendor's foods, and shows a one-time code; the vendor checks the code and gives
the food.

## How it fits the existing jara
- A jara (plate 6, a surprise jara, a Lunch Crew turn) is still created as before. While the
  vendor's wheel is live, that jara is **one spin**: the plate-6 screen and the card show
  "Spin" instead of a code. With the wheel off, nothing changes (the plain code, a free extra).
- **The server decides.** `POST /public/{slug}/wheel/spin {jara_id}` picks the prize with a
  secure random choice weighted by each prize's chance (often 5, sometimes 3, rarely 1), and where
  in its slice the pointer stops. Slices on the wheel are drawn with the same sizes, so the wheel
  is honest about the odds. The phone only animates the server's result.
- **Once per jara.** The result is stored (`jaraprize`, one row per jara). Asking again, a
  reload or a double tap returns the same result; a used jara cannot spin.
- **The code comes with the prize.** At the spin the jara gets a new code, `JARA-XXXX-XXXX`
  (8 characters without 0/O/1/I, unique at the stand), shown with a QR code. Prizes can be
  collected for `WHEEL_PRIZE_VALID_DAYS` days (default 14).
- **The vendor checks and gives once.** `GET /stands/{slug}/jara/{code}` says `valid`,
  `redeemed`, `expired`, `not_spun`, `other_stand` or `unknown`, with the prize, its photo and
  the customer's first name. Typed codes are forgiving (case, spaces, missing dashes). The
  existing `POST /stands/{slug}/jara/{code}/redeem` marks it given atomically (one of two taps
  wins) and refuses expired prizes, so a screenshot of a used code is worth nothing.

## Vendor
Dashboard → **Prize wheel**: up to 6 prizes, each with a photo (take one with the camera or
choose one; the phone shrinks it), the food's name, what the customer wins, an optional
description, how often it comes up, and "available today". A live preview shows the wheel with
the stand's character in the middle. **Publish** needs at least 2 available prizes; if prizes are
removed or marked finished below that, the wheel pauses by itself. **Check a jara code**: type
the code or scan its QR code (camera scan where the browser has BarcodeDetector, e.g. Chrome on
Android), then "Give prize & mark as used". The jara list shows each code's prize, or that the
customer has not spun yet.

## Customer
`/s/{slug}/wheel`: the wheel with photos, a big SPIN button (sounds made on the phone, with a
mute button, and a little buzz on the win), a celebration and the prize card with code and QR.
Below: prizes to collect and all prizes on the wheel (rare ones marked). The card shows a wheel
teaser while the wheel is live. Reduced-motion settings get a short spin without effects.

## Setup
Run `backend/scripts/migrations/2026-10-15_prize_wheel.sql` on the database before deploying the
backend (new tables `wheelitem`, `jaraprize`; nothing else changes). The wheel is off for every
stand until its vendor publishes one.

Code: `backend/app/services/prize_wheel.py`, `backend/app/api/api_v1/endpoints/prize_wheel.py`,
`frontend/src/features/prizeWheel/`. Tests: `backend/app/tests/api/api_v1/test_prize_wheel.py`.
