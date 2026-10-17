// Light / System / Dark. The choice is kept on this phone; "System" follows the phone's setting
// (and changes with it). index.html applies it before the first paint.
export type ThemePick = 'light' | 'system' | 'dark';

const KEY = 'customa:theme';
const media = () => window.matchMedia?.('(prefers-color-scheme: dark)');

export function getThemePick(): ThemePick {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch { /* storage blocked */ }
  return 'system';
}

export function applyTheme(pick: ThemePick) {
  const dark = pick === 'dark' || (pick === 'system' && !!media()?.matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (meta) meta.content = dark ? '#15110E' : '#FDE6E2';
}

export function setThemePick(pick: ThemePick) {
  try { localStorage.setItem(KEY, pick); } catch { /* storage blocked: still applied now */ }
  applyTheme(pick);
}

// Keep "System" in step when the phone switches between light and dark.
export function followSystem(): () => void {
  const m = media();
  if (!m) return () => {};
  const onChange = () => { if (getThemePick() === 'system') applyTheme('system'); };
  m.addEventListener?.('change', onChange);
  return () => m.removeEventListener?.('change', onChange);
}
