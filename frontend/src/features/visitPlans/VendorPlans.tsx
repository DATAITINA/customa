import type { Dashboard } from '../../api';
import type { Slot } from './plansApi';
import './plans.css';

const SLOT_WORD: Record<Slot, string> = { morning: 'morning', lunch: 'lunch', evening: 'evening' };

// Plan the next visit, vendor side: who plans to come today (to cook the right amount), plans
// kept this week, and the one measure: % of customers who came back within 14 days.
export function VendorPlansCard({ d }: { d: Dashboard }) {
  const plans = d.plans;
  const back = d.return_14d;
  if (!plans) return null;
  const { coming_today: coming, kept_week: kept } = plans;
  const slots = (Object.keys(SLOT_WORD) as Slot[]).filter((s) => coming.by_slot[s] > 0);

  return (
    <section className="card-outline vendor-plans" aria-label="Plans and come-backs">
      <div className="vp-row">
        <div className="vp-block">
          <span className="eyebrow">COMING TODAY</span>
          <span className="vp-big">{coming.total}</span>
          <span className="vp-sub">{slots.length ? slots.map((s) => `${SLOT_WORD[s]} ${coming.by_slot[s]}`).join(' · ') : 'No plans for today yet'}</span>
        </div>
        <div className="vp-block">
          <span className="eyebrow">PLANS KEPT THIS WEEK</span>
          <span className="vp-big">{kept.total ? `${kept.kept} of ${kept.total}` : '–'}</span>
          <span className="vp-sub">{kept.total ? 'customers who came when they said' : 'Shows once plans are due'}</span>
        </div>
        <div className="vp-block">
          <span className="eyebrow">BACK WITHIN 14 DAYS</span>
          <span className="vp-big">{back?.percent == null ? '–' : `${back.percent}%`}</span>
          <span className="vp-sub">{back?.customers ? `${back.returned} of ${back.customers} customers` : 'Shows once customers are 14 days in'}</span>
        </div>
      </div>
      {coming.names.length > 0 && (
        <div className="vp-names">
          {coming.names.map((n, i) => (
            <span key={i} className={n.came ? 'came' : undefined}>{n.came ? '✓ ' : ''}{n.name} · {SLOT_WORD[n.slot]}</span>
          ))}
        </div>
      )}
      <span className="note">Plans help you cook the right amount. They are plans, not bookings: nobody asked you to hold food.</span>
    </section>
  );
}
