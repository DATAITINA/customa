import { useState } from 'react';
import { PanelSkeleton } from '../../components/Loading';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ajoApi, errorText, naira, timeOf, type AjoVendor } from './ajoApi';
import './plateAjo.css';

// Plate Ajo, vendor side: turn it on, bank details, confirm transfers, see plates left.
// Customers pay into the vendor's own account; Customa only keeps the plate count.
export function VendorAjoPanel({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ['ajo', slug], queryFn: () => ajoApi.vendor(slug), refetchInterval: 15000 });
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (q.isLoading) return <PanelSkeleton label="Plate Ajo" />;
  if (q.isError || !q.data) {
    return (
      <div className="card ajo-panel">
        <span className="eyebrow">PLATE AJO</span>
        <p className="error" style={{ margin: 0 }}>Could not load Plate Ajo.</p>
      </div>
    );
  }
  const d = q.data;
  const hasBank = Boolean(d.bank_name && d.account_number && d.account_name);

  const run = async (key: string, fn: () => Promise<unknown>, fallback: string) => {
    setBusy(key);
    setError(null);
    try {
      const result = await fn();
      // Settings calls return the whole panel: show it at once instead of a second request.
      if (result && typeof result === 'object' && 'enabled' in result && 'pending' in result) {
        qc.setQueryData(['ajo', slug], result as AjoVendor);
      } else {
        await q.refetch();
      }
      return true;
    } catch (err) {
      setError(errorText(err, fallback));
      await q.refetch();
      return false;
    } finally {
      setBusy(null);
    }
  };

  const toggle = async () => {
    if (!d.enabled && !hasBank) {
      setEditing(true); // turning on needs the bank details first
      return;
    }
    // Flip at once; the save runs in the background and flips back if it fails.
    const next = !d.enabled;
    qc.setQueryData(['ajo', slug], { ...d, enabled: next });
    const ok = await run('switch', () => ajoApi.saveSettings(slug, { enabled: next }), 'Could not change Plate Ajo. Try again.');
    if (!ok) qc.setQueryData(['ajo', slug], { ...d, enabled: !next });
  };
  const needsBank = !d.enabled && !hasBank;

  const head = (
    <div className="ajo-head">
      <span className="eyebrow">PLATE AJO: CUSTOMERS PREPAY AT TODAY'S PRICE</span>
      <button
        type="button"
        role="switch"
        aria-checked={d.enabled}
        className="switch"
        disabled={busy !== null}
        onClick={toggle}
      >
        <span className="switch-track" aria-hidden="true" />
        {d.enabled ? 'On' : 'Off'}
      </button>
    </div>
  );

  const form = editing && (
    <BankForm
      initial={d}
      turningOn={!d.enabled}
      busy={busy === 'save'}
      onCancel={() => setEditing(false)}
      onSave={async (body) => {
        const ok = await run('save', () => ajoApi.saveSettings(slug, body), 'Could not save. Try again.');
        if (ok) setEditing(false);
      }}
    />
  );

  if (!d.enabled) {
    return (
      <div className="card ajo-panel">
        {head}
        <span style={{ fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.4 }}>
          Customers prepay you 5 or 10 plates by transfer to your own account, and use one plate per visit.
          You get cash up front; they beat price rises.
        </span>
        {needsBank && !editing && (
          <button type="button" className="btn ajo-setup-btn" onClick={() => setEditing(true)}>Add bank details to turn on</button>
        )}
        {needsBank && editing && (
          <span className="ajo-setup-hint">Add the account customers will pay into. Plate Ajo turns on when you save.</span>
        )}
        {form}
        {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
        {(d.pending.length > 0 || d.active.length > 0) && <Lists slug={slug} d={d} busy={busy} rejecting={rejecting} setRejecting={setRejecting} run={run} />}
      </div>
    );
  }

  return (
    <div className="card ajo-panel">
      {head}
      {editing ? (
        form
      ) : (
        <div className="row" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700, fontSize: '0.9375rem' }}>
            Pay to: {d.bank_name} · {d.account_number} · {d.account_name}
          </span>
          <button className="link-btn" onClick={() => setEditing(true)}>Edit bank details</button>
        </div>
      )}
      {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
      <Lists slug={slug} d={d} busy={busy} rejecting={rejecting} setRejecting={setRejecting} run={run} />
    </div>
  );
}

type Run = (key: string, fn: () => Promise<unknown>, fallback: string) => Promise<boolean>;

