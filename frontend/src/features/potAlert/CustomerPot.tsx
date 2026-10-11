import { useEffect, useState } from 'react';
import type { StandPublic } from '../../api';
import { errorText, joinItems, potApi, type MyWatch, type PotPublic, type ReadyCall } from './potApi';
import './potAlert.css';

const REFRESH_MS = 60_000;

// Pot Alert, customer side: "tell me when ___ is ready" on WhatsApp.
// Mounted only once the customer exists (after their first plate). Hidden when the vendor has not
// turned Pot Alert on, when the menu is empty, or if the stand cannot be reached.
export function PotWatchCard({ slug }: { slug: string; stand: StandPublic }) {
  const [pot, setPot] = useState<PotPublic | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let alive = true;
    potApi
      .read(slug)
      .then((p) => alive && setPot(p))
      .catch(() => alive && setPot(null));
    return () => {
      alive = false;
    };
  }, [slug]);

  if (!pot || !pot.enabled || pot.items.length === 0) return null;
  const setMy = (my: MyWatch) => setPot({ ...pot, my });

  if (pot.my && !editing) {
    return <Watching slug={slug} my={pot.my} onChange={() => setEditing(true)} onStopped={() => setMy(null)} />;
  }
  return (
    <WatchForm
      slug={slug}
      menu={pot.items}
      my={pot.my}
      onSaved={(my) => {
        setMy(my);
        setEditing(false);
      }}
      onCancel={pot.my ? () => setEditing(false) : undefined}
    />
  );
}

function Watching({ slug, my, onChange, onStopped }: { slug: string; my: NonNullable<MyWatch>; onChange: () => void; onStopped: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="card" role="status">
      <span className="eyebrow">POT ALERT</span>
      <strong style={{ fontSize: 18, lineHeight: 1.3 }}>We'll tell you when {joinItems(my.items)} {my.items.length === 1 ? 'is' : 'are'} ready</strong>
      <span className="note">The vendor will message you on WhatsApp at {my.phone_masked}.</span>
      {error && <p className="error" role="alert">{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-outline pot-small-btn" style={{ flex: 1 }} onClick={onChange} disabled={busy}>Change</button>
        <button
          className="btn btn-outline pot-small-btn"
          style={{ flex: 1 }}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await potApi.stopWatches(slug);
              onStopped();
            } catch (err) {
              setError(errorText(err, 'Could not stop the alerts. Try again.'));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? 'Stopping…' : 'Stop alerts'}
        </button>
      </div>
    </div>
  );
}

function WatchForm({
  slug, menu, my, onSaved, onCancel,
}: { slug: string; menu: string[]; my: MyWatch; onSaved: (my: MyWatch) => void; onCancel?: () => void }) {
  const [picked, setPicked] = useState<string[]>(() => (my ? my.items.filter((i) => menu.includes(i)) : []));
  const [phone, setPhone] = useState('');
  // Asked on every save: nothing is pre-ticked, even when changing an existing list.
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const keepPhone = !!my;
  const toggle = (item: string) =>
    setPicked((p) => (p.includes(item) ? p.filter((x) => x !== item) : p.length >= 10 ? p : [...p, item]));

  return (
    <form
      className="card"
      onSubmit={async (e) => {
        e.preventDefault();
        if (picked.length === 0) {
          setError('Pick at least one dish');
          return;
        }
        if (!consent) {
          setError('Please agree to WhatsApp messages from the vendor');
          return;
        }
        if (!phone.trim() && !keepPhone) {
          setError('Enter your WhatsApp number');
          return;
        }
        setBusy(true);
        setError(null);
        try {
          const r = await potApi.saveWatches(slug, picked, phone.trim(), consent);
          onSaved(r.my);
        } catch (err) {
          setError(errorText(err, 'Could not save. Try again.'));
        } finally {
          setBusy(false);
        }
      }}
    >
      <span className="eyebrow">POT ALERT</span>
      <strong style={{ fontSize: 20, lineHeight: 1.2 }}>Tell me when it's ready</strong>
      <span className="note">Pick the dishes you want. Tap again to remove.</span>
      <div className="seg pot-dishes" role="group" aria-label="Dishes">
        {menu.map((item) => (
          <button type="button" key={item} aria-pressed={picked.includes(item)} onClick={() => toggle(item)}>
            {item}
          </button>
        ))}
      </div>
      <label className="field">
        {keepPhone ? `WhatsApp number (leave empty to keep ${my!.phone_masked})` : 'Your WhatsApp number'}
        <input
          className="input"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          maxLength={20}
          placeholder="0803 123 4567"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
      </label>
      <label className="check">
        <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>The vendor can message me on WhatsApp when these dishes are ready. I can remove this anytime.</span>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn" type="submit" disabled={busy || !consent}>{busy ? 'Saving…' : 'Tell me when it\'s ready'}</button>
      {onCancel && (
        <button type="button" className="link-btn" style={{ alignSelf: 'center' }} onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      )}
    </form>
  );
}

// Shown at the top of the stand page to everyone while a pot is ready.
export function PotReadyBanner({ slug }: { slug: string }) {
  const [ready, setReady] = useState<ReadyCall[]>([]);

  useEffect(() => {
    let alive = true;
    const load = () =>
      potApi
        .read(slug)
        .then((p) => alive && setReady(p.enabled ? p.ready : []))
        .catch(() => alive && setReady([]));
    load();
    const t = setInterval(load, REFRESH_MS);
    // Phones pause timers in the background: refresh when the page is shown again.
    const onShow = () => document.visibilityState === 'visible' && load();
    document.addEventListener('visibilitychange', onShow);
    return () => {
      alive = false;
      clearInterval(t);
      document.removeEventListener('visibilitychange', onShow);
    };
  }, [slug]);

  // The server only sends live calls; also drop any that ran out since the last refresh.
  const now = Date.now();
  const live = ready
    .filter((r) => {
      const end = Date.parse(r.until + 'Z');
      return Number.isNaN(end) || end > now;
    })
    .slice(0, 3);
  if (live.length === 0) return null;
  return (
    <div className="pot-banner-wrap">
      <div className="last-plates pot-banner" role="status">
        <span className="lp-dot" aria-hidden="true" />
        <span className="pot-banner-lines">
          {live.map((r) => (
            <strong key={r.id}>
              🔥 {r.item} is ready now
              {r.plates_left ? ` · ${r.plates_left} plate${r.plates_left === 1 ? '' : 's'} left` : ''}
            </strong>
          ))}
        </span>
      </div>
    </div>
  );
}
