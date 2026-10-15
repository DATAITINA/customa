import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { Link } from '../../App';
import { naira, payApi, type Payment } from './payApi';
import './pay.css';

// Paystack sends the customer back here (/s/<slug>/paid?reference=...). We ask our server, which
// asks Paystack: the address alone never proves a payment.
export function PaidPage({ slug }: { slug: string }) {
  const reference = new URLSearchParams(window.location.search).get('reference') ?? new URLSearchParams(window.location.search).get('trxref');
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(reference ? null : 'No payment reference in this link.');

  useEffect(() => {
    if (!reference) return;
    payApi.confirm(slug, reference).then((r) => setPayment(r.payment)).catch((err: ApiError) => setError(err.message || 'Could not check the payment.'));
  }, [slug, reference]);

  const p = payment;
  return (
    <main className="phone" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <section className={`pay-card${p?.status === 'paid' ? ' pay-done' : ''}`} aria-live="polite">
        {!p && !error && <strong>Checking your payment with Paystack…</strong>}
        {error && <span className="error" role="alert">{error}</span>}
        {p?.status === 'paid' && (
          <>
            <strong>Paid {naira(p.amount)} for {p.item} ✓</strong>
            <span className="note">{p.stamped ? 'Your stamp is on your card.' : 'This plate is paid. Your card already got a stamp in the last 6 hours.'}</span>
          </>
        )}
        {p?.status === 'pending' && <strong>Paystack hasn't confirmed it yet. Refresh in a moment.</strong>}
        {p && (p.status === 'failed' || p.status === 'cancelled') && <strong>The payment didn't go through. Nothing was charged for this plate.</strong>}
      </section>
      <Link to={`/s/${slug}`} className="btn">Back to my card</Link>
    </main>
  );
}
