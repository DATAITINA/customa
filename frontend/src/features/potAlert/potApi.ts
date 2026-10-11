// Pot Alert API calls and the WhatsApp message text.
import { apiClient, customerHeaders, type ApiError } from '../../api';

export type ReadyCall = { id: number; item: string; plates_left: number | null; at: string; until: string };
export type MyWatch = { items: string[]; phone_masked: string } | null;
export type PotPublic = { enabled: boolean; items: string[]; ready: ReadyCall[]; my: MyWatch };
export type PotVendor = {
  enabled: boolean;
  stand_name: string;
  slug: string;
  demand: { item: string; waiting: number }[];
  ready: ReadyCall[];
};
export type Watcher = { name: string; phone: string };
export type ReadyResult = { ready: ReadyCall; watchers: Watcher[] };

const pub = (slug: string) => `/public/${encodeURIComponent(slug)}/pot`;
const ven = (slug: string) => `/stands/${encodeURIComponent(slug)}/pot`;

export const potApi = {
  read: (slug: string) => apiClient<PotPublic>('GET', pub(slug), null, customerHeaders(slug)),
  saveWatches: (slug: string, items: string[], phone: string, consent: boolean) =>
    apiClient<{ my: MyWatch }>('PUT', `${pub(slug)}/watches`, { items, phone, consent }, customerHeaders(slug)),
  stopWatches: (slug: string) => apiClient<{ my: null }>('DELETE', `${pub(slug)}/watches`, null, customerHeaders(slug)),

  vendor: (slug: string) => apiClient<PotVendor>('GET', ven(slug)),
  setEnabled: (slug: string, enabled: boolean) => apiClient<PotVendor>('PUT', `${ven(slug)}/settings`, { enabled }),
  ready: (slug: string, item: string, plates_left: number | null) =>
    apiClient<ReadyResult>('POST', `${ven(slug)}/ready`, plates_left ? { item, plates_left } : { item }),
  watchers: (slug: string, id: number) => apiClient<ReadyResult>('GET', `${ven(slug)}/ready/${id}/watchers`),
  end: (slug: string, id: number) => apiClient<{ ready: ReadyCall; ended: boolean }>('POST', `${ven(slug)}/ready/${id}/end`),
};

/** A readable message from an API error (FastAPI detail string, or validation list). */
export function errorText(err: unknown, fallback: string): string {
  const e = err as ApiError | undefined;
  const detail = e?.raw?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0] && typeof detail[0].msg === 'string') return detail[0].msg;
  return e?.message || fallback;
}

export const standLink = (slug: string) => `${window.location.origin}/s/${encodeURIComponent(slug)}`;

const platesText = (n: number | null) => (n ? ` Only ${n} plate${n === 1 ? '' : 's'} left.` : '');

export function readyMessage(o: { name?: string; item: string; standName: string; platesLeft: number | null; slug: string }) {
  const hello = o.name && o.name !== 'Guest' ? `Hello ${o.name}!` : 'Hello!';
  return `${hello} ${o.item} is ready now at ${o.standName}.${platesText(o.platesLeft)} Come and eat: ${standLink(o.slug)}`;
}

export function statusMessage(o: { item: string; standName: string; platesLeft: number | null; slug: string }) {
  return `🔥 ${o.item} is ready now at ${o.standName}.${platesText(o.platesLeft)} Come and eat: ${standLink(o.slug)}`;
}

export const waLink = (phone: string, text: string) => `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;

/** "Afang soup", "Afang soup and Pepper soup", "A, B and C". */
export function joinItems(items: string[]): string {
  if (items.length <= 1) return items[0] ?? '';
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}
