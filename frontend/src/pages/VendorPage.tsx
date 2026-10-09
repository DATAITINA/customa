import { useEffect, useRef, useState } from 'react';
import { Logo } from '../components/Logo';
import { useAuth } from '@msflib/react-auth';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type ApiError, type Character as CharacterT, type StandSummary } from '../api';
import { Character, PRESETS } from '../components/Character';
import { FoodStamp } from '../components/FoodStamp';
import { StandPhoto } from '../components/StandPhoto';
import { Link } from '../App';

export function VendorPage() {
  const { status } = useAuth();
  return (
    <main className="vendor">
      <VendorTop />
      {status === 'loading' && <p className="note">Loading…</p>}
      {status === 'unauthenticated' && <SignIn />}
      {status === 'authenticated' && <VendorHome />}
    </main>
  );
}

function VendorTop() {
  const { status, me, logout } = useAuth();
  const qc = useQueryClient();
  return (
    <header className="vendor-top">
      <Link to="/" className="logo-link"><Logo size={26} /></Link>
      {status !== 'authenticated' && <FoodStamp />}
      {status === 'authenticated' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{me?.email}</span>
          <button className="link-btn" onClick={async () => { try { await logout(); } finally { qc.clear(); } }}>Sign out</button>
        </div>
      )}
    </header>
  );
}

// --- Sign in / register (MSFLib auth: POST /login, POST /open) -------------

function SignIn() {
  const { login, register, loading } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  return (
    <div style={{ maxWidth: 420, margin: '24px auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Character body="pepper" color="pepper" accessory="chef" expression="happy" pose="wave" size={150} />
      <h1 className="display" style={{ fontSize: 40 }}>{mode === 'login' ? 'VENDOR SIGN IN' : 'START YOUR STAND'}</h1>
      <form
        className="stack"
        style={{ padding: 0, gap: 14 }}
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            if (mode === 'register') await register({ email, password });
            await login({ email, password });
          } catch (err) {
            setError((err as ApiError).message ?? 'Could not sign in');
          }
        }}
      >
        <label className="field">Email
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label className="field">Password
          <input className="input" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" type="submit" disabled={loading.login || loading.register}>
          {mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>
      <button className="link-btn" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? 'New vendor? Create an account' : 'Have an account? Sign in'}
      </button>
    </div>
  );
}

// --- Home: create a stand, or show its dashboard ---------------------------

function VendorHome() {
  const stands = useQuery({ queryKey: ['stands', 'mine'], queryFn: api.myStands });
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (stands.isLoading) return <p className="note">Loading your stands…</p>;
  if (stands.isError) return <p className="error">Could not load your stands.</p>;
  const list = stands.data ?? [];
  if (creating || list.length === 0) {
    return <StandSetup onCreated={(s) => { setCreating(false); setSelected(s.slug); stands.refetch(); }} />;
  }
  const slug = selected ?? list[0].slug;
  return (
    <>
      {list.length > 1 && (
        <div className="seg" style={{ marginBottom: 12 }}>
          {list.map((s) => (
            <button key={s.slug} aria-pressed={s.slug === slug} onClick={() => setSelected(s.slug)}>{s.name}</button>
          ))}
        </div>
      )}
      <Dashboard slug={slug} onNewStand={() => setCreating(true)} />
    </>
  );
}

// --- Stand setup: the vendor describes their stand, picks the character ----

const BODIES = ['pepper', 'cup', 'pot', 'blob'];
const ACCESSORIES = ['headwrap', 'chef', 'sunglasses', 'bowtie', 'none'];

function parseMenu(text: string) {
  // One item per line: "Jollof rice 1500"
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(/^(.*?)[\s,:-]+₦?\s*([\d,]+)\s*$/);
      return m ? { item: m[1].trim(), price: Number(m[2].replace(/,/g, '')) } : { item: line, price: 0 };
    });
}

