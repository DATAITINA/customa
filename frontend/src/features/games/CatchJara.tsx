import { useEffect, useRef, useState } from 'react';
import type { Character as StandCharacter } from '../../api';
import { Character } from '../../components/Character';

const GAME_MS = 20000;
const AREA_H = 420;
const MAX_ITEMS = 8;
const ITEM = 36; // emoji box, px
const CHAR_SIZE = 70;
const CHAR_H = CHAR_SIZE * 1.2;
const CHAR_TOP = AREA_H - CHAR_H - 6;
const FOODS = ['🍗', '🐟', '🥚', '🍛', '🍌'];
const PEPPER = '🌶️';

type Item = { on: boolean; x: number; y: number; vy: number; pepper: boolean };
type Phase = 'ready' | 'playing' | 'done';

function readBest(key: string): number {
  try {
    return Number(localStorage.getItem(key)) || 0;
  } catch {
    return 0;
  }
}

function writeBest(key: string, n: number) {
  try {
    localStorage.setItem(key, String(n));
  } catch {
    // Private mode or full storage: the best score just will not stick.
  }
}

function endLine(n: number): string {
  if (n >= 15) return `Ehen! You catch ${n}! Na you be chef 👨🏾‍🍳`;
  if (n >= 8) return `E sweet! ${n} plates. You fit come work for my stand!`;
  if (n >= 1) return `${n} only? Hunger dey catch you small. Try again!`;
  return 'Wahala! Pepper don finish you 🌶️ Try again!';
}

