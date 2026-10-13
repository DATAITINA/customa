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
- **iPhone** (iOS 16.4+): web push works only from the Home Screen app. The card shows the three
  steps (Share, Add to Home Screen, open from the Home Screen). iOS shows the title and text with
  the Customa icon; it does not show custom pictures or buttons.
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
`POST /stands/{slug}/last-plates` now returns `alert: {sent, skipped}`; the dashboard has
`alert_subscribers`.
