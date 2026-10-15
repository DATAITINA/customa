# Pay for a plate (Paystack test mode, or cash)

A customer pays for their plate on their phone, or pays cash and the vendor confirms it. A paid
plate counts as a stamp through the same path as a QR scan (`plates.count_visit`), so the 6-hour
rule, the jara, the Prize Wheel, "Who's here now" and plans all keep working.

## How it works
- **Vendor:** "Turn on payments" on the dashboard (per-stand `PAYMENTS_ENABLED`, stored with
  MSFLib workspace-config). Prices come from the stand's menu, on the server; the customer's
  screen never sets the price.
- **Card or transfer (Paystack):** the customer picks the item and taps "Pay ₦… by card or
  transfer". Our server starts the payment with Paystack and sends the customer to Paystack's
  checkout page. Paystack sends them back to `/s/<stand>/paid`; our server then asks Paystack
  (`/transaction/verify`) and marks the payment paid only for `success`, the exact amount, in NGN.
  The signed webhook (`POST /api/v1/payments/paystack/webhook`) does the same check, so a payment
  is confirmed even if the customer closes the page. It is marked paid once, even if both arrive.
- **Cash:** the customer taps "I'll pay cash" and shows a 3-letter code. The vendor matches the
  code under "Cash waiting" and taps "Cash received". The stamp lands on the customer's card.
- **"Today's payments"** on the dashboard: total, card/transfer, cash, and who paid (first name
  only if given).
- A plate already counted in the last 6 hours is still paid, but gets no second stamp.
- **"Delete my data":** pending payments are deleted; paid ones stay as the vendor's takings, with
  the customer removed.

## Test mode only
Only a Paystack secret key that starts with `sk_test_` is used. A live key (`sk_live_`) is
refused with a clear message, so no real money can move. Without a key, card payments show
"not set up yet" and cash still works.

## Setup
1. Run the migration on Neon before deploying the backend:
   `backend/scripts/migrations/2026-10-18_payments.sql` (new `payment` table; safe to run twice).
2. Paystack dashboard (test mode) > Settings > API Keys & Webhooks:
   - copy the **Test Secret Key**;
   - set the **Test Webhook URL** to `https://customa-api.vercel.app/api/v1/payments/paystack/webhook`.
3. Vercel, project customa-api > Settings > Environment Variables:
   - `PAYSTACK_SECRET_KEY` = your `sk_test_...` key;
   - optional: `PAYSTACK_BASE_URL` (default `https://api.paystack.co`), `PAYSTACK_EMAIL_DOMAIN`.
   - `PUBLIC_WEB_URL` must be the customer site (Paystack returns customers there).
   Redeploy the backend.
4. Paystack test card: `4084 0840 8408 4081`, any future expiry, CVV `408`, PIN `0000`, OTP `123456`.

**Never commit keys.** They live only in Vercel's environment variables (and your local `.env`,
which git ignores).

## Going live later (not built)
Live mode would need each vendor's own Paystack subaccount (split payments), so money goes to the
vendor, not to Customa.

## Code
- `backend/app/models/payments.py`: `Payment` (MSFLib `ModelBase`).
- `backend/app/actions/payments.py`: `PaymentAction` (MSFLib `ModelAction`).
- `backend/app/services/paystack.py`: Paystack client (test keys only, webhook signature).
- `backend/app/services/payments.py`: the rules.
- `backend/app/api/api_v1/endpoints/payments.py`: customer, vendor and webhook routes.
- `frontend/src/features/payments/`: `PayCard`, `PaidPage`, `VendorPaymentsCard`.
- Tests: `backend/app/tests/api/api_v1/test_payments.py` (Paystack replaced by a fake).
