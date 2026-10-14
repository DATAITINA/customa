import { forwardRef, useImperativeHandle, useMemo, useRef } from 'react';
import { photoUrl, type Character as CharacterT } from '../../api';
import { Character } from '../../components/Character';
import type { WheelSlice } from './wheelApi';

// Customa's food colours, in turn around the wheel. Text colour picked for contrast.
const SLICE_COLORS = [
  { fill: '#F04E30', text: '#FFFFFF' },
  { fill: '#FFC926', text: '#141414' },
  { fill: '#3DBE5A', text: '#FFFFFF' },
  { fill: '#2BB3F0', text: '#141414' },
  { fill: '#FF8A1F', text: '#141414' },
  { fill: '#CF5DF2', text: '#FFFFFF' },
];
const R = 150; // wheel radius in the SVG's units
const PHOTO_AT = 90; // distance of a slice's photo from the centre
const LABEL_AT = 133; // the food's name runs along the rim at this radius

export type Arc = { start: number; end: number }; // degrees, clockwise from the top

/** Each slice's angle range: its share of the wheel is its weight (how often it comes up). */
export function arcs(slices: { weight: number }[]): Arc[] {
  const total = slices.reduce((sum, s) => sum + Math.max(1, s.weight), 0) || 1;
  let at = 0;
  return slices.map((s) => {
    const size = (360 * Math.max(1, s.weight)) / total;
    const arc = { start: at, end: at + size };
    at += size;
    return arc;
  });
}

const point = (deg: number, r: number) => {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [r * Math.cos(rad), r * Math.sin(rad)] as const;
};

function slicePath({ start, end }: Arc) {
  if (end - start >= 359.99) return `M 0 ${-R} A ${R} ${R} 0 1 1 0 ${R} A ${R} ${R} 0 1 1 0 ${-R} Z`;
  const [x1, y1] = point(start, R);
  const [x2, y2] = point(end, R);
  return `M 0 0 L ${x1} ${y1} A ${R} ${R} 0 ${end - start > 180 ? 1 : 0} 1 ${x2} ${y2} Z`;
}

const short = (name: string, max: number) => (name.length > max ? `${name.slice(0, max - 1).trimEnd()}…` : name);

export type WheelHandle = {
  /** Turn the wheel to `deg` (clockwise), as the spin animation runs. */
  setRotation: (deg: number) => void;
  /** The pointer's flap kicks when a slice edge passes it. */
  kick: () => void;
};

type Props = {
  slices: WheelSlice[];
  character?: CharacterT | null;
  size?: number;
  idle?: boolean; // slow turn while waiting (decoration)
  lights?: 'idle' | 'spin' | 'win';
  winner?: number | null; // highlight this slice after the spin
};

