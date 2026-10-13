import { useEffect, useRef, useState } from 'react';
import { Logo } from '../components/Logo';
import {
  api,
  captureScan,
  clearCustomerKey,
  getCustomerKey,
  getScan,
  markScanCounted,
  photoUrl,
  setStandManifest,
  setCustomerKey,
  type ApiError,
  type CountResult,
  type CustomerState,
  type StandPublic,
} from '../api';
import { Character, PRESETS } from '../components/Character';
import { Link, rememberStand } from '../App';
import { LastPlatesBanner } from '../components/LastPlates';
import { AjoCard } from '../features/plateAjo/CustomerAjo';
import { CrewCard } from '../features/lunchCrew/CustomerCrew';
import { AlertsCard } from '../features/alerts/CustomerAlerts';
import { CharacterLoader } from '../components/Loading';
import { DeleteMyData } from '../components/DeleteMyData';

type View =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'welcome' }
  // Not counted: no fresh scan of the stand's QR code (stale = the code was old or wrong).
  | { kind: 'scan'; stale?: boolean }
  | { kind: 'counted'; result: CountResult }
  | { kind: 'tooSoon'; secondsLeft: number; windowSeconds: number; plate: number; name: string | null }
  | { kind: 'jara'; result: CountResult }
  | { kind: 'deleted' };

const ChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
  </svg>
);
const ThumbUp = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7 10v12" />
    <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
  </svg>
);
const ThumbDown = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17 14V2" />
    <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79-1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
  </svg>
);
const Check = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

const naira = (n: number) => `₦${n.toLocaleString('en-NG')}`;