function StandSetup({ onCreated }: { onCreated: (s: StandSummary) => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [menuText, setMenuText] = useState('');
  const [char, setChar] = useState<Partial<CharacterT>>({ name: '', body: 'pepper', color: 'pepper', accessory: 'headwrap', greeting: '' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [suggesting, setSuggesting] = useState(false);

  const suggest = async () => {
    if (!description.trim()) return;
    setSuggesting(true);
    try {
      const s = await api.suggestCharacter(`${name}. ${description}`);
      setChar((c) => ({ ...c, ...s }));
    } catch {
      setError('Could not suggest a character right now. Pick one below.');
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="grid-2" style={{ alignItems: 'start' }}>
      <form
        className="stack"
        style={{ padding: 0, gap: 14 }}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const stand = await api.createStand({
              name,
              description,
              character: {
                name: char.name || `${name.split(' ')[0]} Buddy`,
                body: char.body, color: char.color, accessory: char.accessory,
                greeting: char.greeting || `Welcome to ${name}!`,
                ...(char.personality ? { personality: char.personality } : {}),
                menu: parseMenu(menuText),
              },
            });
            onCreated(stand);
          } catch (err) {
            setError((err as ApiError).message ?? 'Could not create the stand');
          } finally {
            setBusy(false);
          }
        }}
      >
        <h1 className="display" style={{ fontSize: 40 }}>SET UP YOUR STAND</h1>
        <label className="field">Stand name
          <input className="input" required minLength={2} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Mama Ekaette's Kitchen" />
        </label>
        <label className="field">Describe your stand and food in your own words
          <textarea className="input" maxLength={200} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Spicy afang soup and fufu, near the market gate. Customers call me Mama." />
        </label>
        <div className="soon" aria-disabled="true">
          <button type="button" className="soon-mic" disabled aria-label="Voice note, coming soon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="9" y="2" width="6" height="12" rx="3" /><path d="M19 10v1a7 7 0 0 1-14 0v-1" /><path d="M12 18v4" />
            </svg>
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexGrow: 1, minWidth: 0 }}>
            <span className="soon-badge" style={{ alignSelf: 'flex-start' }}>COMING SOON</span>
            <span style={{ fontWeight: 800, fontSize: 15 }}>Rather talk? Send a voice note</span>
            <span className="note">English or Nigerian Pidgin. We turn it into your stand's words.</span>
          </div>
        </div>
        <StandPhoto />
        <button type="button" className="btn btn-outline" onClick={suggest} disabled={suggesting || !description.trim()}>
          {suggesting ? 'Thinking…' : 'Suggest a character from my words'}
        </button>
        <label className="field">Menu, one item per line with the price
          <textarea className="input" value={menuText} onChange={(e) => setMenuText(e.target.value)} placeholder={'Afang soup and fufu 2000\nPepper soup 1500'} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create my stand'}</button>
      </form>

      <section className="hero" style={{ margin: 0, padding: 20, gap: 14 }} aria-label="Your character">
        <div className="bubble">{char.greeting || (name ? `Welcome to ${name}!` : 'Hello! I go welcome your customers.')}</div>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Character body={char.body} color={char.color} accessory={char.accessory} expression="excited" pose="wave" size={200} />
        </div>
        <label className="field">Character name
          <input className="input" value={char.name ?? ''} onChange={(e) => setChar({ ...char, name: e.target.value })} placeholder="e.g. Ekaette Pot" />
        </label>
        <label className="field">Greeting
          <input className="input" value={char.greeting ?? ''} onChange={(e) => setChar({ ...char, greeting: e.target.value })} placeholder="Welcome! Soup dey hot." />
        </label>
        <span className="eyebrow">BODY</span>
        <div className="seg">
          {BODIES.map((b) => <button type="button" key={b} aria-pressed={char.body === b} onClick={() => setChar({ ...char, body: b })}>{b}</button>)}
        </div>
        <span className="eyebrow">COLOUR</span>
        <div className="swatches">
          {Object.entries(PRESETS).map(([k, v]) => (
            <button type="button" key={k} className="swatch" aria-label={k} aria-pressed={char.color === k} style={{ background: v.fill }} onClick={() => setChar({ ...char, color: k })} />
          ))}
        </div>
        <span className="eyebrow">ACCESSORY</span>
        <div className="seg">
          {ACCESSORIES.map((a) => <button type="button" key={a} aria-pressed={char.accessory === a} onClick={() => setChar({ ...char, accessory: a })}>{a}</button>)}
        </div>
      </section>
    </div>
  );
}

// --- Live dashboard (refreshes every 5 seconds) -----------------------------

