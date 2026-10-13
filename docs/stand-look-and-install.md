# Stand look, install and polish (Oct 2026)

## Home Screen app keeps the customer's card
- On iPhone, an app added to the Home Screen has its own storage, apart from Safari, so it did
  not know the customer and opened the homepage.
- Each stand page now points "Add to Home Screen" at a manifest for that stand
  (`/m/{slug}?k={customer key}`, rewritten by `frontend/vercel.json` to the API's
  `GET /public/{slug}/manifest`). The installed app starts at `/s/{slug}?app=1&k=...`; the page
  stores the key on first launch (never replacing one) and removes it from the address bar.
- An app opened at `/` (or the old start URL `/?app=1`) goes straight to the last stand.
- Customers who installed before this change: remove the icon and add it again from the stand page.

## Demo stand removed
The "Try the demo stand" button, the demo seed (`app/seed/demo.py`), the demo login settings and
all demo wording are gone. The demo stand's data in the database is left as it is.

## Characters
Animal friends join the food friends: **panda**, chick, bunny and cat (plus pepper, pot, cup,
blob). Same style: flat colour, ink lines, dot eyes, rosy cheeks. The panda is always black and
white. Vendors pick from picture tiles. Migration: `2026-10-14_animal_characters.sql` (adds enum
values only).

## Living characters
- Idle float, blink and wave are SVG animations (no JavaScript per frame).
- Tap the character: it boings, smiles and sends up a few hearts; on the customer page it also
  says a short playful line.
- Its eyes follow the finger or mouse (one transform per frame, no re-render).
- While the AI thinks, the chat character glows softly and typing dots bounce.
- Everything respects "reduce motion".

## Stand photo
Vendors snap or upload a photo when they set up the stand, or later under "Customize your stand".
The phone shrinks it (about 1280 px JPEG) before upload. Customers see it at the top of the stand
page. `PUT/DELETE /stands/{slug}/photo`, `GET /public/{slug}/photo?v=N` (versioned, cached for a
year). Migration: `2026-10-14_stand_photo.sql`.

## Loading, delete, games, speed
- Loading: a little character at work with kind words, and skeletons shaped like the dashboard
  and panels, instead of "Loading…".
- Delete my data: a bottom sheet that lists exactly what goes, warns it cannot be undone, and
  needs "I understand" ticked before the red button works.
- Games (`/s/{slug}/play`, no AI, nothing sent to the server): "Catch the jara" (20 seconds,
  dodge the pepper) and "Which one cost pass?" (the stand's real menu prices).
- Speed: chat, vendor, QR and games pages load only when opened; the service worker keeps the
  app's files on the phone (pages still come from the network first); hashed files are cached
  for a year; the stand view says which optional cards are on, so switched-off features are not
  asked; vendor polling is gentler (dashboard 10 s, Plate Ajo 15 s, Lunch Crew 30 s).
