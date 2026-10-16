# Customa UI audit (before the refresh)

Walked 37 screens at 360px (and the vendor dashboard at desktop) against a mocked API:
first scan, welcome, counted, almost there, jara (spin / code / surprise), too soon, back
without a scan, stale QR, crew card, last-plates banner + photo, delete sheet, deleted,
404, offline, slow load, chat (open / reply / closed / no plate), games, prize wheel
(ready / won / waiting), vendor sign-in / create account / error, stand setup, dashboard
(full / empty), customize, QR sign, QR denied, Google return error.

## Already great: keep it

- **The characters.** Pure-SVG, cheap to render, blink/float/wave, tap reactions with hearts,
  eyes that follow your finger. This is the soul of the product.
- **The voice.** "Plate 5 don land", "You don try, Ada!", "No wahala, life happen 😄". Warm,
  local, never cringe.
- **Head-start stamps card.** The gift stamps + pepper stamps + "J" slot reads instantly.
- **Jara moment** and the **prize wheel** (server-picked, ticks, sound, haptics).
- **Bold, consistent brand:** Lilita One display + Figtree, ink/blush/pepper, thick ink borders.
- Already respects `prefers-reduced-motion`, lazy-loads every secondary route, uses skeletons
  on the vendor dashboard, and the delete sheet is calm and honest.

## Confusing

1. **No single next step after a plate is counted.** The counted screen is ~4,600px tall with
   eight equal-weight bordered cards (plan, wheel, alerts, usual, crew, talk/play, rate, menu).
   A first-time customer can't tell what matters.
2. **"Wait for the timer"** is a full-width *disabled* primary button. A dead button as the
   main action reads as "broken". The ring timer above already says it.
3. **Vendor dashboard order.** On a phone it is ~10,000px tall. The two-second questions
   ("how many plates today?", "any jara to give out?") sit below the Who's-here, Plans and
   Payments cards; five stat tiles stack one per row; "Jara to give out" and "Check a code"
   are ~4 screens down.
4. **Errors are dead ends.** Offline shows red "Network error" + Try again on a blank page;
   a wrong stand link shows "This stand does not exist." with a pointless "Try again".
5. **Home Screen install is invisible.** It works (per-stand manifest) but nothing tells a
   customer they can do it.

## Inconsistent

- Radii: 14 / 16 / 18 / 20 / 22 / 24 / 28 px used ad hoc. Button heights: 38 / 40 / 44 / 52 / 56 / 64.
- Many hard-coded colours outside tokens (`#B3261E`, `#C2321A`, `#1E7B34`, `#1F8A4C`, `#FFC926`…),
  lots of inline `style={{ fontSize: … }}`.
- "Back" is a small underlined text link on Chat / Play / Wheel; elsewhere actions are pills.
- Eyebrow labels mix ALL-CAPS strings in code with sentence case.

## Feels flat

- Counting a plate has no "stamp lands" moment: the new stamp is just there.
- One plate away gets a pulsing pill, but no line from the character that feels special.
- Pressing buttons gives no visual feedback (no press state on `.btn`).
- Page changes are hard cuts.

## Accessibility and performance findings

- **Touch targets under 44px:** `.link-btn` (~33px, incl. "Delete my data", Back, "Change plan"),
  chat quick replies, `.seg` / accessory pills, swatches, `.signout`, vendor small buttons (38px).
- **Contrast:** pepper `#F04E30` text on white/blush (gift note, prize "what") is ~3.4:1 at
  13–15px: fails AA. Disabled buttons at 55% opacity are unreadable in sun.
- **Large system font:** every size is fixed `px`, so Android/Chrome's font-size setting is ignored.
- **No dark mode** at all (white page at night on a phone at full brightness).
- **Prize reveal:** the falling food confetti draws *over* the code and QR, so it hides the information.
- Jara "Done, start my new card (2 stamps on us 🎁)" wraps to an awkward second line at 360px.
- Bundle is healthy (main JS 82 KB gz, CSS 9 KB gz). No new libraries needed.