// Arcade game: food falls, the stand character catches it. The frame loop writes transforms
// straight onto DOM nodes; React only re-renders when the score or the whole-second timer changes,
// so cheap phones keep up.
export function CatchJara({ slug, character }: { slug: string; character: StandCharacter | null }) {
  const bestKey = `customa:game:catch:${slug}`;
  const [phase, setPhase] = useState<Phase>('ready');
  const [score, setScore] = useState(0);
  const [secs, setSecs] = useState(GAME_MS / 1000);
  const [best, setBest] = useState(() => readBest(bestKey));
  const [newBest, setNewBest] = useState(false);
  const [face, setFace] = useState<'happy' | 'excited' | 'wink'>('happy');

  const areaRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<(HTMLSpanElement | null)[]>([]);
  // Mutable game state lives in one ref so the loop never waits on React.
  const g = useRef({
    items: Array.from({ length: MAX_ITEMS }, (): Item => ({ on: false, x: 0, y: 0, vy: 0, pepper: false })),
    width: 320,
    px: 0,
    target: 0,
    left: GAME_MS,
    spawnIn: 0,
    score: 0,
    last: 0,
    raf: 0,
    running: false,
    seed: 1,
    slow: 1,
    shownSecs: GAME_MS / 1000,
  });
  const faceTimer = useRef(0);

  const ch = character;
  const first = ch?.name.split(' ')[0] ?? 'Me';

  // Small deterministic PRNG: no Math.random, so a round is reproducible from its seed.
  function rand() {
    let t = (g.current.seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  function measure() {
    const el = areaRef.current;
    if (el) g.current.width = el.clientWidth;
  }

  function placePlayer() {
    const s = g.current;
    const max = s.width - CHAR_SIZE;
    s.px = Math.max(0, Math.min(max, s.px));
    if (playerRef.current) playerRef.current.style.transform = `translate3d(${s.px}px,${CHAR_TOP}px,0)`;
  }

  function flash(f: 'excited' | 'wink') {
    setFace(f);
    clearTimeout(faceTimer.current);
    faceTimer.current = window.setTimeout(() => setFace('happy'), 450);
  }

  function frame(now: number) {
    const s = g.current;
    if (!s.running) return;
    // Clamp dt so a stalled frame does not teleport everything.
    const dt = Math.min(50, now - (s.last || now));
    s.last = now;
    s.left -= dt;

    // Ease toward the finger so taps glide instead of jumping.
    s.px += (s.target - s.px) * Math.min(1, dt / 60);
    placePlayer();

    s.spawnIn -= dt;
    if (s.spawnIn <= 0 && s.left > 600) {
      const free = s.items.findIndex((it) => !it.on);
      if (free >= 0) {
        const it = s.items[free];
        const elapsed = 1 - s.left / GAME_MS;
        it.on = true;
        it.pepper = rand() < 0.18;
        it.x = rand() * (s.width - ITEM);
        it.y = -ITEM;
        // px per ms, speeding up as the clock runs down.
        it.vy = (0.16 + elapsed * 0.14 + rand() * 0.06) * s.slow;
        const node = nodeRefs.current[free];
        if (node) {
          node.textContent = it.pepper ? PEPPER : FOODS[Math.floor(rand() * FOODS.length)];
          node.style.visibility = 'visible';
        }
      }
      s.spawnIn = 520 - (1 - s.left / GAME_MS) * 180;
    }

    let scored = 0;
    s.items.forEach((it, i) => {
      if (!it.on) return;
      it.y += it.vy * dt;
      const node = nodeRefs.current[i];
      const cx = it.x + ITEM / 2;
      const cy = it.y + ITEM / 2;
      const caught = cy >= CHAR_TOP && cy <= CHAR_TOP + CHAR_H * 0.6 && Math.abs(cx - (s.px + CHAR_SIZE / 2)) < CHAR_SIZE * 0.55;
      if (caught || it.y > AREA_H) {
        it.on = false;
        if (node) node.style.visibility = 'hidden';
        if (caught) {
          scored += it.pepper ? -1 : 1;
          flash(it.pepper ? 'wink' : 'excited');
        }
        return;
      }
      if (node) node.style.transform = `translate3d(${it.x}px,${it.y}px,0)`;
    });

    if (scored) {
      s.score = Math.max(0, s.score + scored);
      setScore(s.score);
    }
    const whole = Math.max(0, Math.ceil(s.left / 1000));
    if (whole !== s.shownSecs) {
      s.shownSecs = whole;
      setSecs(whole);
    }

    if (s.left <= 0) {
      finish();
      return;
    }
    s.raf = requestAnimationFrame(frame);
  }

  function run() {
    const s = g.current;
    if (s.running) return;
    s.running = true;
    s.last = 0;
    s.raf = requestAnimationFrame(frame);
  }

  function halt() {
    const s = g.current;
    s.running = false;
    cancelAnimationFrame(s.raf);
  }

  function finish() {
    halt();
    const s = g.current;
    s.items.forEach((it, i) => {
      it.on = false;
      const node = nodeRefs.current[i];
      if (node) node.style.visibility = 'hidden';
    });
    const prev = readBest(bestKey);
    const isBest = s.score > prev;
    if (isBest) {
      writeBest(bestKey, s.score);
      setBest(s.score);
    }
    setNewBest(isBest);
    setFace('happy');
    setPhase('done');
  }

  function start() {
    measure();
    const s = g.current;
    s.items.forEach((it) => (it.on = false));
    s.left = GAME_MS;
    s.spawnIn = 300;
    s.score = 0;
    s.seed = (Date.now() & 0xffffffff) >>> 0;
    s.shownSecs = GAME_MS / 1000;
    // Reduced motion keeps the game, just slower.
    s.slow = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 0.6 : 1;
    s.px = s.target = (s.width - CHAR_SIZE) / 2;
    placePlayer();
    setScore(0);
    setSecs(GAME_MS / 1000);
    setNewBest(false);
    setPhase('playing');
    areaRef.current?.focus({ preventScroll: true });
    run();
  }

  // Pause when the tab is hidden (screen off, app switch); resume on return.
  useEffect(() => {
    if (phase !== 'playing') return;
    const onVis = () => (document.visibilityState === 'hidden' ? halt() : run());
    const onResize = () => {
      measure();
      placePlayer();
    };
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('resize', onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  useEffect(() => {
    measure();
    g.current.px = g.current.target = (g.current.width - CHAR_SIZE) / 2;
    placePlayer();
    return () => {
      halt();
      clearTimeout(faceTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function aim(clientX: number) {
    const el = areaRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    g.current.target = Math.max(0, Math.min(g.current.width - CHAR_SIZE, clientX - rect.left - CHAR_SIZE / 2));
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (phase !== 'playing') return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    aim(e.clientX);
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    // Mouse follows on hover; touch and pen only while pressed.
    if (phase !== 'playing') return;
    if (e.pointerType === 'mouse' || e.buttons) aim(e.clientX);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (phase !== 'playing') return;
    const step = g.current.width / 6;
    const s = g.current;
    if (e.key === 'ArrowLeft') s.target = Math.max(0, s.target - step);
    else if (e.key === 'ArrowRight') s.target = Math.min(s.width - CHAR_SIZE, s.target + step);
    else return;
    e.preventDefault();
  }

  return (
    <section className="games-panel" aria-label="Catch the jara">
      <div className="games-hud">
        <span>
          <span className="eyebrow">SCORE</span>
          <span className="games-hud-num" aria-live="off">{score}</span>
        </span>
        <span>
          <span className="eyebrow">TIME</span>
          <span className="games-hud-num">{secs}s</span>
        </span>
        <span>
          <span className="eyebrow">BEST</span>
          <span className="games-hud-num">{best}</span>
        </span>
      </div>

      <div
        ref={areaRef}
        className="games-area"
        style={{ height: AREA_H }}
        tabIndex={phase === 'playing' ? 0 : -1}
        aria-label="Play area. Drag or use the arrow keys to move."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onKeyDown={onKeyDown}
      >
        {Array.from({ length: MAX_ITEMS }, (_, i) => (
          <span
            key={i}
            ref={(el) => {
              nodeRefs.current[i] = el;
            }}
            className="games-item"
            aria-hidden="true"
          />
        ))}
        <div ref={playerRef} className="games-player" aria-hidden="true">
          <Character
            body={ch?.body}
            color={ch?.color}
            accessory={ch?.accessory}
            expression={phase === 'done' ? (score >= 8 ? 'excited' : 'wink') : face}
            pose={phase === 'done' ? (score >= 8 ? 'jump' : 'wave') : 'idle'}
            size={CHAR_SIZE}
          />
        </div>

        {phase !== 'playing' && (
          <div className="games-overlay">
            {phase === 'ready' ? (
              <>
                <span className="display games-h">Catch the jara!</span>
                <p className="games-overlay-text">
                  Drag {first} left and right. Every food na +1. Hot pepper 🌶️ na -1. You get 20 seconds.
                </p>
                <button type="button" className="btn games-btn" onClick={start}>Start</button>
              </>
            ) : (
              <>
                <span className="display games-h">{score} caught</span>
                <p className="games-overlay-text" role="status">
                  <strong>{first}:</strong> “{endLine(score)}”
                  {newBest && <span className="games-tag">New best!</span>}
                </p>
                <button type="button" className="btn games-btn" onClick={start}>Play again</button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