export function CustomerPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [view, setView] = useState<View>({ kind: 'loading' });
  // The latest we know about this customer (card, crew, unredeemed jara codes), from any response.
  const [me, setMeState] = useState<CustomerState | null>(null);
  // Bumped on every update of `me` (a plate counted here, a prepaid plate, a crew change), so
  // feature cards that show plate-related state (the crew card) re-read it.
  const [meVersion, setMeVersion] = useState(0);
  const setMe = (c: CustomerState | null) => {
    setMeState(c);
    setMeVersion((v) => v + 1);
  };
  const started = useRef(false);
  // A playful line after the customer taps the character; it fades back to the real message.
  const [tapLine, setTapLine] = useState<string | null>(null);
  useEffect(() => {
    if (!tapLine) return;
    const t = setTimeout(() => setTapLine(null), 2600);
    return () => clearTimeout(t);
  }, [tapLine]);
  // "Add to Home Screen" installs this stand with this customer's card (iPhone keeps a
  // Home Screen app's storage apart from Safari's).
  useEffect(() => { setStandManifest(slug, me?.key ?? getCustomerKey(slug)); }, [slug, me?.key]);

  // A plate counts only with the scan code from the stand's QR code (read in the effect below).
  const handleCount = async (body: { first_name?: string; consent: boolean }) => {
    const scan = getScan(slug);
    if (!scan) {
      setView({ kind: 'scan' });
      return;
    }
    try {
      const result = await api.countPlate(slug, { ...body, scan: scan.code });
      markScanCounted(slug);
      setCustomerKey(slug, result.customer.key);
      setMe(result.customer);
      setView(result.jara ? { kind: 'jara', result } : { kind: 'counted', result });
    } catch (err) {
      const e = err as ApiError;
      const detail = e.raw?.detail as
        | { seconds_left: number; customer: CustomerState; code?: string }
        | undefined;
      if (e.status === 403 && detail?.code === 'scan_required') {
        setView({ kind: 'scan', stale: true });
      } else if (e.status === 409 && detail) {
        if (detail.customer?.key) setMe(detail.customer);
        setView({ kind: 'tooSoon', secondsLeft: detail.seconds_left, windowSeconds: detail.customer.window_seconds ?? stand?.window_seconds ?? 0, plate: detail.customer.plate_number, name: detail.customer.first_name });
      } else if (e.status === 404) {
        // We had a key but the stand forgot us (data deleted): start fresh.
        clearCustomerKey(slug);
        setView({ kind: 'welcome' });
      } else {
        setView({ kind: 'error', message: e.message ?? 'Something went wrong' });
      }
    }
  };

  // After a plate is counted somewhere else (a prepaid Plate Ajo plate), re-read the stand
  // and show the card with the real time left. Read only: it never counts a plate itself.
  const refreshPlates = async () => {
    try {
      const s = await api.stand(slug);
      setStand(s);
      if (s.customer) setMe(s.customer);
      if (s.customer && (s.customer.seconds_left ?? 0) > 0) {
        setView({ kind: 'tooSoon', secondsLeft: s.customer.seconds_left ?? 0, windowSeconds: s.customer.window_seconds, plate: s.customer.plate_number, name: s.customer.first_name });
      }
    } catch {
      // Keep the current screen; the next scan shows the right state.
    }
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    captureScan(slug);
    rememberStand(slug);
    api
      .stand(slug)
      .then((s) => {
        setStand(s);
        if (s.customer) setMe(s.customer);
        const scan = getScan(slug);
        const freshScan = scan !== null && !scan.counted;
        if (s.customer && getCustomerKey(slug)) {
          // A new scan from a phone we already know is a new visit: count it straight away.
          // Without one (a bookmark, a refresh, the history) only show the card.
          if (freshScan) handleCount({ consent: true });
          else if ((s.customer.seconds_left ?? 0) > 0) {
            setView({ kind: 'tooSoon', secondsLeft: s.customer.seconds_left ?? 0, windowSeconds: s.customer.window_seconds, plate: s.customer.plate_number, name: s.customer.first_name });
          } else setView({ kind: 'scan' });
        } else setView(freshScan ? { kind: 'welcome' } : { kind: 'scan' });
      })
      .catch((err: ApiError) =>
        setView({ kind: 'error', message: err.status === 404 ? 'This stand does not exist.' : err.message }),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  if (view.kind === 'loading') return <Shell stand={stand}><CharacterLoader kind="card" character={stand?.character} /></Shell>;
  if (view.kind === 'error' || !stand) {
    return (
      <Shell stand={stand}>
        <div className="stack">
          <p className="error">{view.kind === 'error' ? view.message : 'Could not load this stand.'}</p>
          <button className="btn" onClick={() => window.location.reload()}>Try again</button>
        </div>
      </Shell>
    );
  }

  const ch = stand.character;
  const total = stand.plates_for_jara;
  // After joining, creating or leaving a crew: re-read which card this customer's plates go to.
  // Read only, and it keeps the current screen.
  const refreshMe = async () => {
    try {
      const s = await api.stand(slug);
      if (s.customer) setMe(s.customer);
    } catch {
      // The next scan shows the right card.
    }
  };
  // The return-visit features. Each card hides itself when the vendor has not turned it on.
  const featureCards = (
    <>
      <OpenJara codes={me?.open_jara ?? []} />
      {me && <AlertsCard slug={slug} stand={stand} />}
      <CrewCard slug={slug} stand={stand} onChange={refreshMe} refreshKey={meVersion} ownPlate={me?.own_plate_number ?? null} />
      <AjoCard slug={slug} stand={stand} onPlateCounted={refreshPlates} />
    </>
  );
  // The hero character reacts to a tap with a jump and a line, and its eyes follow the finger.
  const charProps = {
    body: ch?.body, color: ch?.color, accessory: ch?.accessory, react: true, follow: true,
    onTap: () => setTapLine(TAP_LINES[Math.floor(Math.random() * TAP_LINES.length)]),
  };
  const charName = ch?.name ?? 'your host';

  if (view.kind === 'jara') return <JaraScreen stand={stand} result={view.result} onDone={() => setView({ kind: 'counted', result: { ...view.result, jara: null } })} />;

  if (view.kind === 'deleted') {
    return (
      <Shell stand={stand}>
        <Hero tapLine={tapLine} bubble={`Done. I don forget you. Come back anytime!`}>
          <Character {...charProps} expression="happy" pose="idle" size={170} />
        </Hero>
        <div className="stack">
          <p className="note">Your name, plates and ratings at this stand are deleted.</p>
          <button className="btn" onClick={() => setView({ kind: 'welcome' })}>Start again</button>
        </div>
      </Shell>
    );
  }

  if (view.kind === 'welcome') {
    return (
      <Shell stand={stand}>
        <Hero tapLine={tapLine} bubble={`${ch?.greeting ?? 'Welcome!'} Wetin be your name?`}>
          <Character {...charProps} expression="excited" pose="wave" size={180} />
        </Hero>
        <WelcomeForm onSubmit={handleCount} />
      </Shell>
    );
  }

  if (view.kind === 'scan') {
    const known = me?.first_name ? `${me.first_name}! ` : '';
    const bubble = view.stale
      ? 'Hmm, that QR code is old. Scan the QR code at the stand to count your plate!'
      : me
        ? `${known}Welcome back! Scan the QR code at the stand to count today's plate.`
        : `${ch?.greeting ?? 'Welcome!'} Scan the QR code at the stand to count your first plate.`;
    return (
      <Shell stand={stand}>
        <Hero tapLine={tapLine} bubble={bubble}>
          <Character {...charProps} expression="happy" pose="wave" size={170} />
        </Hero>
        <div className="stack">
          <ScanHint charName={charName} />
          {me && (
            <>
              <PlateCard plate={me.plate_number} total={total} crewName={me.crew_name ?? null} windowSeconds={me.window_seconds} />
              {featureCards}
              <TalkAndPlay slug={slug} first={charName.split(' ')[0]} outline />
            </>
          )}
          <Menu items={ch?.menu ?? []} />
          {me && <DeleteMyData slug={slug} standName={stand.stand.name} plates={me?.own_plate_number ?? (me?.plate_number ?? 0) % total} total={total} me={me} onDeleted={() => { clearCustomerKey(slug); setMe(null); setView({ kind: 'deleted' }); }} />}
        </div>
      </Shell>
    );
  }

  if (view.kind === 'tooSoon') {
    return (
      <Shell stand={stand}>
        <TooSoon
          stand={stand}
          initialSeconds={view.secondsLeft}
          windowSeconds={view.windowSeconds}
          plate={me?.plate_number ?? view.plate}
          crewName={me?.crew_name ?? null}
          name={view.name}
          canCount={(() => { const sc = getScan(slug); return sc !== null && !sc.counted; })()}
          onReady={() => handleCount({ consent: true })}
          extras={featureCards}
        />
        <div className="stack">
          <DeleteMyData slug={slug} standName={stand.stand.name} plates={me?.own_plate_number ?? (me?.plate_number ?? 0) % total} total={total} me={me} onDeleted={() => { clearCustomerKey(slug); setMe(null); setView({ kind: 'deleted' }); }} />
        </div>
      </Shell>
    );
  }

  // Plate counted.
  const r = view.result;
  const name = r.customer.first_name;
  const left = total - r.plate_number;
  const crew = r.crew;
  // The crew this customer is in now: it can change on this screen (create, join, leave).
  const nowCrew = me ? me.crew_name ?? null : crew?.name ?? null;
  const ownPlate = me?.own_plate_number ?? r.plate_number % total;
  const hi = name ? name + '! ' : '';
  let bubble: string;
  if (crew && !nowCrew) {
    bubble = `You left ${crew.name}. Your own card continues from plate ${ownPlate} of ${total}.`;
  } else if (!crew && nowCrew) {
    bubble = `${hi}Plate ${r.plate_number} is saved on your own card, paused while you're in ${nowCrew}. Your next plates go on the crew card.`;
  } else if (crew && crew.jara_to && !crew.jara_to_me) {
    bubble = `Plate ${crew.plate_number} for ${crew.name}! This jara goes to ${crew.jara_to}. Your turn is coming.`;
  } else if (crew) {
    bubble = `${hi}Plate ${crew.plate_number} of ${crew.plates_for_jara} for ${crew.name}.`;
  } else if (left === 1) {
    // Almost there: people speed up when a reward is close, so make plate 5 feel exciting.
    bubble = `${hi}Plate ${r.plate_number} don land! Just ONE more plate and jara na yours! 🎉`;
  } else if (r.returning) {
    bubble = `${hi}Back again! Plate ${r.plate_number} of ${total}.`;
  } else {
    bubble = `${hi}Plate ${r.plate_number} don land. ${left} more and jara na yours.`;
  }
  // The card shown: the latest we know (it follows a crew joined or left on this screen).
  const cardPlate = me ? me.plate_number : r.plate_number;
  const cardCrew = me ? me.crew_name ?? null : crew?.name ?? null;

  return (
    <Shell stand={stand}>
      <Hero tapLine={tapLine} bubble={bubble} counted>
        <Character {...charProps} expression="excited" pose={r.returning ? 'wave' : 'hop'} size={180} />
      </Hero>
      <div className="stack">
        <PlateCard plate={cardPlate} total={total} crewName={cardCrew} windowSeconds={r.customer.window_seconds ?? stand.window_seconds} />
        {featureCards}
        <TalkAndPlay slug={slug} first={charName.split(' ')[0]} />
        <Rate slug={slug} visitId={r.visit_id} />
        <Menu items={ch?.menu ?? []} />
        <Goodbye name={name} plate={r.plate_number} />
        <DeleteMyData slug={slug} standName={stand.stand.name} plates={me?.own_plate_number ?? (me?.plate_number ?? 0) % total} total={total} me={me} onDeleted={() => { clearCustomerKey(slug); setMe(null); setView({ kind: 'deleted' }); }} />
      </div>
    </Shell>
  );
}

function Shell({ stand, children }: { stand: StandPublic | null; children: React.ReactNode }) {
  return (
    <main className="phone">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span className="stand-name">{stand?.stand.name ?? ''}</span>
        </div>
        <Logo size={22} />
      </header>
      {stand?.photo && (
        <div className="stand-cover">
          <img src={photoUrl(stand.photo)} alt={`${stand.stand.name}, the food stand`} loading="lazy" decoding="async" />
        </div>
      )}
      {stand?.last_plates && <div style={{ padding: '0 12px 10px' }}><LastPlatesBanner lp={stand.last_plates} /></div>}
      {children}
    </main>
  );
}

const TAP_LINES = [
  'Hehe, that tickles! 😆',
  'I dey here o! 👋🏾',
  'Abeg no press me too much 😂',
  'You don chop today? 🍲',
  'Hi again! You fine die 😄',
];

function Hero({ bubble, tapLine, counted, children }: { bubble: string; tapLine?: string | null; counted?: boolean; children: React.ReactNode }) {
  return (
    <section className="hero">
      {counted && (
        <div className="counted-pill" role="status">
          <Check /> Visit counted
        </div>
      )}
      <div className="bubble" key={tapLine ?? 'main'} style={counted ? { marginTop: 18 } : undefined} aria-live="polite">{tapLine ?? bubble}</div>
      <div className="hero-row">{children}</div>
    </section>
  );
}

function PlateCard({ plate, total, windowSeconds, crewName }: { plate: number; total: number; windowSeconds: number; crewName?: string | null }) {
  const windowText = windowSeconds < 120 ? `${windowSeconds} seconds` : `${Math.round(windowSeconds / 3600)} hours`;
  return (
    <div className="card">
      <div className="row">
        <span className="eyebrow">{crewName ? 'CREW CARD' : 'YOUR JARA'}</span>
        <span style={{ fontSize: 13, fontWeight: 700 }}>
          {crewName ? `${crewName} · jara on plate ${total}, by turns` : `Free extra on plate ${total}`}
        </span>
      </div>
      <div className="row" style={{ alignItems: 'center' }}>
        <span className="plate-count">PLATE {plate}/{total}</span>
        {plate === total - 1 && <span className="almost-pill">1 more! 🔥</span>}
      </div>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={plate}>
        <div style={{ width: `${(plate / total) * 100}%` }} />
      </div>
      <span className="note">One plate counts per visit. Next one counts after {windowText}.</span>
    </div>
  );
}

function WelcomeForm({ onSubmit }: { onSubmit: (b: { first_name?: string; consent: boolean }) => Promise<void> }) {
  const [name, setName] = useState('');
  const [consent, setConsent] = useState(true);
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="stack"
      style={{ padding: '22px 20px 20px', gap: 14 }}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        await onSubmit({ first_name: name || undefined, consent });
        setBusy(false);
      }}
    >
      <h1 className="display" style={{ fontSize: 38 }}>YOUR FIRST PLATE!</h1>
      <label className="field">
        First name
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Kelechi" maxLength={40} autoComplete="given-name" />
      </label>
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>Remember my first name at this stand. The vendor only sees my first name, plates and ratings. I can delete my data anytime.</span>
      </label>
      <button className="btn" type="submit" disabled={busy}>{busy ? 'Counting…' : 'Count my first plate'}</button>
    </form>
  );
}

