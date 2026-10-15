import { useEffect, useRef, useState } from 'react';

// "Snap your stand": opens the phone's rear camera (or the photo picker on a laptop)
// and shows the photo inside a viewfinder frame, with retake and remove.
// initialUrl: the stand's saved photo, if any. busy: the photo is being saved.
export function StandPhoto({
  onChange, initialUrl = null, busy = false,
}: { onChange?: (file: File | null) => void; initialUrl?: string | null; busy?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [local, setLocal] = useState<string | null>(null);
  const [removed, setRemoved] = useState(false);

  useEffect(() => () => { if (local) URL.revokeObjectURL(local); }, [local]);

  const url = local ?? (removed ? null : initialUrl);
  const pick = () => input.current?.click();
  const set = (file: File | null) => {
    if (local) URL.revokeObjectURL(local);
    setLocal(file ? URL.createObjectURL(file) : null);
    setRemoved(!file);
    onChange?.(file);
  };

  return (
    <div className="field">
      <span>Photo of your stand <span style={{ fontWeight: 500, color: 'var(--muted)' }}>(optional)</span></span>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => { set(e.target.files?.[0] ?? null); e.target.value = ''; }}
      />

      {!url ? (
        <button type="button" className="viewfinder" onClick={pick} disabled={busy}>
          <span className="vf-corner tl" /><span className="vf-corner tr" />
          <span className="vf-corner bl" /><span className="vf-corner br" />
          <span className="vf-shutter" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
              <circle cx="12" cy="13" r="3" />
            </svg>
          </span>
          <span style={{ fontSize: 17, fontWeight: 800 }}>Snap your stand</span>
          <span className="note" style={{ maxWidth: 240 }}>Get the food and your sign in the frame. Customers see it on your page.</span>
        </button>
      ) : (
        <div className={`photo-preview${busy ? ' photo-busy' : ''}`}>
          <img src={url} alt="Your stand" decoding="async" />
          <span className="photo-chip" role="status">
            {busy ? (
              'Saving…'
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
                Looks delicious
              </>
            )}
          </span>
          <div className="photo-actions">
            <button type="button" className="photo-btn" onClick={pick} disabled={busy}>Retake</button>
            <button type="button" className="photo-btn photo-btn-ghost" onClick={() => set(null)} disabled={busy}>Remove</button>
          </div>
        </div>
      )}
    </div>
  );
}
