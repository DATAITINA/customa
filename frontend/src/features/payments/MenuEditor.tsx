import { useState } from 'react';
import { api, type ApiError, type Character } from '../../api';
import { MenuRows, fromRows, menuProblem, toRows, type MenuRow } from '../../components/MenuRows';
import './pay.css';

// "Your menu & prices" on the vendor dashboard: a food box and a price box per dish. Prices let
// customers pay for a plate, and power Plate Ajo and the character's menu answers.
export function MenuEditor({ slug, character, onSaved }: { slug: string; character: Character; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<MenuRow[]>(() => toRows(character.menu));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const missing = character.menu.length === 0 || character.menu.some((m) => !m.price);

  const save = async () => {
    const problem = menuProblem(rows);
    if (problem) { setMsg(problem); return; }
    setBusy(true);
    setMsg(null);
    try {
      await api.updateCharacter(slug, { menu: fromRows(rows) });
      setMsg('Saved ✓');
      setOpen(false);
      onSaved();
    } catch (err) {
      setMsg((err as ApiError).message || 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-outline pay-card" aria-label="Your menu and prices">
      <span className="eyebrow">YOUR MENU & PRICES</span>
      {missing && !open && <span className="note">Add a price to each food so customers can pay for their plate.</span>}
      {open ? (
        <>
          <MenuRows rows={rows} onChange={setRows} />
          <button type="button" className="btn" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save menu'}</button>
          <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => { setRows(toRows(character.menu)); setOpen(false); setMsg(null); }}>Cancel</button>
        </>
      ) : (
        <button type="button" className="btn btn-outline" onClick={() => { setRows(toRows(character.menu)); setOpen(true); }}>Edit menu & prices</button>
      )}
      {msg && <span className={msg.endsWith('✓') ? 'note' : 'error'} role={msg.endsWith('✓') ? undefined : 'alert'}>{msg}</span>}
    </section>
  );
}
