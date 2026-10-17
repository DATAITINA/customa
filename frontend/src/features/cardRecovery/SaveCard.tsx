import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { cardApi, digits, type CardState } from './cardApi';
import './card.css';

// "Save your card so you never lose it": link the card to a phone number + a 4-digit PIN, so it
// can come back in any browser (another browser, WhatsApp, the Home Screen app). Optional.
// Once saved it shows only the masked number: 0803 ••• 4521.
export function SaveCard({ slug, offer = false }: { slug: string; offer?: boolean }) {
  const [state, setState] = useState<CardState | null>(null);
  const [open, setOpen] = useState(offer);
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  useEffect(() => { cardApi.state(slug).then(setState).catch(() => setState(null)); }, [slug]);
  if (!state?.enabled) return null;

  if (state.linked && !open) {
    return (
      <section className="save-card saved" aria-label="Your card is saved">
        <span className="grow">{justSaved ? 'Saved! ' : ''}💾 Card saved to {state.masked}</span>
        <button type="button" className="link-btn" onClick={() => { setOpen(true); setError(null); }}>Change</button>
      </section>
    );
  }

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      setState(await cardApi.link(slug, phone, pin));
      setOpen(false);
      setJustSaved(true);
      setPin('');
    } catch (err) {
      setError((err as ApiError).message || 'Could not save your card. Try again.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="btn btn-outline" onClick={() => setOpen(true)}>💾 Save your card so you never lose it</button>
    );
  }

  return (
    <section className="save-card" aria-label="Save your card">
      <h3>💾 Save your card so you never lose it</h3>
      <span className="note">New phone, another browser, or opened from WhatsApp? Your number and PIN bring your plates back.</span>
      <label className="field">Your phone number
        <input className="input" type="tel" inputMode="tel" autoComplete="tel" placeholder="0803 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      <label className="field">Pick a 4-digit PIN (only you know it)
        <input className="input pin-input" type="password" inputMode="numeric" autoComplete="new-password" maxLength={4} placeholder="••••" value={pin} onChange={(e) => setPin(digits(e.target.value, 4))} />
      </label>
      <button type="button" className="btn" disabled={busy || phone.replace(/\D/g, '').length < 10 || pin.length !== 4} onClick={save}>
        {busy ? 'Saving…' : 'Save my card'}
      </button>
      <span className="note">We keep your number locked away: the stand never sees it.</span>
      {error && <span className="error" role="alert">{error}</span>}
      <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => { setOpen(false); setError(null); }}>{state.linked ? 'Keep it as it is' : 'Not now'}</button>
    </section>
  );
}
