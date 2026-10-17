import { useEffect, useState } from 'react';
import { setCustomerKey, type ApiError, type CustomerState } from '../../api';
import { cardApi, digits } from './cardApi';
import './card.css';

// "Already have a card?" on the welcome screen: the customer types their number and PIN (or a
// code we text them, when the stand can send texts) and this browser gets its own key for
// their card, with every plate, jara, crew card and plan.
export function RecoverCard({ slug, onRecovered }: { slug: string; onRecovered: (c: CustomerState) => void }) {
  const [open, setOpen] = useState(false);
  const [sms, setSms] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [phone, setPhone] = useState('');
  const [pin, setPin] = useState('');
  const [useCode, setUseCode] = useState(false);
  const [code, setCode] = useState('');
  const [codeNote, setCodeNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { cardApi.state(slug).then((s) => { setSms(s.sms); setEnabled(s.enabled); }).catch(() => null); }, [slug]);
  if (!enabled) return null;
  if (!open) {
    return <button type="button" className="link-btn recover-open" onClick={() => setOpen(true)}>Already have a card? Get it back</button>;
  }

  const phoneOk = phone.replace(/\D/g, '').length >= 10;
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError((err as ApiError).message || 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const recover = () => run(async () => {
    const r = await cardApi.recover(slug, phone, useCode ? { code } : { pin });
    setCustomerKey(slug, r.key);
    onRecovered(r.customer);
  });
  const sendCode = () => run(async () => {
    const r = await cardApi.sendCode(slug, phone);
    setUseCode(true);
    setCodeNote(r.message);
  });

  return (
    <section className="save-card" aria-label="Get your card back">
      <h3>Get your card back</h3>
      <span className="note">Use the number and PIN you saved your card with.</span>
      <label className="field">Your phone number
        <input className="input" type="tel" inputMode="tel" autoComplete="tel" placeholder="0803 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      {useCode ? (
        <label className="field">The 6-digit code we texted you
          <input className="input pin-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="••••••" value={code} onChange={(e) => setCode(digits(e.target.value, 6))} />
        </label>
      ) : (
        <label className="field">Your 4-digit PIN
          <input className="input pin-input" type="password" inputMode="numeric" autoComplete="current-password" maxLength={4} placeholder="••••" value={pin} onChange={(e) => setPin(digits(e.target.value, 4))} />
        </label>
      )}
      {codeNote && <span className="note">{codeNote}</span>}
      <button type="button" className="btn" disabled={busy || !phoneOk || (useCode ? code.length !== 6 : pin.length !== 4)} onClick={recover}>
        {busy ? 'Checking…' : 'Get my card back'}
      </button>
      {error && <span className="error" role="alert">{error}</span>}
      {sms && !useCode && <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} disabled={busy || !phoneOk} onClick={sendCode}>Forgot your PIN? Text me a code</button>}
      {useCode && <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => { setUseCode(false); setCode(''); }}>Use my PIN instead</button>}
      <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => { setOpen(false); setError(null); }}>I'm new here</button>
    </section>
  );
}
