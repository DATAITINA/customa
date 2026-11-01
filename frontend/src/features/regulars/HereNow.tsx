import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { keyBytes, pushSupport } from '../alerts/alertsApi';
import { regularsApi, type HereNow, type PingInfo } from './regularsApi';
import './regulars.css';

const JARA_TEXT = { next_is_jara: 'next plate is jara!', has_jara: 'has a jara code' } as const;
const time = (iso: string) => new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

// "Ime don land!": who is at the stand now, so staff greet regulars by name. Live with the
// dashboard (it refreshes every 10 seconds); "Greeted ✓" is saved to measure greeting.
export function HereNowCard({ slug, entries, onChange }: { slug: string; entries: HereNow[]; onChange: () => void }) {
  const [greeted, setGreeted] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState<number | null>(null);

  const greet = async (id: number) => {
    setBusy(id);
    setGreeted((g) => ({ ...g, [id]: true }));
    try {
      await regularsApi.greeted(slug, id);
      onChange();
    } catch {
      setGreeted((g) => ({ ...g, [id]: false }));
    } finally {
      setBusy(null);
    }
  };

  const regulars = entries.filter((e) => e.returning).length;
  return (
    <section className="here-now" aria-labelledby={`here-${slug}`}>
      <div className="here-now-head">
        <span id={`here-${slug}`} className="eyebrow">WHO'S HERE NOW</span>
        {entries.length > 0 && <span className="here-count">{regulars} regular{regulars === 1 ? '' : 's'} · {entries.length - regulars} new</span>}
      </div>
      {entries.length === 0 ? (
        <span className="note">When customers scan, they show here so you can greet them by name.</span>
      ) : (
        <ul className="here-list">
          {entries.map((e) => {
            const done = !!e.greeted_at || greeted[e.id];
            return (
              <li key={e.id} className={`here-item${e.returning ? ' regular' : ''}${done ? ' done' : ''}`}>
                <span className="here-avatar" aria-hidden="true">{e.name ? e.name[0].toUpperCase() : e.returning ? '★' : '👋'}</span>
                <div className="here-main">
                  <div className="here-who">
                    <strong>{e.name ?? (e.returning ? 'A regular' : 'A new customer')}</strong>
                    <span className="here-tag">{e.visit_label}</span>
                  </div>
                  <span className="note">
                    {[e.last_came && `last came ${e.last_came}`, e.jara && JARA_TEXT[e.jara], `here since ${time(e.at)}`].filter(Boolean).join(' · ')}
                  </span>
                  {e.usual && <span className="here-usual">Their usual: <strong>{e.usual}</strong></span>}
                  <span className="here-say">Say: “{e.greeting}”</span>
                </div>
                <button type="button" className={`here-greet${done ? ' on' : ''}`} disabled={done || busy === e.id} onClick={() => greet(e.id)} aria-label={done ? 'Greeted' : `Mark ${e.name ?? 'this customer'} as greeted`}>
                  {done ? 'Greeted ✓' : 'Greeted?'}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <PingToggle slug={slug} />
    </section>
  );
}

const pingKey = (slug: string) => `customa:vendor-ping:${slug}`;

// "Ping me when regulars arrive": web push to this phone (returning customers only, once per
// visit). Optional: the card above works without it.
function PingToggle({ slug }: { slug: string }) {
  const [info, setInfo] = useState<PingInfo | null>(null);
  const [on, setOn] = useState(() => { try { return localStorage.getItem(pingKey(slug)) === '1'; } catch { return false; } });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const support = pushSupport();

  useEffect(() => { regularsApi.pingInfo(slug).then(setInfo).catch(() => setInfo(null)); }, [slug]);
  if (!info?.available || !info.public_key || support !== 'ok') return null;

  const remember = (v: boolean) => { try { if (v) localStorage.setItem(pingKey(slug), '1'); else localStorage.removeItem(pingKey(slug)); } catch { /* not kept */ } };
  const turnOn = async () => {
    setBusy(true);
    setError(null);
    try {
      if ((await Notification.requestPermission()) !== 'granted') {
        setError('Notifications are blocked. Allow them for this site in your browser settings.');
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(info.public_key!) }));
      await regularsApi.pingOn(slug, sub.toJSON());
      remember(true);
      setOn(true);
    } catch (err) {
      setError((err as ApiError).message || 'Could not turn on pings. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const turnOff = async () => {
    setBusy(true);
    try {
      const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
      if (sub) await regularsApi.pingOff(slug, sub.endpoint);
    } catch {
      // Off on this phone anyway.
    }
    remember(false);
    setOn(false);
    setBusy(false);
  };

  return (
    <div className="here-ping">
      {on ? (
        <>
          <span>🔔 This phone gets a ping when a regular arrives.</span>
          <button type="button" className="link-btn" onClick={turnOff} disabled={busy}>Turn off</button>
        </>
      ) : (
        <button type="button" className="here-ping-btn" onClick={turnOn} disabled={busy}>🔔 Ping me when regulars arrive</button>
      )}
      {error && <span className="error">{error}</span>}
    </div>
  );
}

