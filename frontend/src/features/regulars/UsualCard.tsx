import { useEffect, useState } from 'react';
import type { ApiError } from '../../api';
import { regularsApi } from './regularsApi';
import './regulars.css';

// "Let <stand> know my usual": off by default. Only when the customer turns it on and picks a
// menu item does the staff alert show it. Nothing is ever taken from the private chat.
export function UsualCard({ slug, standName }: { slug: string; standName: string }) {
  const [menu, setMenu] = useState<string[] | null>(null);
  const [usual, setUsual] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    regularsApi.usual(slug).then((r) => { setMenu(r.menu); setUsual(r.usual); }).catch(() => setMenu(null));
  }, [slug]);

  if (!menu || menu.length === 0) return null;
  const on = usual !== null || open;

  const pick = async (item: string) => {
    setBusy(true);
    setError(null);
    try {
      setUsual((await regularsApi.setUsual(slug, item)).usual);
    } catch (err) {
      setError((err as ApiError).message || 'Could not save. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const clear = async () => {
    setBusy(true);
    setError(null);
    try {
      await regularsApi.clearUsual(slug);
      setUsual(null);
      setOpen(false);
    } catch {
      setError('Could not clear it. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-outline usual-card">
      <label className="usual-switch">
        <span>
          <strong>Let {standName} know my usual</strong>
          <span className="note" style={{ display: 'block' }}>Staff see it when you arrive, so your food fit start quick. Off until you choose.</span>
        </span>
        <input type="checkbox" role="switch" checked={on} disabled={busy} onChange={(e) => (e.target.checked ? setOpen(true) : void clear())} />
      </label>
      {on && (
        <div className="usual-items" role="radiogroup" aria-label="My usual">
          {menu.map((m) => (
            <button key={m} type="button" role="radio" aria-checked={usual === m} className={usual === m ? 'on' : undefined} disabled={busy} onClick={() => pick(m)}>
              {m}
            </button>
          ))}
        </div>
      )}
      {usual && <span className="note">Your usual: <strong>{usual}</strong>. Turn the switch off to clear it.</span>}
      {error && <span className="error">{error}</span>}
    </div>
  );
}
