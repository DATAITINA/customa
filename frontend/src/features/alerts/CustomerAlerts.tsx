import { useEffect, useState } from 'react';
import type { ApiError, StandPublic } from '../../api';
import { Character } from '../../components/Character';
import { alertsApi, alertsOnHere, keyBytes, pushSupport, rememberAlerts, type AlertsInfo } from './alertsApi';
import { drawAlertArt, saveAlertArt } from './characterArt';
import './alerts.css';

type Phase = 'idle' | 'busy' | 'on' | 'denied' | 'error';

// "Tell me when food is almost finished": the stand character's leftover-food alerts.
// Text messages work on every phone (iPhone and Android, no app); push notifications are a free
// extra in browsers that support them. Hidden until the server offers alerts and the customer
// has a card at this stand.
export function AlertsCard({ slug, stand }: { slug: string; stand: StandPublic }) {
  const [info, setInfo] = useState<AlertsInfo | null>(null);
  const [phase, setPhase] = useState<Phase>(() => (alertsOnHere(slug) ? 'on' : 'idle'));
  const support = pushSupport();
  const ch = stand.character;
  const first = ch?.name.split(' ')[0] ?? 'We';
  const standName = stand.stand.name;

  const offered = stand.features?.alerts ?? true;
  useEffect(() => {
    if (!offered) return;
    alertsApi.info(slug).then(setInfo).catch(() => setInfo(null));
  }, [slug, offered]);

  // Alerts on: redraw the character's picture now and then, in case the vendor changed it.
  useEffect(() => {
    if (phase !== 'on') return;
    drawAlertArt(ch, standName).then((art) => saveAlertArt(slug, art)).catch(() => undefined);
  }, [phase, slug, ch, standName]);

  const pushOffered = !!info?.available && !!info.public_key && support === 'ok';
  if (!info) return null;

  const turnOn = async () => {
    setPhase('busy');
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setPhase('denied');
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(info.public_key!) }));
      await alertsApi.turnOn(slug, sub.toJSON());
      rememberAlerts(slug, true);
      let art = null;
      try {
        art = await drawAlertArt(ch, standName);
        await saveAlertArt(slug, art);
      } catch {
        // The alert still works with the Customa icon.
      }
      setPhase('on');
      // A first, friendly alert so the customer sees what they will get.
      try {
        await reg.showNotification(`${first}: alerts are on! 🔔`, {
          body: `I go tell you when food is almost finished at ${standName}. No spam, promise 🤞🏾`,
          icon: art?.icon ?? '/icons/icon-192.png',
          badge: '/icons/badge-96.png',
          tag: `alerts-on-${slug}`,
          data: { url: `/s/${slug}` },
        } as NotificationOptions);
      } catch {
        // Alerts are on; this welcome is only a preview.
      }
    } catch {
      setPhase('error');
    }
  };

  const turnOff = async () => {
    setPhase('busy');
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) await alertsApi.turnOff(slug, sub.endpoint);
    } catch {
      // Turned off on this phone anyway; the server drops it on the next alert if it is gone.
    }
    rememberAlerts(slug, false);
    setPhase('idle');
  };

  return (
    <div className="alerts-card">
      <div className="row" style={{ alignItems: 'center' }}>
        <span className="eyebrow">LAST PLATES ALERTS</span>
        {phase === 'on' && <span className="alerts-on-pill">On</span>}
      </div>

      {/* What the alert looks like on the phone. */}
      <div className="alert-preview" aria-hidden="true">
        <div className="alert-preview-avatar">
          <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="excited" pose="idle" size={44} />
        </div>
        <div className="alert-preview-text">
          <span className="alert-preview-app">CUSTOMA · now</span>
          <strong>{first}: last plates tonight! 🍲</strong>
          <span>Only 8 plates left at {standName}. Come chop before 8:30 PM 🏃🏾</span>
        </div>
      </div>

      {info.sms && <TextAlerts slug={slug} first={first} terms={info.sms_terms ?? ''} texting={info.texting} />}

      {pushOffered && (phase === 'on' ? (
        <>
          <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>🔔 {first} go also ping this phone when food is almost finished.</span>
          <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={turnOff}>Turn phone pings off</button>
        </>
      ) : phase === 'denied' ? (
        <span className="note">Pings are blocked on this phone. Allow notifications for this site in your browser settings, then try again.</span>
      ) : info.sms ? (
        <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} disabled={phase === 'busy'} onClick={turnOn}>
          {phase === 'busy' ? 'Turning on…' : 'Or get free pings on this phone instead 🔔'}
        </button>
      ) : (
        <>
          <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Get a ping when {first} has food left before closing. Only then, no spam.</span>
          <button type="button" className="btn" disabled={phase === 'busy'} onClick={turnOn}>
            {phase === 'busy' ? 'Turning on…' : `🔔 Get ${first}'s alerts`}
          </button>
        </>
      ))}
      {pushOffered && phase === 'error' && <span className="error">Could not turn on pings. Check your connection and try again.</span>}
      {!info.sms && <span className="alerts-soon">📱 Text alerts: coming soon</span>}
    </div>
  );
}

// Text-message alerts: the customer's number and their "I agree" to the terms (shown in full).
function TextAlerts({ slug, first, terms, texting }: { slug: string; first: string; terms: string; texting: string | null }) {
  const [number, setNumber] = useState<string | null>(texting);
  const [phone, setPhone] = useState('');
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const textMe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agree || !phone.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setNumber((await alertsApi.textMe(slug, phone)).texting);
      setPhone('');
    } catch (err) {
      setError((err as ApiError).message || 'Could not turn on texts. Check your connection and try again.');
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await alertsApi.stopTexts(slug);
      setNumber(null);
      setAgree(false);
    } catch {
      setError('Could not stop texts. Check your connection and try again.');
    } finally {
      setBusy(false);
    }
  };

  if (number) {
    return (
      <>
        <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>📱 {first} go text {number} when food is almost finished.</span>
        <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} disabled={busy} onClick={stop}>Stop texts</button>
        {error && <span className="error">{error}</span>}
      </>
    );
  }

  return (
    <form className="text-alerts" onSubmit={textMe}>
      <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Get a text when {first} has food left before closing. Any phone, no app.</span>
      <label className="field" htmlFor={`sms-phone-${slug}`}>
        <span>Your phone number</span>
        <input
          id={`sms-phone-${slug}`}
          className="input"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          placeholder="0803 123 4567"
          value={phone}
          maxLength={24}
          onChange={(e) => setPhone(e.target.value)}
        />
      </label>
      <label className="text-alerts-agree">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
        <span>{terms}</span>
      </label>
      <button type="submit" className="btn" disabled={busy || !agree || !phone.trim()}>
        {busy ? 'Turning on…' : '📱 Text me'}
      </button>
      {error && <span className="error" role="alert">{error}</span>}
    </form>
  );
}
