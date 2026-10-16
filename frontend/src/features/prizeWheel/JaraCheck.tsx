import { useEffect, useRef, useState } from 'react';
import { api, photoUrl, type ApiError } from '../../api';
import { wheelApi, type CodeCheck } from './wheelApi';
import './wheel.css';

const day = (iso?: string | null) => (iso ? new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleDateString([], { day: 'numeric', month: 'short' }) : '');

const STATUS: Record<CodeCheck['status'], { tone: string; title: string }> = {
  valid: { tone: 'ok', title: 'Valid. Give it!' },
  redeemed: { tone: 'used', title: 'Already given' },
  expired: { tone: 'warn', title: 'This prize expired' },
  not_spun: { tone: 'info', title: 'Not spun yet' },
  other_stand: { tone: 'bad', title: 'From another stand' },
  unknown: { tone: 'bad', title: 'No jara with this code' },
};

type Detector = { detect: (source: CanvasImageSource) => Promise<{ rawValue: string }[]> };

// The vendor checks a jara code the customer shows: type it, or scan its QR code with the
// camera (where the phone can). It says what the code is worth, then "Give it" marks it used.
export function JaraCheckPanel({ slug, onGiven }: { slug: string; onGiven: () => void }) {
  const [code, setCode] = useState('');
  const [check, setCheck] = useState<CodeCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [given, setGiven] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const canScan = typeof window !== 'undefined' && 'BarcodeDetector' in window && !!navigator.mediaDevices?.getUserMedia;

  const look = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setGiven(null);
    try {
      setCheck(await wheelApi.check(slug, text));
    } catch (err) {
      setError((err as ApiError).message || 'Could not check the code. Check your network and try again.');
    } finally {
      setBusy(false);
    }
  };

  const give = async () => {
    if (!check) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.redeemJara(slug, check.code);
      setGiven(r.prize ? `Given: ${r.prize}. Enjoy the smile! 😄` : 'Given: a free extra portion.');
      setCheck(await wheelApi.check(slug, check.code));
      onGiven();
    } catch (err) {
      setError((err as ApiError).message || 'Could not mark it as given. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const s = check ? STATUS[check.status] : null;
  return (
    <section className="card-outline jara-check">
      <span className="eyebrow">CHECK A JARA CODE</span>
      <form className="jara-check-form" onSubmit={(e) => { e.preventDefault(); void look(code); }}>
        <label htmlFor={`jc-${slug}`} className="visually-hidden">Jara code</label>
        <input id={`jc-${slug}`} className="input" value={code} placeholder="JARA-XXXX-XXXX" autoCapitalize="characters" autoComplete="off"
          onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={20} />
        <button type="submit" className="btn" disabled={busy || !code.trim()}>Check</button>
        {canScan && <button type="button" className="btn btn-outline" onClick={() => setScanning(true)} disabled={busy}>Scan</button>}
      </form>
      {error && <span className="error" role="alert">{error}</span>}

      {check && s && (
        <div className={`jara-result ${s.tone}`} role="status">
          <strong className="jara-result-title">{s.title}</strong>
          {check.prize ? (
            <div className="jara-result-prize">
              {check.prize.photo ? <img src={photoUrl(check.prize.photo)} alt="" className="wheel-thumb big" /> : <span className="wheel-thumb big wheel-thumb-empty" aria-hidden="true">🍲</span>}
              <span>
                <strong style={{ fontSize: '1.125rem' }}>{check.prize.name}</strong>
                {check.prize.prize && <span style={{ display: 'block', fontWeight: 700 }}>{check.prize.prize}</span>}
                <span className="note">
                  {check.customer} · spun {day(check.prize.spun_at)}
                  {check.prize.redeemed_at ? ` · given ${day(check.prize.redeemed_at)}` : ` · valid until ${day(check.prize.expires_at)}`}
                </span>
              </span>
            </div>
          ) : check.status === 'valid' || check.status === 'redeemed' || check.status === 'not_spun' ? (
            <span>{check.status === 'not_spun' ? `${check.customer} has a jara but has not spun your wheel yet. Ask them to tap "Spin" on their phone.` : `A free extra portion · ${check.customer}`}</span>
          ) : (
            <span className="note">{check.status === 'other_stand' ? 'This code belongs to another stand. It cannot be given here.' : 'Check the letters, or ask the customer to show the code again.'}</span>
          )}
          <span className="note">{check.code}</span>
          {check.status === 'valid' && (
            <button type="button" className="btn" disabled={busy} onClick={give}>{busy ? 'Saving…' : check.prize ? 'Give prize & mark as used' : 'Give jara & mark as used'}</button>
          )}
          {check.status === 'not_spun' && (
            <button type="button" className="link-btn" disabled={busy} onClick={give}>Give a regular free portion instead</button>
          )}
        </div>
      )}
      {given && <span className="jara-given" role="status">✅ {given}</span>}
      {scanning && <Scanner onCode={(text) => { setScanning(false); setCode(text); void look(text); }} onClose={() => setScanning(false)} />}
    </section>
  );
}

// Camera QR scan with the browser's own BarcodeDetector (Chrome on Android). No library.
function Scanner({ onCode, onClose }: { onCode: (code: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const found = useRef(onCode);
  found.current = onCode;

  useEffect(() => {
    let stream: MediaStream | null = null;
    let stop = false;
    (async () => {
      try {
        const Ctor = (window as unknown as { BarcodeDetector: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
        const detector = new Ctor({ formats: ['qr_code'] });
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        if (!video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        while (!stop) {
          const codes = await detector.detect(video.current).catch(() => []);
          const hit = codes.find((f) => /JARA/i.test(f.rawValue));
          if (hit) { found.current(hit.rawValue.trim().toUpperCase()); return; }
          await new Promise((ok) => setTimeout(ok, 250));
        }
      } catch {
        setFailed(true);
      }
    })();
    return () => { stop = true; stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  return (
    <div className="scan-overlay" role="dialog" aria-modal="true" aria-label="Scan a jara QR code">
      <div className="scan-box">
        {failed ? <p className="error">The camera could not start. Type the code instead.</p> : <video ref={video} playsInline muted />}
        <span className="note" style={{ color: '#fff' }}>Point the camera at the QR code on the customer's phone.</span>
        <button type="button" className="btn btn-outline" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
