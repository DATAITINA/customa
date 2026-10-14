import { useEffect, useState } from 'react';
import type { StandPublic } from '../../api';
import { Link } from '../../App';
import { Wheel } from './Wheel';
import { wheelApi, type WheelState } from './wheelApi';
import './wheel.css';

// The Prize Wheel on the customer's card: a spin waiting, or the prizes to come on plate N.
// Shown only when the vendor's wheel is live.
export function WheelCard({ slug, stand, refreshKey }: { slug: string; stand: StandPublic; refreshKey?: number }) {
  const [state, setState] = useState<WheelState | null>(null);
  const live = stand.features?.prize_wheel ?? false;

  useEffect(() => {
    if (!live) return;
    wheelApi.state(slug).then(setState).catch(() => setState(null));
  }, [slug, live, refreshKey]);

  if (!live || !state?.enabled || state.items.length < 2) return null;
  const spins = state.spins.length;
  const first = stand.character?.name.split(' ')[0] ?? stand.stand.name;

  return (
    <Link to={`/s/${slug}/wheel`} className={`wheel-card${spins ? ' has-spin' : ''}`}>
      <div className="wheel-card-mini" aria-hidden="true">
        <Wheel slices={state.items} character={stand.character} size={104} idle />
      </div>
      <div className="wheel-card-text">
        <span className="eyebrow">{spins ? 'YOUR JARA IS A SPIN!' : `${first.toUpperCase()}'S PRIZE WHEEL`}</span>
        <strong>{spins ? (spins > 1 ? `${spins} spins waiting 🎡` : 'A spin is waiting 🎡') : `Win ${state.items.map((i) => i.name).slice(0, 3).join(', ')}${state.items.length > 3 ? '…' : ''}`}</strong>
        <span className="note">{spins ? 'Tap to spin and see what you win.' : `Every jara (plate ${stand.plates_for_jara}) is a spin. Tap to see the prizes.`}</span>
      </div>
    </Link>
  );
}