function TooSoon({
  stand, initialSeconds, windowSeconds, plate, crewName, name, canCount, onReady, extras,
}: { stand: StandPublic; initialSeconds: number; windowSeconds: number; plate: number; crewName?: string | null; name: string | null; canCount: boolean; onReady: () => void; extras?: React.ReactNode }) {
  // Count down to a fixed end time, not by ticking: phones pause timers while the
  // screen is off or the tab is in the background, which would leave a 6-hour
  // countdown far behind. Re-read the clock on every tick and when the page is shown again.
  const [endsAt] = useState(() => Date.now() + initialSeconds * 1000);
  const secondsLeft = () => Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
  const [seconds, setSeconds] = useState(secondsLeft);
  useEffect(() => {
    const sync = () => setSeconds(secondsLeft());
    const t = setInterval(sync, 1000);
    document.addEventListener('visibilitychange', sync);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', sync);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endsAt]);
  const ch = stand.character;
  const total = stand.plates_for_jara;
  const mm = Math.floor(seconds / 60);
  const ss = String(seconds % 60).padStart(2, '0');
  const hh = Math.floor(seconds / 3600);
  const label = seconds >= 3600 ? `${hh}h ${Math.floor((seconds % 3600) / 60)}m` : `${mm}:${ss}`;
  const pct = Math.min(100, Math.round((1 - seconds / Math.max(1, windowSeconds)) * 100));
  return (
    <>
      <Hero bubble={`You don collect this plate already${name ? ', ' + name : ''}! I dey count the next one.`}>
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="wink" pose="idle" size={170} react follow />
        <div className="timer" style={{ background: `conic-gradient(#141414 0 ${pct}%, #FFFFFF ${pct}% 100%)` }} aria-label={`Next plate in ${label}`}>
          <div className="timer-inner">
            {/* One line always: hours ("5h 59m") get a smaller size so they fit the ring. */}
            <span style={{ fontFamily: 'var(--display)', fontSize: label.length > 5 ? 21 : 28, lineHeight: 1, whiteSpace: 'nowrap' }}>{label}</span>
            <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>NEXT PLATE</span>
          </div>
        </div>
      </Hero>
      <div className="stack">
        <PlateCard plate={plate} total={total} crewName={crewName} windowSeconds={windowSeconds} />
        {extras}
        <div className="card-outline">
          <span className="eyebrow">WHY THE WAIT?</span>
          <span style={{ fontSize: 15, lineHeight: 1.45, fontWeight: 600 }}>
            One plate per visit keeps the jara fair for everyone.
          </span>
        </div>
        {seconds > 0 ? (
          <button className="btn" disabled>Wait for the timer</button>
        ) : canCount ? (
          // Scanned at the stand while the timer was still running: count now.
          <button className="btn" onClick={onReady}>Count my next plate</button>
        ) : (
          <ScanHint charName={ch?.name ?? 'your host'} done />
        )}
        <TalkAndPlay slug={stand.stand.slug} first={ch?.name.split(' ')[0] ?? 'us'} outline />
      </div>
    </>
  );
}

// The two ways to spend time with the character: chat (AI, limited per plate) and play
// (games run on the phone, no AI).
function TalkAndPlay({ slug, first, outline }: { slug: string; first: string; outline?: boolean }) {
  return (
    <div className="duo">
      <Link to={`/s/${slug}/chat`} className={outline ? 'btn btn-outline' : 'btn'}><ChatIcon /> Talk to {first}</Link>
      <Link to={`/s/${slug}/play`} className="btn btn-outline"><span aria-hidden="true">🎮</span> Play</Link>
    </div>
  );
}

// A warm goodbye at the end of every visit (people remember how an experience ends).
const GOODBYES = [
  'Enjoy your food, see you next time! 👋',
  'Thanks for coming, e go sweet you! 😋',
  'Go well, come back soon o! 🙌',
  'Chop well, we dey wait for you! 🍲',
];
function Goodbye({ name, plate }: { name: string | null; plate: number }) {
  const line = GOODBYES[plate % GOODBYES.length];
  return <p className="goodbye">{name ? `${name}, ${line.charAt(0).toLowerCase()}${line.slice(1)}` : line}</p>;
}

// How to count a plate: scan the stand's QR code with the phone camera.
function ScanHint({ charName, done }: { charName: string; done?: boolean }) {
  return (
    <div className="scan-hint" role="status">
      <span className="scan-hint-icon" aria-hidden="true"><CameraIcon /></span>
      <span>
        <strong>{done ? 'Timer done! Scan the QR code at the stand' : 'Scan the QR code at the stand'}</strong>
        <span className="note" style={{ display: 'block' }}>
          Open your phone camera and point it at {charName.split(' ')[0]}'s QR sign. Only a scan at the stand counts a plate.
        </span>
      </span>
    </div>
  );
}

const CameraIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
    <circle cx="12" cy="13" r="3" />
  </svg>
);

// Unredeemed jara codes at this stand (own card or a crew turn), so a code is never lost.
function OpenJara({ codes }: { codes: { code: string }[] }) {
  if (!codes.length) return null;
  return (
    <div className="card-outline" role="status" style={{ background: 'var(--blush)', borderColor: 'var(--pepper)' }}>
      <span className="eyebrow">{codes.length > 1 ? 'YOUR JARA CODES' : 'YOUR JARA'}</span>
      {codes.map((j) => (
        <span key={j.code} style={{ fontFamily: 'var(--display)', fontSize: 32, lineHeight: 1, letterSpacing: '0.06em' }}>{j.code}</span>
      ))}
      <span style={{ fontSize: 15, fontWeight: 700 }}>Show this to the vendor for a free extra portion. One use.</span>
    </div>
  );
}

function Rate({ slug, visitId }: { slug: string; visitId: number }) {
  const [choice, setChoice] = useState<number | null>(null);
  const rate = async (stars: number) => {
    setChoice(stars);
    try { await api.rate(slug, visitId, stars); } catch { setChoice(null); }
  };
  return (
    <div className="rate">
      <span style={{ fontSize: 16, fontWeight: 800, lineHeight: 1.25 }}>{choice ? 'Thanks for rating!' : "Rate today's food"}</span>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="thumb" aria-label="Good" aria-pressed={choice === 5} onClick={() => rate(5)}><ThumbUp /></button>
        <button type="button" className="thumb" aria-label="Not good" aria-pressed={choice === 1} onClick={() => rate(1)}><ThumbDown /></button>
      </div>
    </div>
  );
}

function Menu({ items }: { items: { item: string; price: number }[] }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  return (
    <>
      <button className="btn btn-outline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Hide menu' : 'See menu'}</button>
      {open && (
        <div className="card-outline">
          {items.map((m) => (
            <div key={m.item} className="row" style={{ fontSize: 15 }}>
              <span style={{ fontWeight: 600 }}>{m.item}</span>
              <span style={{ fontWeight: 800 }}>{naira(m.price)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function JaraScreen({ stand, result, onDone }: { stand: StandPublic; result: CountResult; onDone: () => void }) {
  const ch = stand.character;
  const colors = Object.values(PRESETS).map((p) => p.fill);
  const confetti = Array.from({ length: 34 }, (_, i) => {
    const seed = (i * 9301 + 49297) % 233280;
    const r = (n: number) => ((seed * (n + 3)) % 1000) / 1000;
    const round = r(1) < 0.35;
    return {
      left: `${Math.round(r(2) * 96)}%`, top: Math.round(r(3) * 470) + 20,
      w: round ? 10 : 8 + Math.round(r(4) * 6), h: round ? 10 : 14 + Math.round(r(5) * 8),
      rot: Math.round(r(6) * 180) - 90, color: colors[i % colors.length], round, delay: r(7) * 0.6,
    };
  });
  return (
    <main className="jara">
      {confetti.map((c, i) => (
        <span key={i} className="confetti" aria-hidden="true" style={{
          left: c.left, top: c.top, width: c.w, height: c.h, background: c.color,
          borderRadius: c.round ? 999 : 3, transform: `rotate(${c.rot}deg)`, animationDelay: `${c.delay}s`,
        }} />
      ))}
      <header className="topbar" style={{ position: 'relative' }}>
        <span className="stand-name">{stand.stand.name}</span>
        <Logo size={22} />
      </header>
      <div style={{ position: 'relative', paddingTop: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: '0.1em' }}>
          {result.surprise
            ? `${(ch?.name ?? 'THE VENDOR').toUpperCase()} DON DASH YOU · PLATE ${result.plate_number}`
            : `${result.crew ? `${result.crew.name.toUpperCase()}: YOUR TURN · ` : ''}${result.plates_for_jara} OF ${result.plates_for_jara} PLATES`}
        </span>
        <h1 className="display" style={{ fontSize: result.surprise ? 76 : 104 }}>{result.surprise ? 'SURPRISE JARA!' : 'JARA!'}</h1>
      </div>
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
        <div className="bubble" style={{ alignSelf: 'center', textAlign: 'center' }}>
          {result.surprise
            ? `Today na your lucky day${result.customer.first_name ? ', ' + result.customer.first_name : ''}! 🎁`
            : `You don try${result.customer.first_name ? ', ' + result.customer.first_name : ''}! Enjoy am, see you soon 👋`}
        </div>
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="excited" pose="jump" size={210} />
      </div>
      <div className="code-card" role="status">
        <span style={{ fontSize: 15, fontWeight: 800 }}>Show this screen to the vendor</span>
        <span style={{ fontFamily: 'var(--display)', fontSize: 44, lineHeight: 1, letterSpacing: '0.06em' }}>{result.jara?.code}</span>
        <span style={{ fontSize: 18, fontWeight: 800 }}>A free extra portion</span>
        <span className="note">{result.customer.first_name ? `${result.customer.first_name} · ` : ''}one use</span>
      </div>
      <div style={{ position: 'relative', padding: '14px 12px 24px' }}>
        <button className="btn" onClick={onDone}>{result.surprise ? 'Done, back to my card' : `Done, start my next ${result.plates_for_jara}`}</button>
      </div>
    </main>
  );
}
