// The Customa logo: a C that is a speech bubble and a plate, with the jara dot.
export function LogoMark({ size = 32, ink = '#141414' }: { size?: number; ink?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M47.3 17.1 A20 20 0 1 0 47.3 42.9" fill="none" stroke={ink} strokeWidth="9" strokeLinecap="round" />
      <path d="M19.5 41.5 L10.5 55.5 L27 48.5 Z" fill={ink} stroke={ink} strokeWidth="3" strokeLinejoin="round" />
      <circle cx="32" cy="30" r="7" fill="#F04E30" />
    </svg>
  );
}

export function Logo({ size = 28, ink = '#141414' }: { size?: number; ink?: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: size * 0.22, color: ink }} aria-label="Customa">
      <LogoMark size={size} ink={ink} />
      <span style={{ fontFamily: 'var(--display)', fontSize: size * 0.82, lineHeight: 1, letterSpacing: '0.01em' }}>customa</span>
    </span>
  );
}
