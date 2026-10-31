import { useEffect, useState } from 'react';
import { Logo } from '../components/Logo';
import { QRCodeSVG } from 'qrcode.react';
import { api, type StandPublic } from '../api';
import { Character } from '../components/Character';
import { Link } from '../App';
import { LastPlatesBanner } from '../components/LastPlates';
import { Skeleton } from '../components/Loading';

// The sign a vendor puts up (or shows on a screen): scan to be welcomed and count a plate.
// The code carries the stand's secret scan code (?s=), so only a real scan counts a plate.
// Only the stand's vendor can open this page.
export function QrPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [scan, setScan] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  const [confirmNew, setConfirmNew] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.stand(slug).then(setStand).catch(() => setStand(null)); }, [slug]);
  useEffect(() => {
    api.qrCode(slug).then((r) => setScan(r.scan)).catch(() => setDenied(true));
  }, [slug]);

  const makeNew = async () => {
    setBusy(true);
    try {
      setScan((await api.newQrCode(slug)).scan);
      setConfirmNew(false);
    } finally {
      setBusy(false);
    }
  };

  const url = `${window.location.origin}/s/${slug}`;
  const ch = stand?.character;

  if (denied) {
    return (
      <main className="qr-sign page-in">
        <Logo size={36} />
        <p style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0 }}>Only the vendor can show this QR code.</p>
        <p className="note">Sign in to your dashboard, then tap "Show QR code".</p>
        <div style={{ width: 280 }}><Link to="/vendor" className="btn">Go to dashboard</Link></div>
      </main>
    );
  }

  return (
    <main className="qr-sign page-in">
      <Logo size={36} />
      <h1 className="display" style={{ fontSize: '2.875rem' }}>{stand?.stand.name ?? ' '}</h1>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="excited" pose="wave" size={180} />
        <div className="qr-box">
          {scan ? <QRCodeSVG value={`${url}?s=${scan}`} size={260} level="M" marginSize={1} /> : <Skeleton h={260} w={260} r={8} />}
        </div>
      </div>
      <LastPlatesBanner lp={stand?.last_plates ?? null} big />
      <p style={{ fontSize: '1.375rem', fontWeight: 800, margin: 0 }}>Scan to say hi to {ch?.name ?? 'us'}</p>
      <p className="note" style={{ fontSize: '0.9375rem' }}>Every visit counts a plate. Plate {stand?.plates_for_jara ?? 6} earns a jara.</p>
      <div className="qr-tools">
        {confirmNew ? (
          <>
            <span style={{ fontWeight: 700 }}>Make a new QR code? Your old printed QR codes will stop counting plates.</span>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn" style={{ width: 'auto', padding: '0 20px' }} disabled={busy} onClick={makeNew}>{busy ? 'Making…' : 'Yes, new QR code'}</button>
              <button className="btn btn-outline" style={{ width: 'auto', padding: '0 20px' }} onClick={() => setConfirmNew(false)}>Keep this one</button>
            </div>
          </>
        ) : (
          <button className="link-btn" onClick={() => setConfirmNew(true)}>Someone copied your QR code? Make a new one</button>
        )}
      </div>
      <Link to="/vendor" className="link-btn">Back to dashboard</Link>
    </main>
  );
}
