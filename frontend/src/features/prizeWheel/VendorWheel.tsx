import { useEffect, useRef, useState } from 'react';
import { photoUrl, type ApiError, type Character as CharacterT } from '../../api';
import { shrinkPhoto } from '../../utils/photo';
import { Wheel } from './Wheel';
import { CHANCES, wheelApi, type ItemInput, type VendorWheel, type Weight, type WheelItemVendor } from './wheelApi';
import './wheel.css';

type Draft = { id: number | null; name: string; prize: string; description: string; weight: Weight; available: boolean; photo: string | null; photoChanged: boolean };

const emptyDraft = (): Draft => ({ id: null, name: '', prize: '', description: '', weight: 3, available: true, photo: null, photoChanged: false });

// The vendor's Prize Wheel: up to 6 food prizes (photo, name, what the customer gets, how
// often it comes up), a live preview, and Publish. Every jara becomes a spin while it is live.
export function VendorWheelPanel({ slug, character }: { slug: string; character?: CharacterT | null }) {
  const [wheel, setWheel] = useState<VendorWheel | null>(null);
  const [failed, setFailed] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    wheelApi.vendor(slug).then(setWheel).catch(() => setFailed(true));
  }, [slug]);

  const run = async (job: () => Promise<VendorWheel>) => {
    setBusy(true);
    setError(null);
    try {
      setWheel(await job());
      return true;
    } catch (err) {
      setError((err as ApiError).message || 'That did not save. Check your network and try again.');
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (failed) return <div className="card-outline"><span className="eyebrow">PRIZE WHEEL</span><p className="error">Could not load your prize wheel.</p></div>;
  if (!wheel) return null;

  const available = wheel.items.filter((i) => i.available);
  const canPublish = available.length >= wheel.min_to_publish;

  const save = async () => {
    if (!draft || !draft.name.trim()) return;
    const body: ItemInput = {
      name: draft.name.trim(),
      prize: draft.prize.trim() || null,
      description: draft.description.trim() || null,
      weight: draft.weight,
      available: draft.available,
    };
    if (draft.photoChanged) body.photo = draft.photo;
    const ok = await run(() => (draft.id ? wheelApi.updateItem(slug, draft.id, body) : wheelApi.addItem(slug, body)));
    if (ok) setDraft(null);
  };

  const edit = (i: WheelItemVendor) =>
    setDraft({ id: i.id, name: i.name, prize: i.prize ?? '', description: i.description ?? '', weight: (i.weight as Weight) ?? 3, available: i.available, photo: i.photo ? photoUrl(i.photo) : null, photoChanged: false });

  return (
    <section className="hero vendor-wheel" aria-labelledby={`vw-${slug}`}>
      <div className="row" style={{ alignItems: 'center' }}>
        <span id={`vw-${slug}`} className="eyebrow">PRIZE WHEEL · JARA BECOMES A SPIN</span>
        <span className={`vw-status ${wheel.enabled ? 'live' : ''}`}>{wheel.enabled ? 'Live' : 'Draft'}</span>
      </div>

      <div className="vw-grid">
        <div className="vw-preview">
          {available.length >= 2 ? (
            <Wheel slices={available} character={character} size={220} idle={wheel.enabled} />
          ) : (
            <div className="vw-empty-wheel">
              <span style={{ fontSize: 44 }} aria-hidden="true">🎡</span>
              <span className="note">Add {Math.max(0, 2 - available.length)} more {available.length === 1 ? 'prize' : 'prizes'} to see your wheel.</span>
            </div>
          )}
          {wheel.enabled && <span className="note" style={{ textAlign: 'center' }}>{wheel.stats.spins} {wheel.stats.spins === 1 ? 'spin' : 'spins'} · {wheel.stats.given} {wheel.stats.given === 1 ? 'prize' : 'prizes'} given</span>}
        </div>

        <div className="vw-list">
          {wheel.items.length === 0 && !draft && (
            <span className="note" style={{ fontSize: 15 }}>
              On plate 6, customers spin your wheel and win one of your foods. Add up to {wheel.max_items}: snap a photo, give it a name and say what they win.
            </span>
          )}
          {wheel.items.map((i) => (
            <div key={i.id} className={`vw-item${i.available ? '' : ' off'}`}>
              {i.photo ? <img src={photoUrl(i.photo)} alt="" className="wheel-thumb" /> : <span className="wheel-thumb wheel-thumb-empty" aria-hidden="true">🍲</span>}
              <span className="vw-item-text">
                <strong>{i.name}</strong>
                <span className="note">{i.prize || 'Free'} · {CHANCES.find((c) => c.weight === i.weight)?.label ?? 'Sometimes'}{i.available ? '' : ' · finished today'}</span>
              </span>
              <button type="button" className="vw-small" onClick={() => edit(i)} disabled={busy}>Edit</button>
            </div>
          ))}

          {draft ? (
            <ItemEditor
              draft={draft}
              busy={busy}
              onChange={setDraft}
              onSave={save}
              onCancel={() => { setDraft(null); setError(null); }}
              onRemove={draft.id ? async () => { if (await run(() => wheelApi.removeItem(slug, draft.id!))) setDraft(null); } : undefined}
            />
          ) : (
            wheel.items.length < wheel.max_items && (
              <button type="button" className="btn btn-outline vw-add" onClick={() => setDraft(emptyDraft())} disabled={busy}>
                + Add a prize ({wheel.items.length}/{wheel.max_items})
              </button>
            )
          )}
          {error && <span className="error" role="alert">{error}</span>}
        </div>
      </div>

      {!draft && (
        <div className="vw-publish">
          {wheel.enabled ? (
            <>
              <span style={{ fontWeight: 700 }}>Your wheel is live. Every new jara is a spin. Check prize codes in “Check a jara code” above.</span>
              <button type="button" className="btn btn-outline vw-publish-btn" disabled={busy} onClick={() => run(() => wheelApi.publish(slug, false))}>Pause wheel</button>
            </>
          ) : (
            <>
              <span className="note" style={{ fontSize: 14 }}>
                {canPublish ? 'Happy with the preview? Publish it and customers spin on their next jara.' : `Add at least ${wheel.min_to_publish} prizes to publish.`}
              </span>
              <button type="button" className="btn vw-publish-btn" disabled={busy || !canPublish} onClick={() => run(() => wheelApi.publish(slug, true))}>Publish wheel</button>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function ItemEditor({ draft, busy, onChange, onSave, onCancel, onRemove }: {
  draft: Draft; busy: boolean; onChange: (d: Draft) => void; onSave: () => void; onCancel: () => void; onRemove?: () => void;
}) {
  const camera = useRef<HTMLInputElement>(null);
  const files = useRef<HTMLInputElement>(null);
  const [shrinking, setShrinking] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const set = (patch: Partial<Draft>) => onChange({ ...draft, ...patch });

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setShrinking(true);
    setPhotoError(null);
    try {
      set({ photo: await shrinkPhoto(file, { maxEdge: 800, maxBytes: 500 * 1024 }), photoChanged: true });
    } catch (err) {
      setPhotoError((err as Error).message || 'That photo could not be used. Try another one.');
    } finally {
      setShrinking(false);
    }
  };

  return (
    <form className="vw-editor" onSubmit={(e) => { e.preventDefault(); onSave(); }}>
      <span className="eyebrow">{draft.id ? 'EDIT PRIZE' : 'NEW PRIZE'}</span>
      <div className="vw-photo">
        {draft.photo ? <img src={draft.photo} alt="The food" /> : <span aria-hidden="true">🍲</span>}
        {shrinking && <span className="vw-photo-busy">Getting it ready…</span>}
      </div>
      <div className="vw-photo-actions">
        <button type="button" className="vw-small" onClick={() => camera.current?.click()} disabled={shrinking}>📷 Take photo</button>
        <button type="button" className="vw-small" onClick={() => files.current?.click()} disabled={shrinking}>🖼️ Choose photo</button>
        {draft.photo && <button type="button" className="vw-small ghost" onClick={() => set({ photo: null, photoChanged: true })}>Remove photo</button>}
      </div>
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ''; }} />
      <input ref={files} type="file" accept="image/*" hidden onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ''; }} />
      {photoError && <span className="error">{photoError}</span>}

      <label className="field">Food name
        <input className="input" required maxLength={40} value={draft.name} placeholder="Jollof rice" onChange={(e) => set({ name: e.target.value })} />
      </label>
      <label className="field">What they win
        <input className="input" maxLength={60} value={draft.prize} placeholder="A free plate of jollof" onChange={(e) => set({ prize: e.target.value })} />
      </label>
      <label className="field">Short description <span className="note">(optional)</span>
        <input className="input" maxLength={120} value={draft.description} placeholder="Smoky party jollof with plantain" onChange={(e) => set({ description: e.target.value })} />
      </label>

      <fieldset className="vw-chance">
        <legend>How often it comes up</legend>
        {CHANCES.map((c) => (
          <label key={c.weight} className={draft.weight === c.weight ? 'on' : undefined}>
            <input type="radio" name="weight" checked={draft.weight === c.weight} onChange={() => set({ weight: c.weight })} />
            <strong>{c.label}</strong>
            <span>{c.hint}</span>
          </label>
        ))}
      </fieldset>
      <label className="vw-available">
        <input type="checkbox" checked={draft.available} onChange={(e) => set({ available: e.target.checked })} />
        Available today (untick when this food is finished)
      </label>

      <div className="vw-editor-actions">
        <button type="submit" className="btn" disabled={busy || shrinking || !draft.name.trim()}>{busy ? 'Saving…' : 'Save prize'}</button>
        <button type="button" className="btn btn-outline" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
      {onRemove && <button type="button" className="link-btn" style={{ alignSelf: 'center', color: 'var(--pepper)' }} onClick={onRemove} disabled={busy}>Remove this prize</button>}
    </form>
  );
}
