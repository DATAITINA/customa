// A bold rotating sticker: a scalloped black seal, the Customa loop in a ring of text,
// and a steaming bowl with the jara dot. Decorative only.

// Scalloped seal edge: 28 bumps around the centre (computed once, same on every render).
const SEAL = (() => {
  const points = 56;
  const pts: string[] = [];
  for (let i = 0; i < points; i++) {
    const a = (i / points) * Math.PI * 2;
    const r = i % 2 === 0 ? 48 : 44.5;
    pts.push(`${(50 + r * Math.cos(a)).toFixed(2)},${(50 + r * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(' ');
})();

export function FoodStamp({ size = 88 }: { size?: number }) {
  return (
    <svg className="food-stamp" width={size} height={size} viewBox="-4 -4 108 108" aria-hidden="true">
      <defs>
        <path id="stamp-ring" d="M50 50 m-34 0 a34 34 0 1 1 68 0 a34 34 0 1 1 -68 0" />
      </defs>
      {/* sticker shadow, then the seal */}
      <polygon points={SEAL} fill="#F04E30" transform="translate(3 3)" />
      <polygon points={SEAL} fill="#141414" />
      <circle cx="50" cy="50" r="41" fill="none" stroke="#FFFFFF" strokeOpacity="0.28" strokeWidth="1" strokeDasharray="2 3" />
      <g className="food-stamp-ring">
        <text fontFamily="'Lilita One', sans-serif" fontSize="10.4" letterSpacing="1.15" fill="#FFFFFF">
          <textPath href="#stamp-ring">SCAN · EAT · COME BACK · GET JARA ·</textPath>
        </text>
      </g>
      {/* inner plate */}
      <circle cx="50" cy="50" r="23" fill="#FDE6E2" />
      {/* bowl with the jara dot */}
      <path d="M36 50 H64 C64 59.5 57.5 65 50 65 C42.5 65 36 59.5 36 50 Z" fill="#F04E30" stroke="#141414" strokeWidth="2.6" strokeLinejoin="round" />
      <path d="M34.5 50 H65.5" stroke="#141414" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="50" cy="57" r="2.6" fill="#FDE6E2" />
      {/* steam */}
      <g fill="none" stroke="#141414" strokeWidth="2.3" strokeLinecap="round" className="food-stamp-steam">
        <path d="M44 45 C41 42 47 39.5 44 36" />
        <path d="M50 45 C47 42 53 39.5 50 36" />
        <path d="M56 45 C53 42 59 39.5 56 36" />
      </g>
    </svg>
  );
}
