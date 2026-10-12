// The animated stand character, ported from the Customa design canvas kit.
// Pure SVG: bodies, colour presets, accessories, expressions and poses.

export type Body = 'pepper' | 'cup' | 'pot' | 'blob';
export type Pose = 'idle' | 'wave' | 'hop' | 'jump';
export type Expression = 'happy' | 'excited' | 'wink' | 'proud';

export const PRESETS: Record<string, { fill: string; acc: string }> = {
  pepper: { fill: '#F04E30', acc: '#FFC926' },
  palm: { fill: '#FF8A1F', acc: '#2BB3F0' },
  yolk: { fill: '#FFC926', acc: '#F04E30' },
  okra: { fill: '#3DBE5A', acc: '#FFC926' },
  lagoon: { fill: '#2BB3F0', acc: '#FF8A1F' },
  adire: { fill: '#6C7BFF', acc: '#FFC926' },
  zobo: { fill: '#CF5DF2', acc: '#3DBE5A' },
  puff: { fill: '#FF7BAC', acc: '#6C7BFF' },
};

type BodySpec = {
  d: string;
  lines: string;
  top: string;
  face: [number, number];
  al: [number, number];
  ar: [number, number];
  legs: [number, number, number];
  hat: [number, number, number];
};

const BODIES: Record<Body, BodySpec> = {
  pepper: {
    d: 'M68 72 C78 52 122 52 134 72 C152 98 146 136 126 160 C114 174 104 184 96 186 C88 188 88 180 92 172 C68 146 56 108 68 72 Z',
    lines: '',
    top: 'M101 60 C100 46 106 36 118 34 M82 64 Q101 56 120 64',
    face: [101, 106], al: [66, 120], ar: [138, 120], legs: [88, 114, 160], hat: [101, 58, 1],
  },
  pot: {
    d: 'M44 90 Q100 46 156 90 Z M48 92 H152 V160 C152 172 144 180 132 180 H68 C56 180 48 172 48 160 Z M92 60 A8 8 0 1 0 108 60 A8 8 0 1 0 92 60 Z',
    lines: 'M44 91 H156 M48 106 C34 106 34 124 48 124 M152 106 C166 106 166 124 152 124',
    top: '',
    face: [100, 132], al: [52, 146], ar: [148, 146], legs: [82, 118, 172], hat: [100, 64, 1],
  },
  cup: {
    d: 'M52 64 H148 C152 64 154 68 154 72 C154 76 152 80 148 80 H144 L132 176 C131 182 127 186 120 186 H80 C73 186 69 182 68 176 L56 80 H52 C48 80 46 76 46 72 C46 68 48 64 52 64 Z',
    lines: 'M58 80 H142',
    top: 'M114 64 L122 30 L140 24',
    face: [100, 120], al: [62, 132], ar: [138, 132], legs: [86, 114, 180], hat: [100, 66, 1],
  },
  blob: {
    d: 'M100 50 C140 46 160 76 156 110 C152 146 140 178 100 178 C58 178 44 150 46 116 C48 78 62 54 100 50 Z',
    lines: '',
    top: '',
    face: [100, 106], al: [50, 126], ar: [154, 126], legs: [84, 116, 170], hat: [100, 52, 1],
  },
};

function face(kind: Expression, x: number, y: number) {
  if (kind === 'excited')
    return {
      eyes: [[x - 12, y, 5.5], [x + 12, y, 5.5]],
      eyesLine: `M${x - 18} ${y - 11} Q${x - 12} ${y - 16} ${x - 6} ${y - 11} M${x + 6} ${y - 11} Q${x + 12} ${y - 16} ${x + 18} ${y - 11}`,
      mouthFill: `M${x - 9} ${y + 10} Q${x} ${y + 28} ${x + 9} ${y + 10} Z`,
      mouthLine: '',
    };
  if (kind === 'wink')
    return {
      eyes: [[x - 12, y, 5], [x + 12, y, 0]],
      eyesLine: `M${x + 6} ${y + 1} Q${x + 12} ${y - 6} ${x + 18} ${y + 1}`,
      mouthFill: '',
      mouthLine: `M${x - 9} ${y + 11} Q${x + 1} ${y + 20} ${x + 10} ${y + 9}`,
    };
  if (kind === 'proud')
    return {
      eyes: [[x - 12, y, 0], [x + 12, y, 0]],
      eyesLine: `M${x - 18} ${y + 2} Q${x - 12} ${y - 6} ${x - 6} ${y + 2} M${x + 6} ${y + 2} Q${x + 12} ${y - 6} ${x + 18} ${y + 2}`,
      mouthFill: '',
      mouthLine: `M${x - 7} ${y + 12} Q${x + 2} ${y + 18} ${x + 10} ${y + 10}`,
    };
  return {
    eyes: [[x - 12, y, 5], [x + 12, y, 5]],
    eyesLine: '',
    mouthFill: '',
    mouthLine: `M${x - 8} ${y + 11} Q${x} ${y + 18} ${x + 8} ${y + 11}`,
  };
}

