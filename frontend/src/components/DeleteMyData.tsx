// "Delete my data": a clear, calm sheet that says exactly what goes, and asks the customer
// to confirm they understand before anything is deleted (it cannot be undone).
import { useEffect, useRef, useState } from 'react';
import { api, type ApiError, type CustomerState } from '../api';

type Props = {
  slug: string;
  standName: string;
  plates: number; // on the customer's card toward the next jara
  total: number;
  me: CustomerState | null;
  onDeleted: () => void;
};

export function DeleteMyData({ slug, standName, plates, total, me, onDeleted }: Props) {
  const [open, setOpen] = useState(false);
  const [sure, setSure] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const codes = me?.open_jara?.length ?? 0;

  const close = () => {
    if (busy) return;
    setOpen(false);
    setSure(false);
    setError(null);
    opener.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    sheet.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteMe(slug);
      setOpen(false);
      onDeleted();
    } catch (err) {
      // e.g. 409: prepaid Plate Ajo plates are still left at this stand.
      const e = err as ApiError;
      setError(typeof e.raw?.detail === 'string' ? e.raw.detail : 'Could not delete your data. Check your connection and try again.');
    } finally {
      setBusy(false);
    }
  };

  const goes = [
    `Your plates: ${plates} of ${total} toward your next jara`,
    ...(codes > 0 ? [`${codes} unused jara code${codes === 1 ? '' : 's'} (they stop working)`] : []),
    'Your first name, ratings and Lunch Crew place',
    'Your chat memory and food alerts',
  ];

  return (
    <>
      <div className="links">
        <button ref={opener} type="button" className="link-btn" onClick={() => setOpen(true)}>Delete my data</button>
      </div>
      {open && (
        <div className="sheet-backdrop" onClick={close}>
          <div
            ref={sheet}
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="del-title"
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            <span className="sheet-grip" aria-hidden="true" />
            <span className="sheet-icon" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" /></svg>
            </span>
            <h2 id="del-title" className="sheet-title">Delete your data at {standName}?</h2>
            <p className="sheet-lead">This removes you from this stand only. Your other food spots are not touched.</p>
            <div className="sheet-box">
              <span className="eyebrow">WHAT WILL BE DELETED</span>
              <ul className="sheet-list">
                {goes.map((g) => <li key={g}>{g}</li>)}
              </ul>
            </div>
            <p className="sheet-warn">This cannot be undone. Next time you scan here, you start again from plate 1.</p>
            <label className="check sheet-check">
              <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
              <span>I understand I will lose my plates{codes > 0 ? ' and jara codes' : ''} at this stand.</span>
            </label>
            {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
            <div className="sheet-actions">
              <button type="button" className="btn btn-danger" disabled={!sure || busy} onClick={remove}>
                {busy ? 'Deleting…' : 'Delete my data'}
              </button>
              <button type="button" className="btn btn-outline" disabled={busy} onClick={close}>Keep my card</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
