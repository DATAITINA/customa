// Loading states with Customa's personality: a little character at work and kind words,
// or skeleton blocks shaped like the content that is coming. Pure CSS animation.
import { useEffect, useState } from 'react';
import { Character } from './Character';
import { lookForThisPage } from '../lookCache';

const LINES: Record<string, string[]> = {
  stand: ['Warming up the pot…', 'Setting the table…', 'Calling your host…'],
  card: ['Finding your card…', 'Counting your plates…', 'Checking your jara…'],
  chat: ['Your host is coming…', 'Washing hands small…', 'Finding a seat for you…'],
  vendor: ['Opening your stand…', 'Counting today’s plates…', 'Arranging the dashboard…'],
  game: ['Setting up the game…', 'Arranging the food…'],
};

type LoaderProps = {
  /** Which words to show. */
  kind?: keyof typeof LINES;
  /** The stand's character, when known. */
  character?: { body?: string; color?: string; accessory?: string } | null;
  size?: number;
};

export function CharacterLoader({ kind = 'stand', character, size = 96 }: LoaderProps) {
  const lines = LINES[kind];
  // The stand's own character: given, or remembered on this phone; the pepper only on a first visit.
  const [look] = useState(() => character ?? lookForThisPage());
  character = character ?? look;
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((n) => (n + 1) % lines.length), 1600);
    return () => clearInterval(t);
  }, [lines.length]);
  return (
    <div className="loader" role="status" aria-live="polite">
      <div className="loader-stage">
        <span className="loader-glow" aria-hidden="true" />
        <Character body={character?.body ?? 'pepper'} color={character?.color ?? 'pepper'} accessory={character?.accessory ?? 'chef'} expression="happy" pose="hop" size={size} />
      </div>
      <span className="loader-text" key={i}>{lines[i]}</span>
      <span className="loader-dots" aria-hidden="true"><i /><i /><i /></span>
    </div>
  );
}

/** A grey block that shimmers while content loads. */
export function Skeleton({ h = 16, w = '100%', r = 12, style }: { h?: number | string; w?: number | string; r?: number; style?: React.CSSProperties }) {
  return <span className="skel" style={{ height: h, width: w, borderRadius: r, ...style }} aria-hidden="true" />;
}

/** A card-shaped skeleton for a feature panel. */
export function PanelSkeleton({ label }: { label?: string }) {
  return (
    <div className="card-outline skel-panel" role="status" aria-label={label ? `Loading ${label}` : 'Loading'}>
      <Skeleton h={12} w="40%" />
      <Skeleton h={22} w="70%" />
      <Skeleton h={44} r={999} />
    </div>
  );
}

/** The vendor dashboard while it loads: the same shapes, so nothing jumps when it arrives. */
export function DashboardSkeleton() {
  return (
    <div className="skel-dash" role="status" aria-label="Loading your dashboard">
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        <Skeleton h={64} w={64} r={999} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Skeleton h={26} w="60%" />
          <Skeleton h={14} w="40%" />
        </div>
      </div>
      <Skeleton h={120} r={28} />
      <div className="skel-stats">
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} h={92} r={24} />)}
      </div>
      <Skeleton h={220} r={24} />
    </div>
  );
}
