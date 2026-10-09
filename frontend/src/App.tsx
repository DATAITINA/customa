import { useEffect, useState } from 'react';
import { Logo } from './components/Logo';
import { CustomerPage } from './pages/CustomerPage';
import { ChatPage } from './pages/ChatPage';
import { VendorPage } from './pages/VendorPage';
import { QrPage } from './pages/QrPage';
import { Character } from './components/Character';

// A tiny router: three kinds of page, no library needed.
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

  if (parts[0] === 's' && parts[1]) {
    return parts[2] === 'chat' ? <ChatPage slug={parts[1]} /> : <CustomerPage slug={parts[1]} />;
  }
  if (parts[0] === 'qr' && parts[1]) return <QrPage slug={parts[1]} />;
  if (parts[0] === 'vendor') return <VendorPage />;

  return (
    <main className="qr-sign">
      <Logo size={42} />
      <Character body="pepper" color="pepper" accessory="headwrap" expression="excited" pose="wave" size={200} />
      <h1 className="display" style={{ fontSize: 44 }}>A FRIENDLY FACE FOR EVERY FOOD STAND</h1>
      <p className="note" style={{ maxWidth: 360, fontSize: 16 }}>
        Customers scan a QR code, the stand's character remembers them, and every 6th plate earns a jara.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 340 }}>
        <Link to="/s/iya-bisi-demo" className="btn">Try the demo stand</Link>
        <Link to="/vendor" className="btn btn-outline">I'm a vendor</Link>
      </div>
    </main>
  );
}