const EASE = '0.45 0 0.55 1';
function bobFor(pose: Pose) {
  if (pose === 'hop')
    return { values: '0 0;0 -12;0 0;0 0', times: '0;0.12;0.26;1', splines: `0.3 0 0.5 1;0.5 0 0.7 1;${EASE}`, dur: '1.6s' };
  if (pose === 'jump')
    return { values: '0 0;0 -24;0 2;0 0;0 0', times: '0;0.2;0.38;0.46;1', splines: `0.2 0 0.4 1;0.6 0 0.8 1;${EASE};${EASE}`, dur: '1.4s' };
  return { values: '0 0;0 -4;0 0', times: '0;0.5;1', splines: `${EASE};${EASE}`, dur: '2.4s' };
}

const reduceMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

type Props = {
  body?: string;
  color?: string;
  accessory?: string;
  expression?: Expression;
  pose?: Pose;
  size?: number;
};

export function Character({
  body = 'pepper',
  color = 'pepper',
  accessory = 'headwrap',
  expression = 'happy',
  pose = 'idle',
  size = 180,
}: Props) {
  const bodyKey = (body in BODIES ? body : 'pepper') as Body;
  const b = BODIES[bodyKey];
  const c = PRESETS[color] ?? PRESETS.pepper;
  const animate = !reduceMotion;
  const [fx, fy] = b.face;
  const [alx, aly] = b.al;
  const [arx, ary] = b.ar;
  const [lx, rx, hip] = b.legs;
  const [hx, hy, hs] = b.hat;

  const up = pose === 'jump';
  const rightUp = up || pose === 'wave';
  const armL = up
    ? `M${alx} ${aly} Q${alx - 22} ${aly - 6} ${alx - 26} ${aly - 36}`
    : `M${alx} ${aly} Q${alx - 16} ${aly + 12} ${alx - 20} ${aly + 34}`;
  const armR =
    (rightUp
      ? `M${arx} ${ary} Q${arx + 22} ${ary - 6} ${arx + 26} ${ary - 36}`
      : `M${arx} ${ary} Q${arx + 16} ${ary + 12} ${arx + 20} ${ary + 34}`) +
    (pose === 'wave' ? ` M${arx + 36} ${ary - 50} l7 -6 M${arx + 42} ${ary - 36} l9 -1` : '');
  const r = (deg: number) => `${deg} ${arx} ${ary}`;
  const waveValues = [r(0), r(-16), r(6), r(-16), r(6), r(0), r(0)].join(';');

  const bent = pose === 'jump' || pose === 'hop';
  const legs = bent
    ? `M${lx} ${hip} Q${lx - 16} ${hip + 20} ${lx - 8} ${hip + 38} M${rx} ${hip} Q${rx + 16} ${hip + 20} ${rx + 8} ${hip + 38}`
    : `M${lx} ${hip} L${lx} 220 H${lx - 11} M${rx} ${hip} L${rx} 220 H${rx + 11}`;
  const lift = pose === 'jump' ? -26 : pose === 'hop' ? -10 : 0;
  const shadowRx = pose === 'jump' ? 28 : pose === 'hop' ? 38 : 46;

  const f = face(expression, fx, fy);
  const glasses = accessory === 'sunglasses';
  const hat = accessory === 'headwrap' || accessory === 'chef';
  const bob = bobFor(pose);

  let accT = '';
  let accFill = '';
  let accWhite = '';
  let accBlack = '';
  let accLine = '';
  if (accessory === 'headwrap') {
    accT = `translate(${hx} ${hy}) scale(${hs})`;
    accFill = 'M-48 16 C-54 -18 -20 -34 4 -30 C30 -34 54 -16 48 16 C24 4 -24 4 -48 16 Z M16 -22 C26 -52 62 -50 50 -24 C44 -12 28 -12 16 -22 Z';
    accLine = 'M-36 2 C-16 -10 16 -12 38 0 M-26 -14 C-8 -22 10 -22 24 -16';
  } else if (accessory === 'chef') {
    accT = `translate(${hx} ${hy}) scale(${hs})`;
    accWhite = 'M-26 10 V-6 C-44 -8 -46 -40 -22 -38 C-18 -60 18 -60 22 -38 C46 -40 44 -8 26 -6 V10 Z';
    accLine = 'M-26 -2 H26';
  } else if (glasses) {
    accT = `translate(${fx} ${fy})`;
    accBlack = 'M-27 -8 H-3 V-2 C-3 6 -8 10 -15 10 C-22 10 -27 6 -27 -2 Z M3 -8 H27 V-2 C27 6 22 10 15 10 C8 10 3 6 3 -2 Z';
    accLine = 'M-3 -6 H3 M-27 -6 L-33 -10 M27 -6 L33 -10';
  } else if (accessory === 'bowtie') {
    accT = `translate(${fx} ${fy + 32})`;
    accFill = 'M0 0 L-18 -11 C-21 -12 -23 -10 -23 -7 V7 C-23 10 -21 12 -18 11 Z M0 0 L18 -11 C21 -12 23 -10 23 -7 V7 C23 10 21 12 18 11 Z';
    accBlack = 'M-5 -5 H5 V5 H-5 Z';
  }

  const eye = (e: number[]) => {
    const [x, y, rr] = e;
    const rad = glasses ? 0 : rr;
    return { x, y, rad, blink: [rad, rad, rad * 0.12, rad, rad].join(';') };
  };
  const eyes = f.eyes.map(eye);
  const blush = `M${fx - 27} ${fy + 10} a6 3.5 0 1 0 12 0 a6 3.5 0 1 0 -12 0 Z M${fx + 15} ${fy + 10} a6 3.5 0 1 0 12 0 a6 3.5 0 1 0 -12 0 Z`;
  const stroke = { stroke: '#141414', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

  return (
    // overflow visible: when the character bobs or jumps, its hat may rise above the frame.
    <svg width={size} height={Math.round(size * 1.2)} viewBox="0 0 200 240" role="img" aria-label={`${bodyKey} character`} style={{ overflow: 'visible' }}>
      <ellipse cx="100" cy="226" rx={shadowRx} ry="6" fill="#141414" opacity="0.08" />
      <g transform={`translate(0 ${lift})`}>
        <g>
          {animate && (
            <animateTransform attributeName="transform" type="translate" values={bob.values} keyTimes={bob.times}
              keySplines={bob.splines} calcMode="spline" dur={bob.dur} repeatCount="indefinite" additive="sum" />
          )}
          <path d={legs} fill="none" strokeWidth={5} {...stroke} />
          <path d={armL} fill="none" strokeWidth={5} {...stroke} />
          <g>
            {animate && pose === 'wave' && (
              <animateTransform attributeName="transform" type="rotate" values={waveValues}
                keyTimes="0;0.1;0.2;0.3;0.4;0.5;1" dur="2.4s" repeatCount="indefinite" additive="sum" />
            )}
            <path d={armR} fill="none" strokeWidth={5} {...stroke} />
          </g>
          <path d={b.d} fill={c.fill} />
          <path d={b.lines + (hat ? '' : ' ' + b.top)} fill="none" strokeWidth={5} {...stroke} />
          <path d={blush} fill="#FF5C8A" opacity="0.45" />
          {eyes.map((e, i) => (
            <ellipse key={i} cx={e.x} cy={e.y} rx={e.rad} ry={e.rad} fill="#141414">
              {animate && (
                <animate attributeName="ry" values={e.blink} keyTimes="0;0.92;0.95;0.98;1" dur="3.6s" repeatCount="indefinite" />
              )}
            </ellipse>
          ))}
          {f.mouthFill && <path d={f.mouthFill} fill="#141414" />}
          <path d={(glasses ? '' : f.eyesLine) + ' ' + f.mouthLine} fill="none" strokeWidth={4.5} {...stroke} />
          {accT && (
            <g transform={accT}>
              {accFill && <path d={accFill} fill={c.acc} />}
              {accWhite && <path d={accWhite} fill="#FFFFFF" stroke="#141414" strokeWidth={4} strokeLinejoin="round" />}
              {accBlack && <path d={accBlack} fill="#141414" />}
              {accLine && <path d={accLine} fill="none" strokeWidth={4} {...stroke} />}
            </g>
          )}
        </g>
      </g>
    </svg>
  );
}
