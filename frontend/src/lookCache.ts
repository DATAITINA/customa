// Remembers each stand's character look on this phone, so loading screens show that stand's own
// character (not the default pepper) from the second visit on. Key: the stand's slug, plus
// "vendor" for the vendor's own dashboard.
type Look = { body?: string; color?: string; accessory?: string };

const key = (k: string) => `customa:look:${k}`;

export function rememberLook(k: string, c: Look | null | undefined) {
  if (!c?.body) return;
  try { localStorage.setItem(key(k), JSON.stringify({ body: c.body, color: c.color, accessory: c.accessory })); } catch { /* private mode */ }
}

// The look for the page we are on: /s/<slug>/..., /qr/<slug>, or /vendor.
export function lookForThisPage(): Look | null {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const k = (parts[0] === 's' || parts[0] === 'qr') && parts[1] ? parts[1] : parts[0] === 'vendor' ? 'vendor' : null;
  if (!k) return null;
  try { return JSON.parse(localStorage.getItem(key(k)) || 'null'); } catch { return null; }
}
