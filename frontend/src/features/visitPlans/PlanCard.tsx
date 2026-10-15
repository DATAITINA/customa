import { useEffect, useState } from 'react';
import type { ApiError, Character as CharacterT } from '../../api';
import { Character } from '../../components/Character';
import { plansApi, type PlanState, type Slot } from './plansApi';
import './plans.css';

// "When you go come back?": after a plate the character asks for a day AND a time (both
// needed). One plan at a time; change or cancel it anytime. A plan, never a booking.
// ask: show the question when there is no plan (the counted screen); otherwise only an
// existing plan shows. missed: the last plan was missed: "No wahala, life happen 😄".
export function PlanCard({ slug, character, ask = false, missed = false }: { slug: string; character?: CharacterT | null; ask?: boolean; missed?: boolean }) {
  const [state, setState] = useState<PlanState | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justMade, setJustMade] = useState(false);

  useEffect(() => { plansApi.state(slug).then(setState).catch(() => setState(null)); }, [slug]);
  if (!state) return null;
  const plan = state.plan;
  if (!plan && !ask) return null;

  const chosenDay = state.options.days.find((d) => d.date === day);
  const save = async () => {
    if (!day || !slot) return;
    setBusy(true);
    setError(null);
    try {
      setState(await plansApi.make(slug, day, slot));
      setEditing(false);
      setJustMade(true);
    } catch (err) {
      setError((err as ApiError).message || 'Could not save your plan. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const cancel = async () => {
    setBusy(true);
    try {
      setState(await plansApi.cancel(slug));
      setJustMade(false);
      setDay(null);
      setSlot(null);
    } catch {
      setError('Could not cancel. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const first = character?.name.split(' ')[0] ?? 'I';
  if (plan && !editing) {
    return (
      <section className="plan-card has-plan" aria-label="Your plan">
        <div className="plan-head">
          <Character body={character?.body} color={character?.color} accessory={character?.accessory} expression="happy" pose={justMade ? 'hop' : 'wave'} size={58} />
          <div className="plan-bubble">{justMade ? plan.confirm : `Your plan: ${plan.when}. I go dey expect you!`}</div>
        </div>
        <span className="plan-label">📅 {plan.label}</span>
        <a className="btn plan-calendar" href={plansApi.calendarUrl(slug)}>Add to my calendar</a>
        <span className="note">
          {plan.reminder === 'push'
            ? `🔔 ${first} go remind you about 1 hour before.`
            : plan.reminder === 'sms'
              ? `📱 ${first} go text you about 1 hour before.`
              : 'Want a reminder? Turn on alerts on your card, or add it to your calendar.'}
          {' '}It's a plan, not a booking. No pressure.
        </span>
        <div className="plan-actions">
          <button type="button" className="link-btn" onClick={() => { setEditing(true); setDay(plan.day); setSlot(plan.slot); }} disabled={busy}>Change plan</button>
          <button type="button" className="link-btn" onClick={cancel} disabled={busy}>Cancel plan</button>
        </div>
        {error && <span className="error">{error}</span>}
      </section>
    );
  }

  return (
    <section className="plan-card" aria-label="Plan your next visit">
      <div className="plan-head">
        <Character body={character?.body} color={character?.color} accessory={character?.accessory} expression="happy" pose="wave" size={58} />
        <div className="plan-bubble">{missed && !plan ? 'No wahala, life happen 😄 ' : ''}When you go come back?</div>
      </div>
      <span className="plan-step">Day</span>
      <div className="plan-days" role="radiogroup" aria-label="Day">
        {state.options.days.map((d) => (
          <button key={d.date} type="button" role="radio" aria-checked={day === d.date} className={day === d.date ? 'on' : undefined}
            onClick={() => { setDay(d.date); if (slot && !d.open.includes(slot)) setSlot(null); }}>
            {d.label}
          </button>
        ))}
      </div>
      <span className="plan-step">Time</span>
      <div className="plan-slots" role="radiogroup" aria-label="Time">
        {state.options.slots.map((s) => {
          const closed = !!chosenDay && !chosenDay.open.includes(s.key);
          return (
            <button key={s.key} type="button" role="radio" aria-checked={slot === s.key} disabled={closed} className={slot === s.key ? 'on' : undefined} onClick={() => setSlot(s.key)}>
              <strong>{s.label}</strong>
              <span>{s.hours}</span>
            </button>
          );
        })}
      </div>
      <button type="button" className="btn" disabled={!day || !slot || busy} onClick={save}>
        {busy ? 'Saving…' : !day || !slot ? 'Pick a day and a time' : 'Make it a plan'}
      </button>
      <span className="note">A plan, not a booking: nobody holds food for you. You can change it anytime.</span>
      {editing && <button type="button" className="link-btn" style={{ alignSelf: 'center' }} onClick={() => setEditing(false)}>Keep my old plan</button>}
      {error && <span className="error" role="alert">{error}</span>}
    </section>
  );
}
