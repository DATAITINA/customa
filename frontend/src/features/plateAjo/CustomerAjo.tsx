import { useCallback, useEffect, useState } from 'react';
import type { StandPublic } from '../../api';
import { ajoApi, errorText, naira, parseUtc, timeOf, type AjoPublic, type Bundle, type UseResult } from './ajoApi';
import './plateAjo.css';

const HONEST = 'Pay the vendor directly by transfer. Customa only keeps count of your plates.';

// Plate Ajo, customer side: prepay plates at today's price, then use one per visit.
// Hidden when the stand has not turned it on (and the customer has no plates there), or on any
// load error: the stamp card above must keep working whatever happens here.
export function AjoCard({ slug, stand, onPlateCounted }: { slug: string; stand: StandPublic; onPlateCounted: () => void }) {
  const [data, setData] = useState<AjoPublic | null>(null);
  const [overlay, setOverlay] = useState<{ result: UseResult; shownAt: number } | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await ajoApi.read(slug));
    } catch {
      // Keep what we showed last (a refresh can fail on a weak network). Before the first
      // successful load data stays null, so the card stays hidden.
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const pending = data?.bundles.find((b) => b.status === 'pending') ?? null;
  const pendingId = pending?.id ?? null;
  // While a transfer waits for the vendor, look again now and then so the card updates by itself.
  useEffect(() => {
    if (pendingId === null) return;
    const t = setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, 15000);
    return () => clearInterval(t);
  }, [pendingId, load]);

  if (overlay) {
    return (
      <PaidPlate
        result={overlay.result}
        shownAt={overlay.shownAt}
        onDone={() => {
          setOverlay(null);
          onPlateCounted();
        }}
      />
    );
  }
  if (!data) return null;

  const active = data.bundles.filter((b) => b.status === 'active' && b.plates_left > 0).reverse(); // oldest first
  if (!data.available && !pending && active.length === 0) return null;

  const vendor = stand.stand.name.replace(' (Demo)', '');
  const latest = data.bundles[0];
  const ended = latest && (latest.status === 'rejected' || latest.status === 'closed') ? latest : null;

  return (
    <div className="card">
      <span className="eyebrow">PLATE AJO · LOCK TODAY'S PRICE</span>
      {active.length > 0 && <ActivePlates slug={slug} active={active} onUsed={(r) => { setOverlay({ result: r, shownAt: Date.now() }); load(); }} onError={load} />}
      {pending && <Pending bundle={pending} vendor={vendor} bank={data.bank} />}
      {!pending && ended && active.length === 0 && (
        <p className="note" style={{ margin: 0 }}>
          {ended.status === 'closed'
            ? `Closed by the vendor: your ${ended.item} plates (${ended.plates_used} of ${ended.plates_total} used) were refunded or settled with ${vendor}.`
            : `${vendor} could not confirm your transfer for ${ended.plates_total} plates of ${ended.item}. If you sent money, talk to the vendor.`}
          {data.available ? ' You can start again below.' : ''}
        </p>
      )}
      {!pending && data.available && data.bank && (
        <BuyFlow slug={slug} data={data} compact={active.length > 0} onStarted={load} />
      )}
    </div>
  );
}

