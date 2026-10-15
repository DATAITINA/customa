import { useMemo, useState } from 'react';
import type { Character as StandCharacter } from '../../api';
import { Character } from '../../components/Character';

const ROUNDS = 5;

type Dish = { item: string; price: number };
type Round = [Dish, Dish];

function naira(n: number) {
  return `₦${n.toLocaleString('en-NG')}`;
}

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

function prng(seed: number) {
  let a = seed;
  return () => {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

// Seeded by date + slug, so everyone gets the same first game today. Pairs with different prices
// come first; equal-price pairs are only used when the menu has nothing else.
function buildRounds(menu: Dish[], slug: string, attempt: number): Round[] {
  const rand = prng(hash(`${today()}:${slug}:${attempt}`));
  const shuffle = <T,>(list: T[]) => {
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  };
  const pairs: Round[] = [];
  const ties: Round[] = [];
  for (let i = 0; i < menu.length; i++) {
    for (let j = i + 1; j < menu.length; j++) {
      const pair: Round = rand() < 0.5 ? [menu[i], menu[j]] : [menu[j], menu[i]];
      (menu[i].price === menu[j].price ? ties : pairs).push(pair);
    }
  }
  const pool = [...shuffle(pairs), ...shuffle(ties)];
  // A short menu repeats pairs rather than giving fewer rounds.
  return Array.from({ length: ROUNDS }, (_, i) => pool[i % pool.length]);
}

// "Which one cost pass?": tap the dearer of two real menu items.
export function MenuQuiz({ slug, character }: { slug: string; character: StandCharacter | null }) {
  const ch = character;
  const first = ch?.name.split(' ')[0] ?? 'This stand';
  const menu = useMemo(() => (ch?.menu ?? []).filter((m) => m.item && Number.isFinite(m.price)), [ch]);

  const [attempt, setAttempt] = useState(0);
  const [round, setRound] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [score, setScore] = useState(0);

  const rounds = useMemo(() => (menu.length >= 2 ? buildRounds(menu, slug, attempt) : []), [menu, slug, attempt]);

  if (rounds.length === 0) {
    return (
      <section className="games-panel">
        <div className="card games-center">
          <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression="wink" pose="wave" size={100} />
          <span className="display games-h">{first} never add menu yet!</span>
          <p className="note" style={{ margin: 0 }}>Come back when the menu is ready. Try Catch the jara for now.</p>
        </div>
      </section>
    );
  }

  const finished = round >= ROUNDS;
  const pair = rounds[Math.min(round, ROUNDS - 1)];
  const tie = pair[0].price === pair[1].price;
  const right = picked !== null && (tie || pair[picked].price > pair[1 - picked].price);

  function pick(i: number) {
    if (picked !== null) return;
    setPicked(i);
    if (tie || pair[i].price > pair[1 - i].price) setScore((s) => s + 1);
  }

  function next() {
    setPicked(null);
    setRound((r) => r + 1);
  }

  function again() {
    setAttempt((a) => a + 1);
    setRound(0);
    setPicked(null);
    setScore(0);
  }

  let line = `Which one cost pass? Tap am.`;
  if (finished) {
    line =
      score === ROUNDS
        ? `Ehen! ${score}/${ROUNDS}! You sabi my menu pass me 😄`
        : score >= 3
          ? `E sweet! ${score}/${ROUNDS}. You don chop here before, abi?`
          : `Wahala! ${score}/${ROUNDS}. Come buy more, you go learn 😉`;
  } else if (picked !== null) {
    line = tie
      ? 'Na the same price! I go give you the point 😄'
      : right
        ? `E sweet! ${pair[picked].item} na ${naira(pair[picked].price)}.`
        : `Ah ah! ${pair[1 - picked].item} cost pass: ${naira(pair[1 - picked].price)}.`;
  }

  const face = finished ? (score >= 3 ? 'excited' : 'wink') : picked === null ? 'happy' : right ? 'excited' : 'wink';
  const pose = finished ? (score >= 3 ? 'jump' : 'wave') : picked === null ? 'idle' : right ? 'hop' : 'idle';

  return (
    <section className="games-panel" aria-label="Which one cost pass?">
      <div className="games-quiz-head">
        <span className="eyebrow">{finished ? 'DONE' : `ROUND ${round + 1} OF ${ROUNDS}`}</span>
        <span className="eyebrow">SCORE {score}</span>
      </div>

      <div className="games-quiz-stage">
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression={face} pose={pose} size={96} />
        <p className="games-bubble" aria-live="polite">
          {line}
        </p>
      </div>

      {finished ? (
        <div className="card games-center">
          <span className="display games-score">
            {score}/{ROUNDS}
          </span>
          <button type="button" className="btn" onClick={again}>Play again</button>
        </div>
      ) : (
        <>
          <div className="games-choices">
            {pair.map((dish, i) => {
              const state = picked === null ? '' : tie || dish.price >= pair[1 - i].price ? 'win' : 'lose';
              return (
                <button
                  key={i}
                  type="button"
                  className={`games-choice ${state ? `games-choice-${state}` : ''}`}
                  aria-pressed={picked === i}
                  disabled={picked !== null && picked !== i}
                  onClick={() => pick(i)}
                >
                  <span className="games-choice-name">{dish.item}</span>
                  <span className="games-choice-price">{picked === null ? '₦ ?' : naira(dish.price)}</span>
                </button>
              );
            })}
          </div>
          {picked !== null && (
            <button type="button" className="btn" onClick={next}>
              {round + 1 === ROUNDS ? 'See my score' : 'Next'}
            </button>
          )}
        </>
      )}
    </section>
  );
}
