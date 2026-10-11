import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  errorText,
  potApi,
  readyMessage,
  statusMessage,
  waLink,
  type PotVendor,
  type ReadyResult,
} from './potApi';
import './potAlert.css';

const panelStyle = { margin: 0, padding: 16, gap: 10 } as const;
const cleanName = (name: string) => name.replace(' (Demo)', '');

// Pot Alert, vendor side: demand per dish, "ready now", one-tap WhatsApp messages.
// Customa does not send WhatsApp messages: the vendor sends each one from their own WhatsApp.
export function VendorPotPanel({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ['pot', slug], queryFn: () => potApi.vendor(slug), refetchInterval: 15000 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notify, setNotify] = useState<ReadyResult | null>(null);
  // Who the vendor already tapped WhatsApp for, per ready call (this screen only).
  const [sent, setSent] = useState<Set<string>>(new Set());

  if (q.isLoading) return null;
  if (q.isError || !q.data) {
    return (
      <div className="hero" style={panelStyle}>
        <span className="eyebrow">POT ALERT</span>
        <p className="error">Could not load Pot Alert.</p>
      </div>
    );
  }
  const d = q.data;

  const run = async (fn: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await q.refetch();
    } catch (err) {
      setError(errorText(err, fallback));
    } finally {
      setBusy(false);
    }
  };
  const switchTo = (enabled: boolean) =>
    run(async () => {
      await potApi.setEnabled(slug, enabled);
      if (!enabled) setNotify(null);
    }, 'Could not change Pot Alert. Try again.');

  if (!d.enabled) {
    return (
      <div className="hero" style={panelStyle}>
        <span className="eyebrow">POT ALERT: "YOUR AFANG DON READY"</span>
        <span style={{ fontWeight: 600, fontSize: 15, lineHeight: 1.4 }}>
          Customers pick dishes they want to hear about. When a pot is ready, you tap it and message them on WhatsApp with one tap each.
        </span>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn pot-small-btn" style={{ alignSelf: 'flex-start' }} disabled={busy} onClick={() => switchTo(true)}>
          Turn on Pot Alert
        </button>
      </div>
    );
  }

  const liveByItem = new Map(d.ready.map((r) => [r.item, r]));
  // A live call for a dish since removed from the menu still needs its "End" button.
  const rows = [
    ...d.demand,
    ...d.ready.filter((r) => !d.demand.some((x) => x.item === r.item)).map((r) => ({ item: r.item, waiting: 0 })),
  ];
  return (
    <div className="hero" style={panelStyle}>
      <div className="row" style={{ alignItems: 'center' }}>
        <span className="eyebrow">POT ALERT: TELL CUSTOMERS WHEN FOOD IS READY</span>
        <button className="link-btn" disabled={busy} onClick={() => switchTo(false)}>Turn off</button>
      </div>

      {notify && (
        <TellCustomers
          key={notify.ready.id}
          slug={slug}
          standName={cleanName(d.stand_name)}
          result={notify}
          sent={sent}
          onSent={(k) => setSent((s) => new Set(s).add(k))}
          onClose={() => setNotify(null)}
        />
      )}

      {rows.length === 0 && (
        <span className="note">Add dishes to your menu first. Customers choose from your menu.</span>
      )}
      <div>
        {rows.map((row) => (
          <DishLine
            key={row.item}
            item={row.item}
            waiting={row.waiting}
            live={liveByItem.get(row.item) ?? null}
            busy={busy}
            onReady={(plates) =>
              run(async () => setNotify(await potApi.ready(slug, row.item, plates)), 'Could not mark it ready. Try again.')
            }
            onEnd={(id) =>
              run(async () => {
                await potApi.end(slug, id);
                setNotify((n) => (n && n.ready.id === id ? null : n));
              }, 'Could not end it. Try again.')
            }
            onMessage={(id) => run(async () => setNotify(await potApi.watchers(slug, id)), 'Could not load the list.')}
          />
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <span className="note">Ready calls show on your stand page for 3 hours, or until you end them.</span>
    </div>
  );
}

type Live = PotVendor['ready'][number] | null;

function DishLine({
  item, waiting, live, busy, onReady, onEnd, onMessage,
}: {
  item: string;
  waiting: number;
  live: Live;
  busy: boolean;
  onReady: (platesLeft: number | null) => void;
  onEnd: (id: number) => void;
  onMessage: (id: number) => void;
}) {
  const [plates, setPlates] = useState('');
  const n = plates.trim() === '' ? null : Math.floor(Number(plates));
  const platesOk = n === null || (Number.isFinite(n) && n >= 1 && n <= 500);
  return (
    <div className="pot-line">
      <div className="pot-line-name">
        <span>{item}</span>
        <span className={waiting > 0 ? 'pot-waiting pot-waiting-some' : 'pot-waiting'}>{waiting} waiting</span>
        {live && (
          <span className="pot-waiting" style={{ color: 'var(--ink)' }}>
            🔥 Ready now{live.plates_left ? ` · ${live.plates_left} plates left` : ''}
          </span>
        )}
      </div>
      <div className="pot-line-actions">
        {live ? (
          <>
            <button className="btn btn-outline pot-small-btn" disabled={busy} onClick={() => onMessage(live.id)}>Message</button>
            <button className="btn btn-outline pot-small-btn" disabled={busy} onClick={() => onEnd(live.id)}>End (sold out)</button>
          </>
        ) : (
          <>
            <input
              className="input pot-plates"
              type="number"
              inputMode="numeric"
              min={1}
              max={500}
              placeholder="Plates"
              aria-label={`Plates of ${item} left (optional)`}
              value={plates}
              onChange={(e) => setPlates(e.target.value)}
            />
            <button className="btn pot-small-btn" disabled={busy || !platesOk} onClick={() => { onReady(n); setPlates(''); }}>
              Ready now
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function TellCustomers({
  slug, standName, result, sent, onSent, onClose,
}: { slug: string; standName: string; result: ReadyResult; sent: Set<string>; onSent: (key: string) => void; onClose: () => void }) {
  const { ready, watchers } = result;
  const [copied, setCopied] = useState<'yes' | 'manual' | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const base = { item: ready.item, standName, platesLeft: ready.plates_left, slug };
  const status = statusMessage(base);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(status);
      setCopied('yes');
    } catch {
      // No clipboard access (older phone, http): show the text selected so the vendor can copy it.
      setCopied('manual');
      setTimeout(() => {
        textRef.current?.focus();
        textRef.current?.select();
      }, 0);
    }
  };

  return (
    <div className="pot-notify" aria-live="polite">
      <div className="row" style={{ alignItems: 'center' }}>
        <strong style={{ fontSize: 17 }}>Tell your customers: {ready.item} is ready</strong>
        <button className="link-btn" onClick={onClose}>Done</button>
      </div>
      {watchers.length === 0 ? (
        <span className="note">Nobody is waiting for {ready.item} yet. Post it on your WhatsApp Status instead.</span>
      ) : (
        <span className="note">Tap each WhatsApp button. Your WhatsApp opens with the message ready, then tap send.</span>
      )}
      {watchers.map((w, i) => {
        const key = `${ready.id}:${w.phone}`;
        return (
          <div key={`${key}:${i}`} className="row" style={{ alignItems: 'center' }}>
            <span style={{ fontWeight: 700 }}>
              {w.name}{' '}
              {sent.has(key) && <span className="pot-sent">✓ sent</span>}
            </span>
            <a
              className="btn pot-small-btn pot-wa"
              href={waLink(w.phone, readyMessage({ ...base, name: w.name }))}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => onSent(key)}
            >
              WhatsApp
            </a>
          </div>
        );
      })}
      <button className="btn btn-outline pot-small-btn" style={{ alignSelf: 'flex-start' }} onClick={copy}>
        {copied === 'yes' ? '✓ Copied. Paste it in your Status' : 'Copy for WhatsApp Status'}
      </button>
      {copied === 'manual' && (
        <>
          <span className="note">Copy this text, then paste it in your WhatsApp Status:</span>
          <textarea ref={textRef} className="input pot-status-text" readOnly value={status} onFocus={(e) => e.currentTarget.select()} />
        </>
      )}
    </div>
  );
}