function ActivePlates({
  slug, active, onUsed, onError,
}: { slug: string; active: Bundle[]; onUsed: (r: UseResult) => void; onError: () => void }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const next = active[0];
  const left = active.reduce((n, b) => n + b.plates_left, 0);

  const spendOne = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await ajoApi.use(slug);
      setAsking(false);
      onUsed(r);
    } catch (err) {
      setError(errorText(err, 'Could not use a plate. Check your connection and try again.'));
      onError();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ padding: 0, gap: 10 }}>
      <span className="ajo-big">
        {left} PLATE{left === 1 ? '' : 'S'} LEFT
      </span>
      <span style={{ fontWeight: 800, fontSize: 16 }}>
        {next.item} · {naira(next.unit_price)} locked
      </span>
      {active.length > 1 && (
        <span className="note">
          {active.map((b) => `${b.plates_left} × ${b.item} at ${naira(b.unit_price)}`).join(' · ')}
        </span>
      )}
      {asking ? (
        <div className="card-outline" style={{ background: 'var(--paper)' }}>
          <span style={{ fontWeight: 800 }}>Use 1 plate now?</span>
          <span className="note">Do this at the stand, when the vendor serves you.</span>
          <div className="ajo-actions">
            <button className="btn" disabled={busy} onClick={spendOne}>{busy ? 'Using…' : 'Yes, use 1'}</button>
            <button className="btn btn-outline" disabled={busy} onClick={() => setAsking(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <button className="btn" onClick={() => { setError(null); setAsking(true); }}>Use 1 prepaid plate</button>
      )}
      {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
    </div>
  );
}

function Pending({ bundle, vendor, bank }: { bundle: Bundle; vendor: string; bank: AjoPublic['bank'] }) {
  return (
    <div className="stack" style={{ padding: 0, gap: 8 }}>
      <div className="ajo-wait" role="status">
        <span className="ajo-wait-dot" aria-hidden="true" />
        <span>Waiting for {vendor} to confirm your transfer</span>
      </div>
      <div className="ajo-total">
        <span>{bundle.item} × {bundle.plates_total}</span>
        <strong>{naira(bundle.unit_price * bundle.plates_total)}</strong>
      </div>
      <span className="note">
        {bundle.payer_name ? `Sent by ${bundle.payer_name}` : 'Transfer sent'}
        {bank ? ` to ${bank.account_name}, ${bank.bank_name} ${bank.account_number}` : ''}. Price locked at{' '}
        {naira(bundle.unit_price)} a plate. Your plates appear here once the vendor sees the money.
      </span>
    </div>
  );
}

function BuyFlow({ slug, data, compact, onStarted }: { slug: string; data: AjoPublic; compact: boolean; onStarted: () => void }) {
  const [open, setOpen] = useState(!compact);
  const [step, setStep] = useState<'pick' | 'pay'>('pick');
  const [item, setItem] = useState<string | null>(data.items.length === 1 ? data.items[0].item : null);
  const [plates, setPlates] = useState(data.bundle_sizes[0] ?? 5);
  const [payer, setPayer] = useState('');
  const [copied, setCopied] = useState(false);
  const [manualCopy, setManualCopy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosen = data.items.find((m) => m.item === item) ?? null;
  const total = chosen ? chosen.price * plates : 0;
  const bank = data.bank!;

  if (data.items.length === 0) return compact ? null : <span className="note">The menu has no prices yet, so prepaying is not open.</span>;
  if (!open) {
    return (
      <button className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => setOpen(true)}>
        Prepay more plates
      </button>
    );
  }

  // Copy the number. Without a clipboard (old phone, in-app browser, http), or if copying fails,
  // show the number selected in a box so the customer can copy it by hand.
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('no clipboard');
      await navigator.clipboard.writeText(bank.account_number);
      setManualCopy(false);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
      setManualCopy(true);
    }
  };

  const send = async () => {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      await ajoApi.start(slug, { item: chosen.item, plates, payer_name: payer.trim(), unit_price: chosen.price });
      onStarted();
    } catch (err) {
      setError(errorText(err, 'Could not save. Check your connection and try again.'));
      // The price or menu may have changed (409): reload so the total on screen is the new one.
      onStarted();
    } finally {
      setBusy(false);
    }
  };

  if (step === 'pick' || !chosen) {
    return (
      <div className="stack" style={{ padding: 0, gap: 10 }}>
        {!compact && (
          <span style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.4 }}>
            Prepay 5 or 10 plates at today's price. If the price goes up, yours stays the same.
          </span>
        )}
        <div className="seg ajo-seg" role="group" aria-label="Food">
          {data.items.map((m) => (
            <button key={m.item} type="button" aria-pressed={item === m.item} onClick={() => setItem(m.item)}>
              {m.item} · {naira(m.price)}
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label="Plates">
          {data.bundle_sizes.map((n) => (
            <button key={n} type="button" aria-pressed={plates === n} onClick={() => setPlates(n)}>
              {n} plates
            </button>
          ))}
        </div>
        {chosen && (
          <div className="ajo-total">
            <span>{plates} × {naira(chosen.price)}</span>
            <strong>{naira(total)}</strong>
          </div>
        )}
        <button className="btn" disabled={!chosen} onClick={() => setStep('pay')}>
          {chosen ? `Pay ${naira(total)} by transfer` : 'Pick your food'}
        </button>
        <span className="note">{HONEST}</span>
      </div>
    );
  }

  const payerOk = payer.trim().length >= 2;
  return (
    <form
      className="stack"
      style={{ padding: 0, gap: 10 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (payerOk && !busy) send();
      }}
    >
      <span style={{ fontWeight: 800, fontSize: 15 }}>
        Send {naira(total)} for {plates} × {chosen.item} to:
      </span>
      <div className="ajo-bank">
        <span className="note" style={{ fontWeight: 700 }}>{bank.bank_name}</span>
        <div className="ajo-bank-row">
          <span className="ajo-number">{bank.account_number}</span>
          <button type="button" className="btn btn-outline ajo-small-btn" onClick={copy}>
            {copied ? 'Copied' : 'Copy number'}
          </button>
        </div>
        {manualCopy && (
          <>
            <input
              className="input"
              readOnly
              autoFocus
              value={bank.account_number}
              aria-label="Account number"
              onFocus={(e) => e.currentTarget.select()}
              onClick={(e) => e.currentTarget.select()}
            />
            <span className="note">Press and hold the number to copy it.</span>
          </>
        )}
        <span style={{ fontWeight: 800 }}>{bank.account_name}</span>
      </div>
      <label className="field">
        Name on your transfer
        <input
          className="input"
          value={payer}
          onChange={(e) => setPayer(e.target.value)}
          placeholder="e.g. Kelechi Okafor"
          maxLength={60}
          autoComplete="name"
        />
      </label>
      <button className="btn" type="submit" disabled={!payerOk || busy}>
        {busy ? 'Saving…' : `I have sent ${naira(total)}`}
      </button>
      {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
      <span className="note">{HONEST} The vendor confirms when the money arrives.</span>
      <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => setStep('pick')}>
        Back
      </button>
    </form>
  );
}