function Lists({
  slug, d, busy, rejecting, setRejecting, run,
}: { slug: string; d: AjoVendor; busy: string | null; rejecting: number | null; setRejecting: (id: number | null) => void; run: Run }) {
  const [closing, setClosing] = useState<number | null>(null);
  return (
    <div className="grid-2">
      <div className="card-outline ajo-section" style={{ background: 'var(--card)' }}>
        <span className="eyebrow">TRANSFERS TO CONFIRM</span>
        {d.pending.length === 0 && <span className="note">No transfers waiting.</span>}
        {d.pending.map((p) => (
          <div key={p.id} className="ajo-line">
            <span className="ajo-line-name">
              {p.name}
              <span className="note">
                Name on transfer: {p.payer_name || '–'} · {timeOf(p.created_at)}
              </span>
              <span style={{ fontWeight: 700 }}>
                {p.item} × {p.plates_total} = {naira(p.total)}
              </span>
            </span>
            {rejecting === p.id ? (
              <span className="ajo-actions" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="note">Reject only if no money came.</span>
                <button
                  className="btn ajo-small-btn"
                  disabled={busy !== null}
                  onClick={async () => {
                    await run(`reject-${p.id}`, () => ajoApi.reject(slug, p.id), 'Could not reject. Try again.');
                    setRejecting(null);
                  }}
                >
                  {busy === `reject-${p.id}` ? 'Rejecting…' : 'Yes, reject'}
                </button>
                <button className="btn btn-outline ajo-small-btn" disabled={busy !== null} onClick={() => setRejecting(null)}>
                  Keep
                </button>
              </span>
            ) : (
              <span className="ajo-actions">
                <button
                  className="btn ajo-small-btn ajo-ok"
                  disabled={busy !== null}
                  onClick={() => run(`confirm-${p.id}`, () => ajoApi.confirm(slug, p.id), 'Could not confirm. Try again.')}
                >
                  {busy === `confirm-${p.id}` ? 'Confirming…' : `Got ${naira(p.total)}`}
                </button>
                <button className="btn btn-outline ajo-small-btn" disabled={busy !== null} onClick={() => setRejecting(p.id)}>
                  Reject
                </button>
              </span>
            )}
          </div>
        ))}
        {d.pending.length > 0 && (
          <span className="note" style={{ paddingTop: 8 }}>Check your bank app for the money before you confirm.</span>
        )}
      </div>

      <div className="card-outline ajo-section" style={{ background: 'var(--card)' }}>
        <span className="eyebrow">PREPAID PLATES LEFT</span>
        {d.active.length === 0 && <span className="note">No prepaid plates yet.</span>}
        {d.active.map((a) => (
          <div key={a.id} className="ajo-line">
            <span className="ajo-line-name">
              {a.name}
              <span className="note">
                {a.item} at {naira(a.unit_price)}
              </span>
            </span>
            <strong>
              {a.plates_left} of {a.plates_total} left
            </strong>
            {closing === a.id ? (
              <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button
                  className="btn ajo-small-btn"
                  disabled={busy !== null}
                  onClick={async () => {
                    await run(`close-${a.id}`, () => ajoApi.close(slug, a.id), 'Could not close. Try again.');
                    setClosing(null);
                  }}
                >
                  {busy === `close-${a.id}` ? 'Closing…' : 'Yes, refunded'}
                </button>
                <button className="btn btn-outline ajo-small-btn" disabled={busy !== null} onClick={() => setClosing(null)}>
                  Keep
                </button>
              </span>
            ) : (
              // For when the vendor refunds the customer outside Customa (or settles it in food).
              <button className="btn btn-outline ajo-small-btn" disabled={busy !== null} onClick={() => setClosing(a.id)}>
                Close (refunded)
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="card-outline ajo-section" style={{ background: 'var(--card)' }}>
        <span className="eyebrow">PREPAID PLATES SERVED TODAY</span>
        {d.served_today.length === 0 && <span className="note">None served today.</span>}
        {d.served_today.map((s) => (
          <div key={s.id} className="ajo-line">
            <span className="ajo-line-name">
              {s.name}
              <span className="note">{s.item}</span>
            </span>
            <span style={{ fontWeight: 700 }}>
              Plate {s.plate_number}/{s.plates_total} · {timeOf(s.at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function BankForm({
  initial, turningOn, busy, onSave, onCancel,
}: {
  initial: AjoVendor;
  turningOn: boolean;
  busy: boolean;
  onSave: (body: { enabled: boolean; bank_name: string; account_number: string; account_name: string }) => void;
  onCancel: () => void;
}) {
  const [bank, setBank] = useState(initial.bank_name ?? '');
  const [number, setNumber] = useState(initial.account_number ?? '');
  const [name, setName] = useState(initial.account_name ?? '');
  const digits = number.replace(/\D/g, '');
  const ok = bank.trim().length > 0 && digits.length === 10 && name.trim().length > 0;
  return (
    <form
      className="stack"
      style={{ padding: 0, gap: 10 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (ok) onSave({ enabled: true, bank_name: bank.trim(), account_number: digits, account_name: name.trim() });
      }}
    >
      <span className="note">Customers send money straight to this account. Customa never holds money.</span>
      <div className="ajo-form">
        <label className="field">
          Bank name
          <input className="input" value={bank} onChange={(e) => setBank(e.target.value)} maxLength={60} placeholder="e.g. Opay" autoFocus />
        </label>
        <label className="field">
          Account number
          <input
            className="input"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            inputMode="numeric"
            maxLength={14}
            placeholder="10 digits"
          />
        </label>
        <label className="field">
          Account name
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="As your bank shows it" />
        </label>
      </div>
      {number && digits.length !== 10 && <span className="error">The account number must be 10 digits.</span>}
      {!ok && !(number && digits.length !== 10) && <span className="note">Fill in all three to continue.</span>}
      <div className="ajo-actions" style={{ maxWidth: 420 }}>
        <button className="btn" type="submit" disabled={!ok || busy}>
          {busy ? 'Saving…' : turningOn ? 'Save and turn on' : 'Save'}
        </button>
        <button className="btn btn-outline" type="button" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
