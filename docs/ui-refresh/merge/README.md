# Merging the UI refresh into `build`

The UI refresh (`claude/amazing-keller-vgy01k`, Oct 16-17) was merged into a branch from `build`
(`merge-ui-refresh`). `build` had moved on since then: card recovery, Google sign-in, payments,
MSFLib depth, the theme switch and more. Every feature from both sides is kept, and all of it is
styled with the refresh's design system.

**Before** = `build` today. **After** = the merge. Screens are at 360 px (a small Android phone).

- `customer-before-after.jpg`: welcome, plate counted, jara, prize wheel, card, chat.
- `vendor-and-more-before-after.jpg`: card recovery, games, delete my data, vendor sign-in (email
  and Google), stand setup, dashboard, QR page.
- `dashboard-dark-full.jpg`: the whole vendor dashboard in dark mode, with the new order.

## One design system, one dark theme
Both branches had built a dark theme. The refresh's tokens are the base: colour roles, rem type,
4px spacing, 44px touch targets and press states. Its dark palette is applied through
`data-theme`, so `build`'s **Light / System / Dark** switch (bottom of every page, and the
vendor header) drives it. `index.html` still sets the theme before the first paint.

## Kept from `build`, restyled in the new tokens
- **Buttons:** no underlined links; `.link-btn` is a quiet pill, now 44px tall.
- **Card recovery:** "Already have a card?" and "Save your card".
- **Payments:** Pay for this plate, and "Today's payments" on the dashboard.
- **Dashboard:** "Ask about your stand" (the MSFLib ai-api helper) and the menu with a price box
  per food.
- **Theme:** the theme switch and the round theme button in the vendor header.

## Fixed while checking the merge
- **Error 500 on an early scan:** a customer with a won prize who scanned again inside the 6 hours
  got a server error instead of "see you later". This was already on `build`; the fix comes with a
  test.
- **Pop-ups pinned to the page:** the refresh's page transition left a transform behind, so the
  "Delete my data" sheet and other overlays were placed against the page instead of the screen.
  With the theme switch below the page, this showed up. Fixed with `animation-fill-mode:
  backwards`.
- **Plain words for vendors:** the payments card no longer shows an environment variable name to
  vendors.