// The big screen the customer turns round to show the vendor.
function PaidPlate({ result, shownAt, onDone }: { result: UseResult; shownAt: number; onDone: () => void }) {
  const at = parseUtc(result.use.at);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  // Counted from when this phone got the answer, so a wrong phone clock cannot make it look old.
  const ago = Math.max(0, Math.round((now - shownAt) / 1000));
  const agoText = ago < 60 ? `${ago}s ago` : `${Math.floor(ago / 60)} min ago`;
  const { stamp } = result;
  return (
    <div className="ajo-overlay" role="dialog" aria-modal="true" aria-label="Paid plate">
      <div className="ajo-overlay-tick" aria-hidden="true">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </div>
      <h1 className="ajo-overlay-title">PAID PLATE</h1>
      <div className="ajo-overlay-card" role="status">
        <span className="ajo-overlay-item">{result.use.item}</span>
        <span className="ajo-overlay-plate">
          PLATE {result.use.plate_number} OF {result.use.plates_total}
        </span>
        <span className="ajo-overlay-time">
          {timeOf(result.use.at)} · {at.toLocaleDateString([], { day: 'numeric', month: 'short' })} · {agoText}
        </span>
        <span className="ajo-overlay-stamp">{stampText(result.stamp)}</span>
        {stamp.crew?.jara_to && !stamp.crew.jara_to_me && (
          <span className="ajo-overlay-jara">This jara goes to {stamp.crew.jara_to}</span>
        )}
        {stamp.jara && (
          <span className="ajo-overlay-jara">
            JARA! Free extra: <strong>{stamp.jara.code}</strong>
          </span>
        )}
        <span className="note">
          {result.bundle.plates_left} prepaid plate{result.bundle.plates_left === 1 ? '' : 's'} left
        </span>
      </div>
      <button className="btn" onClick={onDone}>Done</button>
    </div>
  );
}

function stampText(stamp: UseResult['stamp']): string {
  if (!stamp.counted) return 'Stamp already counted for this visit';
  if (stamp.crew) {
    const crew = stamp.crew.name || 'your crew';
    return `Stamp counted: plate ${stamp.crew.plate_number} of ${stamp.crew.plates_for_jara} on ${crew}'s card`;
  }
  return `Stamp counted: plate ${stamp.plate_number} on your jara card`;
}
