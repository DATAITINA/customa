# UI refresh (October 2026)

A frontend-only polish pass on Customa: one design system, a clear next step on every
screen, friendly errors, dark mode, larger touch targets, and a few small moments of joy.
No backend, API or MSFLib wiring changed. The audit that led to it is in [AUDIT.md](AUDIT.md).

Before/after for all 37 screens at 360px phone width: [`screens/`](screens)
(`c…` = customer, `v…` = vendor). Dark mode: [dark-mode.jpg](dark-mode.jpg).
The stamp landing, frame by frame: [stamp-lands.jpg](stamp-lands.jpg).

## What changed and why

### 1. Design system (`frontend/src/styles.css`, top of file)
- **Tokens for everything:** colour (brand and status), type, space, radius, touch size,
  depth and motion. All feature CSS now uses them; ad-hoc hex colours and radii are gone.
  *Why:* consistency is what makes it look professional.
- **Dark mode** (`prefers-color-scheme`): warm charcoal, not black. Character outlines and
  the logo follow the theme so they stay visible; faces stay dark.
- **Text in `rem`**, so the phone's own text-size setting works. Checked at 150%: nothing
  overflows.
- **44px minimum touch targets** for links, chips, swatches, toggles and small vendor buttons
  (several were 33–40px).
- **Contrast for bright sun:** small pepper-coloured text uses a darker accent (AA);
  disabled buttons stay readable instead of fading out.
- **Press feedback:** everything tappable sinks slightly under the thumb.

### 2. Customer card: one clear next step
- **Counted:** card → rewards (spin, codes, pay) → "When you go come back?" → rating → chat
  and play. Everything else sits under a **"More from Bisi"** divider. *Why:* the screen
  was eight equal cards, so nothing said what to do next.
- **Too soon:** the disabled "Wait for the timer" button is gone. A short "See you after
  5h 19m 👋🏾" says when and why.
- **First look without a card:** "How it works" in three steps, so the product's purpose is
  clear on first use.
- **Errors:** wrong link, offline and server failures each get the character, a plain
  explanation and a next step. An offline banner shows before the customer tries to count.
- **Jara:** the "Start my new card" button no longer wraps awkwardly.

### 3. Delight (CSS only, off with `prefers-reduced-motion`)
- **The stamp lands:** the plate just counted drops onto the card with a thump, a ripple
  and a short buzz (a stronger one on jara).
- **One plate away:** the J slot glows and wiggles, the pill says "Jara next! 🔥", and the
  character gets a cheeky line ("Next plate na jara o. No dull yourself 👀").
- The character pops up when a plate is counted; JARA! pops in; rating replies "E sweet!
  Thank you 😋".
- Pages and views fade up softly instead of hard cuts.
- **Prize wheel:** the food confetti now falls *behind* the prize card. Before, it covered
  the code and QR the vendor has to read.

### 4. Vendor dashboard: the two-second answers first
- Today's numbers on top (plates today leads; pairs on phones, one row on desktop), then
  who's here now, jara to give out next to "check a code", then leftovers.
- Setup panels (wheel, customize, delights, ajo, crew) sit under "Set up your stand".
- Real empty states ("No jara waiting. When a customer earns one, their code shows here.")
  and retry on load errors.

### 5. Chat, Play, Wheel, sign-in
- The same **"← My card"** back pill on every inner page.
- Friendly load errors with "Try again".
- Vendor sign-in says what the dashboard is for, has Show/Hide password, and gives
  plain-language errors with a next step.

## Performance
Only `transform` and `opacity` are animated. No new dependencies. Main bundle:
JS 83.8 KB gzip (was 82.6), CSS 10.9 KB gzip (was 9.1).

## How it was checked
- `tsc` typecheck and `vite build` pass. The repo has no automated test suite.
- All 37 screens walked in Chromium (Playwright) at 360px against a mocked API, in light
  and dark mode and at 150% text size, plus the dashboard at desktop width. No page errors.
- The sandbox could not install the private `@msflib/*` packages (GitHub Packages needs
  `NPM_TOKEN`), so local runs used small stand-ins for `@msflib/core` and
  `@msflib/react-auth`. Those stand-ins are not in the repo, and the app's MSFLib wiring is
  unchanged. Run `pnpm build` with your token (or in CI) for the final check.

## Files the card-recovery work also touches
`WelcomeForm`, `DeleteMyData` and `api.ts` are byte-for-byte unchanged.
`CustomerPage.tsx` changed in its layout code (view order, `Shell`, `PlateCard`, `TooSoon`,
new `ErrorScreen` / `MoreFrom` / `HowItWorks`). Merges should only meet in those blocks.