function Dashboard({ slug, onNewStand }: { slug: string; onNewStand: () => void }) {
  const q = useQuery({ queryKey: ['dashboard', slug], queryFn: () => api.dashboard(slug), refetchInterval: 5000 });
  const seen = useRef<Set<number> | null>(null);
  const [fresh, setFresh] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!q.data) return;
    const ids = q.data.recent_visits.map((v) => v.id);
    if (seen.current) {
      const added = ids.filter((id) => !seen.current!.has(id));
      if (added.length) setFresh(new Set(added));
    }
    seen.current = new Set(ids);
  }, [q.data]);

  if (q.isLoading) return <p className="note">Loading dashboard…</p>;
  if (q.isError || !q.data) return <p className="error">Could not load the dashboard.</p>;
  const d = q.data;
  const ch = d.stand.character;
  const stats = [
    { label: 'PLATES TODAY', value: d.stats.plates_today },
    { label: 'CUSTOMERS', value: d.stats.customers },
    { label: 'CAME BACK', value: d.stats.returning_customers },
    { label: 'JARA EARNED', value: d.stats.jara_issued },
    { label: 'RATED GOOD', value: d.stats.average_rating == null ? '–' : `${Math.round(((d.stats.average_rating - 1) / 4) * 100)}%` },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {ch && <Character body={ch.body} color={ch.color} accessory={ch.accessory} pose="idle" size={64} />}
          <div>
            <h1 className="display" style={{ fontSize: 34 }}>{d.stand.name}</h1>
            <span className="live">Live, updates every 5 seconds</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/qr/${slug}`} className="btn" >Show QR code</Link>
          <Link to={`/s/${slug}`} className="btn btn-outline">Customer page</Link>
        </div>
      </div>
      <div className="stats">
        {stats.map((s) => (
          <div key={s.label} className="stat">
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="table-wrap">
        <table>
          <caption style={{ textAlign: 'left', padding: '14px 16px 0', fontWeight: 800 }}>Recent plates</caption>
          <thead>
            <tr><th>Customer</th><th>Plate</th><th>Rating</th><th>Time</th></tr>
          </thead>
          <tbody>
            {d.recent_visits.length === 0 && (
              <tr><td colSpan={4} className="note">No plates yet. Show your QR code to your first customer.</td></tr>
            )}
            {d.recent_visits.map((v) => (
              <tr key={v.id} className={fresh.has(v.id) ? 'fresh' : undefined}>
                <td>{v.name}</td>
                <td>{v.plate_number === d.plates_for_jara ? `${v.plate_number}/${d.plates_for_jara} JARA` : `${v.plate_number}/${d.plates_for_jara}`}</td>
                <td>{v.stars == null ? '–' : v.stars >= 4 ? 'Good' : 'Not good'}</td>
                <td>{new Date(v.at + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid-2">
        <OpenJara slug={slug} items={d.open_jara} onChange={() => q.refetch()} />
        <div className="card-outline">
          <span className="eyebrow">WHAT CUSTOMERS ASKED {ch?.name.split(' ')[0].toUpperCase() ?? ''}</span>
          {d.recent_questions.length === 0 && <span className="note">No questions yet.</span>}
          {d.recent_questions.map((m) => (
            <div key={m.id} className="row" style={{ fontSize: 15 }}>
              <span style={{ fontWeight: 600 }}>"{m.question}"</span>
              <span className="note" style={{ whiteSpace: 'nowrap' }}>{m.who}</span>
            </div>
          ))}
        </div>
      </div>
      <button className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={onNewStand}>Add another stand</button>
    </div>
  );
}

// Jara codes waiting to be given out. Redeeming marks the code used (works once).
function OpenJara({ slug, items, onChange }: { slug: string; items: { code: string; name: string }[]; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  return (
    <div className="card-outline">
      <span className="eyebrow">JARA TO GIVE OUT</span>
      {items.length === 0 && <span className="note">No jara waiting.</span>}
      {items.map((j) => (
        <div key={j.code} className="row" style={{ alignItems: 'center' }}>
          <span><strong style={{ fontFamily: 'var(--display)', fontSize: 20, letterSpacing: '0.04em' }}>{j.code}</strong> <span className="note">{j.name}</span></span>
          <button className="btn" style={{ width: 'auto', height: 40, padding: '0 16px', fontSize: 14 }} disabled={busy === j.code}
            onClick={async () => { setBusy(j.code); try { await api.redeemJara(slug, j.code); onChange(); } finally { setBusy(null); } }}>
            Mark as given
          </button>
        </div>
      ))}
    </div>
  );
}