// The prize wheel: slices sized by how often they come up, each with the food's photo and
// name, Customa colours, a light-up rim, the pointer at the top and the stand's character in
// the middle. The spin itself is driven from outside through the ref (WheelPage).
export const Wheel = forwardRef<WheelHandle, Props>(function Wheel(
  { slices, character, size = 300, idle = false, lights = 'idle', winner = null },
  ref,
) {
  const disc = useRef<SVGGElement>(null);
  const flap = useRef<SVGGElement>(null);
  const shape = useMemo(() => arcs(slices), [slices]);
  const uid = useMemo(() => Math.random().toString(36).slice(2, 8), []);

  useImperativeHandle(ref, () => ({
    setRotation: (deg) => disc.current?.setAttribute('transform', `rotate(${deg})`),
    kick: () => {
      const f = flap.current;
      if (!f) return;
      f.classList.remove('wheel-flap-kick');
      void f.getBoundingClientRect();
      f.classList.add('wheel-flap-kick');
    },
  }));

  const bulbs = Array.from({ length: 24 }, (_, i) => point((360 / 24) * i, R + 12));
  const hub = size * 0.3;

  return (
    <div className={`wheel${idle ? ' wheel-idle' : ''}`} style={{ width: size, height: size + size * 0.06 }}>
      <svg viewBox="-172 -182 344 354" width={size} height={size + size * 0.06} role="img" aria-label={`Prize wheel: ${slices.map((s) => s.name).join(', ')}`}>
        <defs>
          {shape.map((arc, i) => {
            const mid = (arc.start + arc.end) / 2;
            const [cx, cy] = point(mid, PHOTO_AT);
            return (
              <clipPath key={i} id={`wc-${uid}-${i}`}>
                <circle cx={cx} cy={cy} r={photoRadius(arc)} />
              </clipPath>
            );
          })}
          {shape.map((arc, i) => {
            // The name's path: along the rim, clockwise, so it reads like a real prize wheel.
            const [x1, y1] = point(arc.start + 1.5, LABEL_AT);
            const [x2, y2] = point(arc.end - 1.5, LABEL_AT);
            return <path key={`l${i}`} id={`wl-${uid}-${i}`} d={`M ${x1} ${y1} A ${LABEL_AT} ${LABEL_AT} 0 ${arc.end - arc.start > 180 ? 1 : 0} 1 ${x2} ${y2}`} fill="none" />;
          })}
          <radialGradient id={`wsheen-${uid}`} cx="0.35" cy="0.3" r="0.9">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.28" />
            <stop offset="0.6" stopColor="#FFFFFF" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* The shadow and the rim with its lights. */}
        <ellipse cx="0" cy={R + 22} rx={R * 0.8} ry="8" fill="#141414" opacity="0.12" />
        <circle r={R + 20} fill="#141414" />
        {bulbs.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="4.2" className={`wheel-bulb wheel-bulb-${lights} ${i % 2 ? 'odd' : 'even'}`} />
        ))}

        <g ref={disc} className={idle ? 'wheel-disc-idle' : undefined}>
          {slices.map((s, i) => {
            const arc = shape[i];
            const color = SLICE_COLORS[i % SLICE_COLORS.length];
            const mid = (arc.start + arc.end) / 2;
            const [px, py] = point(mid, PHOTO_AT);
            const pr = photoRadius(arc);
            const span = arc.end - arc.start;
            // How many letters fit along this slice's stretch of rim.
            const fits = Math.floor(((span - 3) / 360) * 2 * Math.PI * LABEL_AT / 7.4);
            const isWinner = winner === i;
            return (
              <g key={s.id} className={winner != null && !isWinner ? 'wheel-slice-dim' : undefined}>
                <path d={slicePath(arc)} fill={color.fill} stroke="#141414" strokeWidth="3" strokeLinejoin="round" />
                {s.photo ? (
                  <image
                    href={photoUrl(s.photo)}
                    x={px - pr} y={py - pr} width={pr * 2} height={pr * 2}
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#wc-${uid}-${i})`}
                  />
                ) : (
                  <>
                    <circle cx={px} cy={py} r={pr} fill="#FFFFFF" opacity="0.9" />
                    <text x={px} y={py + pr * 0.35} textAnchor="middle" fontSize={pr} aria-hidden="true">🍲</text>
                  </>
                )}
                <circle cx={px} cy={py} r={pr} fill="none" stroke="#FFFFFF" strokeWidth="3" />
                {fits >= 4 && (
                  <text fill={color.text} fontFamily="Figtree, sans-serif" fontWeight="800" fontSize="12.5" letterSpacing="0.3">
                    <textPath href={`#wl-${uid}-${i}`} startOffset="50%" textAnchor="middle">{short(s.name, fits)}</textPath>
                  </text>
                )}
              </g>
            );
          })}
          <circle r={R} fill={`url(#wsheen-${uid})`} pointerEvents="none" />
        </g>

        {/* The hub and the pointer at the top. */}
        <circle r={R * 0.33} fill="#FFFFFF" stroke="#141414" strokeWidth="5" />
        <g ref={flap} className="wheel-flap">
          <path d="M -17 -178 L 17 -178 L 0 -140 Z" fill="#F04E30" stroke="#141414" strokeWidth="5" strokeLinejoin="round" />
          <circle cx="0" cy="-170" r="4" fill="#FFFFFF" />
        </g>
      </svg>
      <div className="wheel-hub" style={{ width: hub, height: hub }} aria-hidden="true">
        <Character body={character?.body} color={character?.color} accessory={character?.accessory}
          expression={lights === 'win' ? 'excited' : 'happy'} pose={lights === 'spin' ? 'idle' : 'wave'} size={hub * 0.9} />
      </div>
    </div>
  );
});

function photoRadius(arc: Arc) {
  const half = ((arc.end - arc.start) / 2) * (Math.PI / 180);
  return Math.max(9, Math.min(30, Math.sin(Math.min(half, Math.PI / 2)) * PHOTO_AT * 0.82));
}

/** The wheel's final turn so the pointer (at the top) rests at `landing` inside slice `slot`,
 * after at least `turns` full turns from `from`. */
export function targetRotation(slices: { weight: number }[], slot: number, landing: number, from: number, turns = 6) {
  const arc = arcs(slices)[slot];
  const at = arc.start + (arc.end - arc.start) * Math.min(0.95, Math.max(0.05, landing));
  // The pointer sees wheel angle (-rotation mod 360): rest the wheel at -at (mod 360).
  const base = from + turns * 360;
  const want = (((-at - base) % 360) + 360) % 360;
  return base + want;
}

/** Which slice is under the pointer at rotation `deg`. */
export function sliceAt(slices: { weight: number }[], deg: number) {
  const at = (((-deg) % 360) + 360) % 360;
  return arcs(slices).findIndex((a) => at >= a.start && at < a.end);
}
