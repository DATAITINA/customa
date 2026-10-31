# UI refresh (October 2026)

A frontend-only polish pass on Customa: one design system, a clear next step on every
screen, friendly errors, dark mode, larger touch targets, and a few small moments of joy.
No backend, API or MSFLib wiring changed. The audit that led to it is in [AUDIT.md](AUDIT.md).

Before/after for all 37 screens at 360px phone width: [`screens/`](screens)
(`c…` = customer, `v…` = vendor). Dark mode: [dark-mode.jpg](dark-mode.jpg), and the
dark theme before/after its redesign: [dark-before-after.jpg](dark-before-after.jpg).
The stamp landing, frame by frame: [stamp-lands.jpg](stamp-lands.jpg).

## What changed and why

### 1. Design system (`frontend/src/styles.css`, top of file)
- **Tokens for everything:** colour (brand and status), type, space, radius, touch size,
  depth and motion. All feature CSS now uses them; ad-hoc hex colours and radii are gone.
  *Why:* consistency is what makes it look professional.
- **Colour roles:** components ask for a job (`--surface`, `--card`, `--edge`,
  `--btn-bg`, `--select-bg`, …), not a paint colour. In light mode every role is the classic
  ink-and-paper value; dark mode gives each role its own colour (see section 6).
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

### 6. Dark theme: designed, not inverted
The first dark pass simply turned the light theme's black "ink" white, so white was
everywhere: big white buttons, 2px white outlines on every card and input, a glowing white
panda on a maroon block. The redesign follows [Material's dark theme](https://m2.material.io/design/color/dark-theme)
and [Apple's Dark Mode guidance](https://developer.apple.com/design/human-interface-guidelines/dark-mode):
- **Layered warm charcoal, never pure black.** Depth comes from lighter surfaces, not
  shadows: page `#121110` → cards `#1A1816` → controls and bubbles `#26221F`, with sheets
  on an elevated surface (Apple's base/elevated idea).
- **White is rationed.** Text is a soft off-white (13–15:1 instead of a glaring 16–18:1),
  secondary text steps down (6–7:1). Card outlines are quiet greys. Things you tap or type
  into get a stronger grey (3:1, WCAG non-text contrast). Only QR codes and switch knobs
  stay true white, because they need it.
- **Colour carries emphasis instead of white.** Main buttons are a softened pepper with
  dark text (6:1). Chosen chips, tabs and answers get a pepper-tinted fill and pepper edge.
  My chat messages are pepper-tinted.
- **Desaturated brand colours** (Material): pepper and yolk are softened a touch so they
  glow without vibrating; status colours are re-tuned for dark backgrounds.
- **Illustrations adapted** (Apple: soften white in images): the panda and chef hat are a
  warm cream; the character stage is a gentle warm glow; the wheel rim is lifted so it
  doesn't vanish; the chat orb glows pepper, not white; the timer ring fills in pepper.
- **Google button** uses Google's own dark style.
- **Light mode is untouched:** all 37 light screens were re-shot with frozen time and
  motion and pixel-compared with the previous version. They are identical (one screen
  differs by at most 5/255 in a few pixels).

## Performance
Only `transform` and `opacity` are animated. No new dependencies. Main bundle:
JS 83.8 KB gzip (was 82.6), CSS 11.5 KB gzip (was 9.1).

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
