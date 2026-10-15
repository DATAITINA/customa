import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { naira, payApi, type PayState } from './payApi';
import './pay.css';

// "Pay for this plate" on the customer's card: by card/transfer (Paystack, test mode) or cash the
// vendor confirms with a 3-letter code. A paid plate counts as a stamp (6-hour rule still applies).
// Hidden until the vendor turns payments on and the menu has prices.
export function PayCard({ slug, onPaid }: { slug: string; onPaid: () => void }) {
  const [state, setState] = useState<PayState | null>(null);
  const [item, setItem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = () => payApi.state(slug).then(setState).catch(() => setState(null));
  useEffect(() => { load(); }, [slug]);

  // While cash waits for the vendor, check every 5 seconds whether it was received.
  const pending = state?.pending_cash;
  useEffect(() => {
    if (!pending) return;
    const t = window.setInterval(async () => {
      const s = await payApi.state(slug).catch(() => null);
      if (s && !s.pending_cash) {
        setState(s);
        setDone(`Cash received for ${pending.item} ✓`);
        onPaid();
      }
    }, 5000);
    return () => window.clearInterval(t);
  }, [pending?.id]);

  if (!state?.enabled) return null;

  const pay = async (method: 'paystack' | 'cash') => {
    if (!item) return;
    setBusy(true);
    setError(null);
    try {
      const r = await payApi.start(slug, item, method);
      if (r.checkout_url) {
        window.location.href = r.checkout_url;
        return;
      }
      setState({ ...state, pending_cash: r.payment });
    } catch (err) {
      setError((err as ApiError).message || 'Payment could not start. Try again.');
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <section className="pay-card pay-done" aria-label="Paid">
        <strong>{done}</strong>
        <span className="note">Your plate is on your card. Enjoy!</span>
      </section>
    );
  }

  if (pending) {
    return (
      <section className="pay-card" aria-label="Paying cash">
        <span className="eyebrow">SHOW THIS TO THE VENDOR</span>
        <div className="pay-code">{pending.code}</div>
        <strong style={{ textAlign: 'center' }}>{pending.item} · {naira(pending.amount)} cash</strong>
        <span className="note">Pay the vendor. Once they tap "Cash received", your stamp goes on your card.</span>
        <button type="button" className="link-btn" disabled={busy} onClick={async () => {
          await payApi.cancel(slug, pending.id).catch(() => null);
          load();
        }}>Cancel</button>
      </section>
    );
  }

  const price = state.menu.find((m) => m.item === item)?.price;
  return (
    <section className="pay-card" aria-label="Pay for this plate">
      <span className="eyebrow">PAY FOR THIS PLATE</span>
      {state.test_mode && state.card && <span className="pay-test">TEST MODE: no real money</span>}
      <div className="pay-items" role="radiogroup" aria-label="What are you eating?">
        {state.menu.map((m) => (
          <button key={m.item} type="button" role="radio" aria-checked={item === m.item} className={item === m.item ? 'on' : undefined} onClick={() => setItem(m.item)}>
            {m.item} · {naira(m.price)}
          </button>
        ))}
      </div>
      <div className="pay-actions">
        {state.card && (
          <button type="button" className="btn" disabled={!item || busy} onClick={() => pay('paystack')}>
            {busy ? 'Opening Paystack…' : item ? `Pay ${naira(price ?? 0)} by card or transfer` : 'Pick what you are eating'}
          </button>
        )}
        <button type="button" className={state.card ? 'btn btn-outline' : 'btn'} disabled={!item || busy} onClick={() => pay('cash')}>
          I'll pay cash
        </button>
      </div>
      <span className="note">A paid plate counts as a stamp on your card.</span>
      {error && <span className="error" role="alert">{error}</span>}
    </section>
  );
}
