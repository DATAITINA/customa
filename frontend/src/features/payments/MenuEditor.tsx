import { useState } from 'react';
import { api, type ApiError, type Character } from '../../api';
import './pay.css';

// One line per dish: the text before the first number is the dish, the first number is its
// price in naira ("Tomatoes 1500", "Jollof rice ₦2,000", "Okra  ₦500–₦1,000 per portion").
export function parseMenuLines(text: string) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(/^(.*?)[\s,:\-–₦]*?(\d[\d,]*)/);
      const item = (m ? m[1] : line).replace(/[\s,:\-–₦]+$/, '').trim();
      return { item: item || line, price: m ? Number(m[2].replace(/,/g, '')) : 0 };
    });
}

// "Your menu & prices" on the vendor dashboard: prices let customers pay for a plate (and power
// Plate Ajo and the chat's menu answers).
export function MenuEditor({ slug, character, onSaved }: { slug: string; character: Character; onSaved: () => void }) {
  const toText = () => character.menu.map((m) => (m.price ? `${m.item} ${m.price}` : m.item)).join('\n');
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(toText);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const missing = character.menu.length === 0 || character.menu.some((m) => !m.price);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.updateCharacter(slug, { menu: parseMenuLines(text) });
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
      {missing && !open && <span className="note">Add a price to each dish so customers can pay for their plate.</span>}
      {open ? (
        <>
          <label className="field">One dish per line, then its price in naira
            <textarea className="input" rows={Math.min(12, Math.max(4, text.split('\n').length + 1))} value={text} onChange={(e) => setText(e.target.value)} placeholder={'Jollof rice 2000\nFish 20000'} />
          </label>
          <button type="button" className="btn" disabled={busy || !text.trim()} onClick={save}>{busy ? 'Saving…' : 'Save menu'}</button>
          <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => { setText(toText()); setOpen(false); }}>Cancel</button>
        </>
      ) : (
        <button type="button" className="btn btn-outline" onClick={() => { setText(toText()); setOpen(true); }}>Edit menu & prices</button>
      )}
      {msg && <span className={msg.endsWith('✓') ? 'note' : 'error'}>{msg}</span>}
    </section>
  );
}
