// Leftover-food alerts (web push): turn a stand's alerts on or off on this phone.
import { apiClient, customerHeaders } from '../../api';

export type AlertsInfo = { available: boolean; public_key: string | null };

const pub = (slug: string) => `/public/${slug}/alerts`;

export const alertsApi = {
  info: (slug: string) => apiClient<AlertsInfo>('GET', pub(slug)),
  turnOn: (slug: string, subscription: PushSubscriptionJSON) =>
    apiClient<{ subscribed: boolean }>('POST', pub(slug), subscription, customerHeaders(slug)),
  turnOff: (slug: string, endpoint: string) =>
    apiClient<{ subscribed: boolean }>('POST', `${pub(slug)}/off`, { endpoint }, customerHeaders(slug)),
};

// What this phone can do. iPhones get web push only from the Home Screen app (iOS 16.4+).
export type PushSupport = 'ok' | 'ios-install' | 'unsupported';

export function isIos(): boolean {
  return /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

export function isStandalone(): boolean {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function pushSupport(): PushSupport {
  const hasPush = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  if (isIos() && !isStandalone()) return 'ios-install';
  return hasPush ? 'ok' : 'unsupported';
}

export function keyBytes(base64url: string): Uint8Array {
  const pad = '='.repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

// This phone has turned on alerts for this stand (the browser's push subscription is shared
// by every stand, so the per-stand choice is kept here and on the server).
const onKey = (slug: string) => `customa:alerts:${slug}`;
export function alertsOnHere(slug: string): boolean {
  try { return localStorage.getItem(onKey(slug)) === '1'; } catch { return false; }
}
export function rememberAlerts(slug: string, on: boolean) {
  try { if (on) localStorage.setItem(onKey(slug), '1'); else localStorage.removeItem(onKey(slug)); } catch { /* not kept */ }
}
