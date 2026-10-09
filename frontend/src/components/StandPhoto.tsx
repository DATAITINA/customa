import { useEffect, useRef, useState } from 'react';

// "Snap your stand": opens the phone's rear camera (or the photo picker on a laptop)
// and shows the photo inside a viewfinder frame, with retake and remove.
export function StandPhoto({ onChange }: { onChange?: (file: File | null) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const pick = () => input.current?.click();
  const set = (file: File | null) => {
    if (url) URL.revokeObjectURL(url);
    setUrl(file ? URL.createObjectURL(file) : null);
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
        <button type="button" className="viewfinder" onClick={pick}>
          <span className="vf-corner tl" /><span className="vf-corner tr" />
          <span className="vf-corner bl" /><span className="vf-corner br" />
          <span className="vf-shutter" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
              <circle cx="12" cy="13" r="3" />
            </svg>
          </span>
          <span style={{ fontSize: 17, fontWeight: 800 }}>Snap your stand</span>
          <span className="note" style={{ maxWidth: 240 }}>Get the food and your sign in the frame. Your character can match its colours.</span>
        </button>
      ) : (
        <div className="photo-preview">
          <img src={url} alt="Your stand" />
          <span className="photo-chip">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
            Looks delicious
          </span>
          <div className="photo-actions">
            <button type="button" className="photo-btn" onClick={pick}>Retake</button>
            <button type="button" className="photo-btn photo-btn-ghost" onClick={() => set(null)}>Remove</button>
          </div>
        </div>
      )}
    </div>
  );
}
