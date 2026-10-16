import { Suspense, lazy, useEffect, useState } from 'react';
import { Logo } from './components/Logo';
import { CustomerPage } from './pages/CustomerPage';
import { Character } from './components/Character';
import { CharacterLoader } from './components/Loading';

// The customer's stand page loads first and fast; the rest loads only when opened.
const ChatPage = lazy(() => import('./pages/ChatPage').then((m) => ({ default: m.ChatPage })));
const VendorPage = lazy(() => import('./pages/VendorPage').then((m) => ({ default: m.VendorPage })));
const QrPage = lazy(() => import('./pages/QrPage').then((m) => ({ default: m.QrPage })));
const PlayPage = lazy(() => import('./features/games/PlayPage').then((m) => ({ default: m.PlayPage })));
const PaidPage = lazy(() => import('./features/payments/PaidPage').then((m) => ({ default: m.PaidPage })));
const WheelPage = lazy(() => import('./features/prizeWheel/WheelPage').then((m) => ({ default: m.WheelPage })));
const GoogleReturnPage = lazy(() => import('./features/googleSignIn/GoogleSignIn').then((m) => ({ default: m.GoogleReturnPage })));

// A tiny router: a few kinds of page, no library needed.
export function navigate(path: string) {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.scrollTo(0, 0);
}

export function Link({ to, className, children }: { to: string; className?: string; children: React.ReactNode }) {
  return (
    <a
      href={to}
      className={className}
      onClick={(e) => {
        e.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}

// The last stand page this phone opened. The installed app (Home Screen) goes back there
// instead of the homepage when it starts at "/".
const LAST_STAND = 'customa:last-stand';
export function rememberStand(slug: string) {
  try { localStorage.setItem(LAST_STAND, slug); } catch { /* not kept */ }
}
function lastStand(): string | null {
  try { return localStorage.getItem(LAST_STAND); } catch { return null; }
}
function isInstalledApp(): boolean {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

// Before the first render, so the homepage never flashes: an installed app (or one started
// from the old start URL /?app=1) that opens on "/" goes straight back to its stand.
if (window.location.pathname === '/') {
  const fromApp = new URLSearchParams(window.location.search).get('app') === '1' || isInstalledApp();
  const last = lastStand();
  if (fromApp && last) window.history.replaceState({}, '', `/s/${last}`);
}

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  return path;
}

export function App() {
  const path = usePath();
  const parts = path.split('/').filter(Boolean);
  return <Suspense fallback={<main className="phone"><CharacterLoader /></main>}>{route(parts)}</Suspense>;
}

function route(parts: string[]) {
  if (parts[0] === 's' && parts[1]) {
    if (parts[2] === 'chat') return <ChatPage slug={parts[1]} />;
    if (parts[2] === 'play') return <PlayPage slug={parts[1]} />;
    if (parts[2] === 'wheel') return <WheelPage slug={parts[1]} />;
    if (parts[2] === 'paid') return <PaidPage slug={parts[1]} />;
    return <CustomerPage slug={parts[1]} />;
  }
  if (parts[0] === 'qr' && parts[1]) return <QrPage slug={parts[1]} />;
  if (parts[0] === 'vendor' && parts[1] === 'google') return <GoogleReturnPage />;
  if (parts[0] === 'vendor') return <VendorPage />;
  return <Home />;
}

function Home() {
  const last = lastStand();
  return (
    <main className="qr-sign home page-in">
      <Logo size={42} />
      <Character body="pepper" color="pepper" accessory="headwrap" expression="excited" pose="wave" size={200} react follow />
      <h1 className="display" style={{ fontSize: '2.75rem' }}>A FRIENDLY FACE FOR EVERY FOOD STAND</h1>
      <p className="note" style={{ maxWidth: 360, fontSize: '1rem' }}>
        Customers scan a QR code, the stand's character remembers them, and every 6th plate earns a jara.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 340 }}>
        {last && <Link to={`/s/${last}`} className="btn">Back to my food spot</Link>}
        <div className="home-scan">
          <strong>Hungry?</strong> Scan the Customa QR code at your food spot to start your card.
        </div>
        <Link to="/vendor" className={last ? 'btn btn-outline' : 'btn'}>I'm a vendor</Link>
      </div>
    </main>
  );
}
