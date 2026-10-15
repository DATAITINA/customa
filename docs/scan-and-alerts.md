# Real scans only, and leftover-food alerts

## A plate counts only after a real QR scan

The stand's QR code carries a secret scan code (`/s/{slug}?s=...`). The count routes
(`POST /public/{slug}/visits` and using a prepaid Plate Ajo plate) refuse anything without the
current code (403, `code: scan_required`).

- Opening the stand page from a bookmark, the browser history, a shared link or a refresh shows
  the card and a "Scan the QR code at the stand" hint, but counts nothing.
- The phone reads the code once, removes it from the address bar (so a refresh can't count
  again) and keeps it for this browser tab for 30 minutes, for a prepaid plate during the visit.
- The code is derived from the server secret and the stand (`services/qr.py`), nothing stored.
  Only stand members can read it (`GET /stands/{slug}/qr`, used by the QR page).
- "Someone copied your QR code? Make a new one" (`POST /stands/{slug}/qr/new`) bumps
  `QR_VERSION`: every older print stops counting. Reprint after this.
- The demo stand's code is public (`demo_scan` in the stand view) so it can be shown without a
  printed QR ("Pretend I scanned the QR (demo)").

**Existing printed QR codes stop counting after this deploy.** Print or show the new one from
the dashboard ("Show QR code").

Known limit: a photo of the printed QR still works from home. "Make a new one" is the answer
today; a QR that changes every few minutes on the vendor's screen would close it fully.

## Leftover-food alerts (web push)

When the vendor taps "Tell my customers", every phone that turned on that stand's alerts gets a
notification in the character's voice: "Ekaette: last plates tonight! 🍲 — Only 8 plates left
at Mama Ekaette's Kitchen. Come chop before 8:30 PM 🏃🏾".

- **Android** (Chrome, Edge, Firefox, Samsung Internet): the character's picture as the icon, a
  wide "LAST PLATES TONIGHT!" banner with the character, and two buttons: "I'm coming 🏃🏾"
  (opens the stand page) and "Not today".
- **iPhone**: Safari has no web push outside a Home Screen app, so iPhones get **text messages**
  instead (below). The card no longer shows Home Screen steps. A Home Screen app that already
  turned on push keeps getting it.
- The pictures are drawn on the phone from the same SVG character when alerts are turned on,
  and kept in IndexedDB for the service worker (`frontend/public/sw.js`).
- At most one alert per stand per hour (`ALERT_GAP_MINUTES`), so no spam; ending the
  announcement sends nothing. Alerts expire when the announcement ends (push TTL).
- Only real push services are accepted as endpoints (FCM, Mozilla, Apple, Windows), so the
  server never posts to other URLs. Phones that unsubscribed (404/410) are removed.
- Delete-my-data removes the customer's alert subscriptions.

### Setup
1. `python scripts/generate_vapid_keys.py`, then add `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`
   to the backend environment (Vercel) and redeploy. Without them, alerts are not offered.
2. Run `scripts/migrations/2026-10-13_push_alerts.sql` on the database before deploying.

Routes: `GET/POST /public/{slug}/alerts`, `POST /public/{slug}/alerts/off`. The vendor's
`POST /stands/{slug}/last-plates` returns `alert: {sent, texts, skipped}` (`sent` counts phones
reached by push or text, `texts` those reached by text); the dashboard's `alert_subscribers`
counts push phones plus text numbers.

## Leftover-food alerts by text message (SMS, any phone)

Texts reach every phone, iPhone and Android, with no app and no notification settings. They go
out through [Termii](https://termii.com) with the same "Tell my customers" tap and the same
once-an-hour limit as push.

- The customer types their number (Nigerian mobile: `0803 123 4567`, `+234 803…`) and ticks
  "I agree" to the terms shown in full (`TERMS` in `backend/app/services/sms_alerts.py`). The
  server stores the number, when they agreed and which wording (`terms_version`). "Text me" stays
  disabled until they agree; the server also refuses without `agree: true`.
- The vendor sees only how many phones get alerts, never the numbers. One number per card and
  per stand (the same number on a new card moves there, so nobody gets two texts). At most
  `SMS_MAX_SUBSCRIBERS` numbers per stand (default 300), because each text costs money.
- The text is one plain SMS page (≤ 160 characters, no emoji, which would cost more):
  `Ekaette at Mama Ekaette's Kitchen: last plates tonight! Only 10 plates left. Come before
  8:30 PM. customa-web.vercel.app/s/mama-ekaettes-kitchen`
- "Stop texts" on the card, and delete-my-data, remove the number.
- Where the browser supports push (Android Chrome and others), the card also offers free phone
  pings as a smaller option.

### Setup
1. On the Termii dashboard: get the API key, your account's base URL, and register a sender ID
   (for example `Customa`; approval can take a few days). Fund the wallet.
2. Backend environment (Vercel): `TERMII_API_KEY`, `TERMII_SENDER_ID`, and if different from the
   defaults `TERMII_BASE_URL` (default `https://api.ng.termii.com`) and `TERMII_CHANNEL` (default
   `dnd`, which also reaches numbers on Do-Not-Disturb). Without the key and sender ID, texts are
   not offered.
3. Run `scripts/migrations/2026-10-14_sms_alerts.sql` on the database before deploying.

Routes: `POST /public/{slug}/alerts/sms` `{phone, agree: true}` → `{texting: "0803 ••• 4567"}`,
`POST /public/{slug}/alerts/sms/off`; `GET /public/{slug}/alerts` adds `sms`, `sms_terms` and
`texting` (with the customer's key).
