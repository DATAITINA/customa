// A small rotating stamp: a steaming bowl inside a ring of text. Decorative only.
export function FoodStamp({ size = 84 }: { size?: number }) {
  return (
    <svg className="food-stamp" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <path id="stamp-ring" d="M50 50 m-38 0 a38 38 0 1 1 76 0 a38 38 0 1 1 -76 0" />
      </defs>
      <circle cx="50" cy="50" r="48" fill="#FDE6E2" />
      <g className="food-stamp-ring">
        <text fontFamily="Figtree, sans-serif" fontWeight="800" fontSize="9.5" letterSpacing="1.6" fill="#141414">
          <textPath href="#stamp-ring">FRESH FOOD · FRIENDLY FACES · JARA ·</textPath>
        </text>
      </g>
      {/* bowl */}
      <path d="M32 52 H68 C68 64 60 71 50 71 C40 71 32 64 32 52 Z" fill="#F04E30" stroke="#141414" strokeWidth="3" strokeLinejoin="round" />
      <path d="M30 52 H70" stroke="#141414" strokeWidth="3" strokeLinecap="round" />
      {/* steam */}
      <g fill="none" stroke="#141414" strokeWidth="2.6" strokeLinecap="round" className="food-stamp-steam">
        <path d="M42 46 C38 42 46 39 42 34" />
        <path d="M50 46 C46 42 54 39 50 34" />
        <path d="M58 46 C54 42 62 39 58 34" />
      </g>
    </svg>
  );
}
