import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { naira, payApi, type Today } from './payApi';
import '../visitPlans/plans.css';
import './pay.css';

// "Today's payments" on the vendor dashboard: totals by method, cash waiting for "Cash received"
// (match the 3-letter code on the customer's phone), and the paid list.
export function VendorPaymentsCard({ slug, onChange }: { slug: string; onChange?: () => void }) {
  const [t, setT] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => payApi.today(slug).then(setT).catch(() => null);
  useEffect(() => {
    load();
    const id = window.setInterval(load, 10000);
    return () => window.clearInterval(id);
  }, [slug]);
  if (!t) return null;

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await load();
      onChange?.();
    } catch (err) {
      setError((err as ApiError).message || 'Something went wrong. Try again.');
    }
  };

  if (!t.enabled) {
    return (
      <section className="card-outline vendor-plans" aria-label="Payments">
        <span className="eyebrow">PAYMENTS</span>
        <span>Let customers pay for a plate on their phone (card or transfer, test mode) or pay cash that you confirm. A paid plate counts as a stamp.</span>
        <button type="button" className="btn" onClick={() => act(() => payApi.setEnabled(slug, true))}>Turn on payments</button>
        {error && <span className="error">{error}</span>}
      </section>
    );
  }

  return (
    <section className="card-outline vendor-plans" aria-label="Today's payments">
      <div className="vp-row">
        <div className="vp-block">
          <span className="eyebrow">TODAY'S PAYMENTS</span>
          <span className="vp-big">{naira(t.total)}</span>
          <span className="vp-sub">{t.count} paid plate{t.count === 1 ? '' : 's'}</span>
        </div>
        <div className="vp-block">
          <span className="eyebrow">CARD / TRANSFER</span>
          <span className="vp-big">{naira(t.by_method.paystack)}</span>
          <span className="vp-sub">{t.card_ready ? 'Paystack test mode' : 'Not set up'}</span>
        </div>
        <div className="vp-block">
          <span className="eyebrow">CASH</span>
          <span className="vp-big">{naira(t.by_method.cash)}</span>
          <span className="vp-sub">confirmed by you</span>
        </div>
      </div>
      {t.waiting_cash.length > 0 && (
        <div className="vpay-list" aria-label="Cash waiting">
          <span className="eyebrow">CASH WAITING: MATCH THE CODE</span>
          {t.waiting_cash.map((w) => (
            <div key={w.id} className="vpay-row">
              <strong className="code">{w.code}</strong>
              <span className="grow">{w.name} · {w.item} · {naira(w.amount)}</span>
              <button type="button" className="btn" onClick={() => act(() => payApi.cashReceived(slug, w.id))}>Cash received</button>
              <button type="button" className="link-btn" onClick={() => act(() => payApi.vendorCancel(slug, w.id))}>Cancel</button>
            </div>
          ))}
        </div>
      )}
      {t.paid.length > 0 && (
        <div className="vp-names">
          {t.paid.slice(0, 12).map((p) => (
            <span key={p.id} className="came">{p.method === 'cash' ? '💵' : '💳'} {p.name} · {naira(p.amount)}{p.stamped ? ' · stamped' : ''}</span>
          ))}
        </div>
      )}
      {!t.card_ready && t.card_problem && <span className="note">Card payments: {t.card_problem} Cash works now.</span>}
      {error && <span className="error" role="alert">{error}</span>}
      <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => act(() => payApi.setEnabled(slug, false))}>Turn off payments</button>
    </section>
  );
}
