import { useCallback, useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { api, photoUrl, type ApiError, type StandPublic } from '../../api';
import { Link, rememberStand } from '../../App';
import { Logo } from '../../components/Logo';
import { CharacterLoader } from '../../components/Loading';
import { sliceAt, targetRotation, Wheel, type WheelHandle } from './Wheel';
import { setSoundOn, soundOn, tick, unlockSound, winJingle } from './sounds';
import { wheelApi, type SpinResult, type WheelSlice, type WheelState, type WonPrize } from './wheelApi';
import './wheel.css';

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
const easeOut = (p: number) => 1 - Math.pow(1 - p, 4);
const easeInOut = (p: number) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
const day = (iso: string) => new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleDateString([], { day: 'numeric', month: 'short' });

// /s/{slug}/wheel: the customer's Prize Wheel. A jara is one spin: the server picks the prize
// and where the wheel stops, and this page animates exactly that, then shows the prize and its
// one-time code (with a QR code the vendor can scan).
export function WheelPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [state, setState] = useState<WheelState | null>(null);
  const [failed, setFailed] = useState(false);
  const [slices, setSlices] = useState<WheelSlice[]>([]);
  const [phase, setPhase] = useState<'ready' | 'spinning' | 'won'>('ready');
  const [result, setResult] = useState<SpinResult | null>(null);
  const [showing, setShowing] = useState<WonPrize | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sound, setSound] = useState(soundOn());
  const wheel = useRef<WheelHandle>(null);
  const rotation = useRef(0);

  const load = useCallback(async () => {
    const [s, w] = await Promise.all([api.stand(slug), wheelApi.state(slug)]);
    setStand(s);
    setState(w);
    setSlices((now) => (now.length ? now : w.items));
    return w;
  }, [slug]);

  useEffect(() => {
    rememberStand(slug);
    load().catch(() => setFailed(true));
  }, [load, slug]);

  const animate = (target: number, onWheel: WheelSlice[]) =>
    new Promise<void>((done) => {
      const from = rotation.current;
      const quick = reduceMotion();
      const windUp = quick ? 0 : 260; // a small pull back before the throw
      const run = quick ? 1100 : 5400;
      const settle = quick ? 0 : 520;
      const over = quick ? 0 : 4; // a little past the stop, then it settles back
      const start = performance.now();
      let last = sliceAt(onWheel, from);
      const frame = (now: number) => {
        const t = now - start;
        let deg: number;
        if (t < windUp) deg = from - 9 * easeOut(t / windUp);
        else if (t < windUp + run) deg = from - 9 + (target + over - (from - 9)) * easeOut((t - windUp) / run);
        else deg = target + over * (1 - easeInOut(Math.min(1, (t - windUp - run) / Math.max(1, settle))));
        wheel.current?.setRotation(deg);
        const under = sliceAt(onWheel, deg);
        if (under !== last) {
          last = under;
          tick();
          wheel.current?.kick();
        }
        if (t < windUp + run + settle) requestAnimationFrame(frame);
        else {
          rotation.current = target;
          wheel.current?.setRotation(target);
          done();
        }
      };
      requestAnimationFrame(frame);
    });

  const spin = async () => {
    const jaraId = state?.spins[0];
    if (!jaraId || phase === 'spinning') return;
    unlockSound();
    setError(null);
    setPhase('spinning');
    try {
      const r = await wheelApi.spin(slug, jaraId);
      // The wheel exactly as the server spun it (it can differ if the vendor just changed it).
      setSlices(r.wheel);
      await new Promise((ok) => requestAnimationFrame(ok));
      await animate(targetRotation(r.wheel, r.slot, r.landing, rotation.current), r.wheel);
      setResult(r);
      setPhase('won');
      winJingle();
      navigator.vibrate?.([30, 40, 60]);
      setTimeout(() => setShowing(r.prize), quickDelay());
      load().catch(() => undefined);
    } catch (err) {
      setPhase('ready');
      setError((err as ApiError).message || 'The wheel could not spin. Check your network and try again.');
      load().catch(() => undefined);
    }
  };

  if (failed) {
    return (
      <Shell slug={slug}>
        <div className="stack"><p className="error">Could not load the prize wheel. Check your network and try again.</p></div>
      </Shell>
    );
  }
  if (!stand || !state) return <Shell slug={slug}><CharacterLoader kind="stand" /></Shell>;

  const ch = stand.character;
  const first = ch?.name.split(' ')[0] ?? stand.stand.name;
  const spins = state.spins.length;
  const known = !!stand.customer;
  const plate = stand.customer?.plate_number ?? 0;
  const left = stand.plates_for_jara - (plate % stand.plates_for_jara || 0);
  const wheelShown = slices.length >= 2 ? slices : state.items;

  if (!state.enabled && !state.won.length && phase !== 'won') {
    return (
      <Shell slug={slug}>
        <div className="stack" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="display" style={{ fontSize: 40 }}>THE WHEEL IS RESTING</h1>
          <p className="note" style={{ fontSize: 15 }}>{stand.stand.name} has no prize wheel today. Your jara still works: show its code to the vendor.</p>
          <Link to={`/s/${slug}`} className="btn">Back to my card</Link>
        </div>
      </Shell>
    );
  }

  return (
    <Shell slug={slug} sound={sound} onSound={() => { setSoundOn(!sound); setSound(!sound); }}>
      <section className="wheel-stage">
        <span className="eyebrow">{stand.stand.name.toUpperCase()} · PRIZE WHEEL</span>
        <h1 className="display wheel-title">
          {phase === 'won' ? 'YOU WIN!' : spins ? 'SPIN FOR YOUR JARA!' : 'WIN FOOD ON PLATE ' + stand.plates_for_jara}
        </h1>
        {wheelShown.length >= 2 && (
          <Wheel
            ref={wheel}
            slices={wheelShown}
            character={ch}
            size={Math.min(330, window.innerWidth - 40)}
            idle={phase === 'ready' && !spins}
            lights={phase === 'spinning' ? 'spin' : phase === 'won' ? 'win' : 'idle'}
            winner={phase === 'won' && result ? result.slot : null}
          />
        )}

        {phase === 'won' && result ? (
          <button type="button" className="btn wheel-cta" onClick={() => setShowing(result.prize)}>See my prize code</button>
        ) : spins ? (
          <button type="button" className="btn wheel-cta wheel-spin" disabled={phase === 'spinning'} onClick={spin}>
            {phase === 'spinning' ? 'Spinning…' : spins > 1 ? `SPIN! (${spins} spins)` : 'SPIN!'}
          </button>
        ) : (
          <div className="wheel-wait">
            {known ? (
              <>
                <strong>{left === 1 ? 'One more plate' : `${left} more plates`} and you spin {first}'s wheel.</strong>
                <span className="note">Every jara is a spin. The server picks fair and square.</span>
              </>
            ) : (
              <>
                <strong>Scan the QR code at {stand.stand.name} to start your card.</strong>
                <span className="note">On plate {stand.plates_for_jara} you spin for a free food prize.</span>
              </>
            )}
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        {phase === 'won' && spins > 0 && (
          <button type="button" className="btn btn-outline wheel-cta" onClick={() => { setPhase('ready'); setResult(null); }}>
            Spin again ({spins} left)
          </button>
        )}
      </section>

      {state.won.filter((w) => !result || w.code !== result.prize.code).length > 0 && (
        <section className="wheel-section">
          <span className="eyebrow">YOUR PRIZES TO COLLECT</span>
          {state.won.filter((w) => !result || w.code !== result.prize.code).map((w) => (
            <button key={w.code} type="button" className="wheel-won-row" onClick={() => setShowing(w)}>
              <Thumb photo={w.photo} />
              <span className="wheel-won-text"><strong>{w.name}</strong><span className="note">{w.code} · until {day(w.expires_at)}</span></span>
              <span className="wheel-won-go" aria-hidden="true">›</span>
            </button>
          ))}
        </section>
      )}

      {state.items.length > 0 && (
        <section className="wheel-section">
          <span className="eyebrow">PRIZES ON {first.toUpperCase()}'S WHEEL</span>
          <div className="wheel-prizes">
            {state.items.map((i) => (
              <div key={i.id} className="wheel-prize">
                <Thumb photo={i.photo} big />
                <strong>{i.name}</strong>
                {i.prize && <span className="wheel-prize-what">{i.prize}</span>}
                {i.description && <span className="note">{i.description}</span>}
                {i.weight === 1 && <span className="wheel-rare">Rare!</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      {showing && (
        <PrizeReveal
          prize={showing}
          standName={stand.stand.name}
          firstName={stand.customer?.first_name ?? null}
          celebrate={!!result && showing.code === result.prize.code}
          onClose={() => setShowing(null)}
          slug={slug}
        />
      )}
    </Shell>
  );
}

const quickDelay = () => (reduceMotion() ? 200 : 900);

function Shell({ slug, children, sound, onSound }: { slug: string; children: React.ReactNode; sound?: boolean; onSound?: () => void }) {
  return (
    <main className="phone wheel-page">
      <header className="topbar">
        <Link to={`/s/${slug}`} className="link-btn">Back</Link>
        {onSound ? (
          <button type="button" className="wheel-sound" aria-pressed={sound} aria-label={sound ? 'Sound on' : 'Sound off'} onClick={onSound}>
            {sound ? '🔊' : '🔇'}
          </button>
        ) : <span />}
        <Logo size={22} />
      </header>
      {children}
    </main>
  );
}

function Thumb({ photo, big = false }: { photo: string | null; big?: boolean }) {
  return photo ? (
    <img className={`wheel-thumb${big ? ' big' : ''}`} src={photoUrl(photo)} alt="" loading="lazy" decoding="async" />
  ) : (
    <span className={`wheel-thumb wheel-thumb-empty${big ? ' big' : ''}`} aria-hidden="true">🍲</span>
  );
}

const CONFETTI = ['🍗', '🌶️', '🍚', '🥤', '✨', '🎉', '🍲', '⭐'];

// The prize, big: photo, what they won, the one-time code and its QR code for the vendor.
function PrizeReveal({ prize, standName, firstName, celebrate, onClose, slug }: {
  prize: WonPrize; standName: string; firstName: string | null; celebrate: boolean; onClose: () => void; slug: string;
}) {
  return (
    <div className="prize-overlay" role="dialog" aria-modal="true" aria-label={`You won ${prize.name}`}>
      {celebrate && !reduceMotion() && (
        <div className="prize-burst" aria-hidden="true">
          {Array.from({ length: 26 }, (_, i) => (
            <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 9) * 0.07}s`, fontSize: 18 + ((i * 7) % 14) }}>
              {CONFETTI[i % CONFETTI.length]}
            </span>
          ))}
        </div>
      )}
      <div className="prize-card">
        <span className="eyebrow" style={{ color: 'var(--pepper)' }}>{celebrate ? `WINNER${firstName ? ' · ' + firstName.toUpperCase() : ''}!` : 'YOUR PRIZE'}</span>
        {prize.photo ? (
          <img className="prize-photo" src={photoUrl(prize.photo)} alt={prize.name} />
        ) : (
          <div className="prize-photo prize-photo-empty" aria-hidden="true">🍲</div>
        )}
        <h2 className="display prize-name">{prize.name.toUpperCase()}</h2>
        {prize.prize && <p className="prize-what">{prize.prize}</p>}
        {prize.redeemed ? (
          <p className="prize-used">Collected. Enjoy! 😋</p>
        ) : (
          <>
            <div className="prize-code-box">
              <span className="prize-code">{prize.code}</span>
              <QRCodeSVG value={prize.code} size={128} level="M" marginSize={1} />
            </div>
            <p className="prize-how">Show this screen at <strong>{standName}</strong>. The vendor checks the code and gives you your food. One use, until {day(prize.expires_at)}.</p>
          </>
        )}
        <div className="prize-actions">
          <button type="button" className="btn" onClick={onClose}>Done</button>
          <Link to={`/s/${slug}`} className="btn btn-outline">Back to my card</Link>
        </div>
      </div>
    </div>
  );
}
