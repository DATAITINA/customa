import { useEffect, useState } from 'react';
import { Logo } from '../components/Logo';
import { QRCodeSVG } from 'qrcode.react';
import { api, type StandPublic } from '../api';
import { Character } from '../components/Character';
import { Link } from '../App';
import { LastPlatesBanner } from '../components/LastPlates';

// The sign a vendor puts up (or shows on a screen): scan to be welcomed.
export function QrPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  useEffect(() => { api.stand(slug).then(setStand).catch(() => setStand(null)); }, [slug]);
  const url = `${window.location.origin}/s/${slug}`;
  const ch = stand?.character;
  return (
    <main className="qr-sign">
      <Logo size={36} />
      <h1 className="display" style={{ fontSize: 46 }}>{stand?.stand.name.replace(' (Demo)', '') ?? ' '}</h1>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="excited" pose="wave" size={180} />
        <div className="qr-box">
          <QRCodeSVG value={url} size={260} level="M" marginSize={1} />
        </div>
      </div>
      <LastPlatesBanner lp={stand?.last_plates ?? null} big />
      <p style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Scan to say hi to {ch?.name ?? 'us'}</p>
      <p className="note" style={{ fontSize: 15 }}>Every visit counts a plate. Plate {stand?.plates_for_jara ?? 6} earns a jara.</p>
      <p style={{ fontWeight: 700, margin: 0, wordBreak: 'break-all' }}>{url.replace(/^https?:\/\//, '')}</p>
      <Link to="/vendor" className="link-btn">Back to dashboard</Link>
    </main>
  );
}
