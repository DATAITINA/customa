import { useEffect, useState } from 'react';
import { followSystem, getThemePick, setThemePick, type ThemePick } from '../theme';

const Sun = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
  </svg>
);
const Phone = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
    <path d="M10.5 18.5h3" />
  </svg>
);
const Moon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
  </svg>
);

const OPTIONS: { pick: ThemePick; label: string; Icon: () => JSX.Element }[] = [
  { pick: 'light', label: 'Light', Icon: Sun },
  { pick: 'system', label: 'System', Icon: Phone },
  { pick: 'dark', label: 'Dark', Icon: Moon },
];

// The current choice, kept in step across every theme control and with the phone ("System").
function useThemePick(): ThemePick {
  const [pick, setPick] = useState<ThemePick>(getThemePick);
  useEffect(() => {
    const stop = followSystem();
    const onPick = (e: Event) => setPick((e as CustomEvent<ThemePick>).detail);
    window.addEventListener('customa:theme', onPick);
    return () => { stop(); window.removeEventListener('customa:theme', onPick); };
  }, []);
  return pick;
}

// One round button for headers: tap to go Light → Dark → System. Shows the current choice.
export function ThemeButton() {
  const pick = useThemePick();
  const current = OPTIONS.find((o) => o.pick === pick) ?? OPTIONS[1];
  const next: ThemePick = pick === 'light' ? 'dark' : pick === 'dark' ? 'system' : 'light';
  return (
    <button type="button" className="theme-btn" onClick={() => setThemePick(next)}
      aria-label={`Theme: ${current.label}. Tap for ${next}`} title={`Theme: ${current.label}`}>
      <current.Icon />
    </button>
  );
}

// Light / System / Dark, at the bottom of every page.
export function ThemeSwitch() {
  const pick = useThemePick();
  return (
    <footer className="theme-footer">
      <div className="theme-switch" role="radiogroup" aria-label="Theme">
        {OPTIONS.map(({ pick: p, label, Icon }) => (
          <button key={p} type="button" role="radio" aria-checked={pick === p} onClick={() => setThemePick(p)}>
            <Icon />{label}
          </button>
        ))}
      </div>
    </footer>
  );
}
