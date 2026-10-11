// Plate Ajo API calls. Money never passes through Customa: the customer transfers to the
// vendor's own account and Customa keeps the plate count.
import { apiClient, customerHeaders, type ApiError } from '../../api';

export type BundleStatus = 'pending' | 'active' | 'rejected' | 'finished' | 'closed';

export type Bundle = {
  id: number;
  item: string;
  unit_price: number;
  plates_total: number;
  plates_used: number;
  plates_left: number;
  status: BundleStatus;
  payer_name: string | null;
  created_at: string;
};

export type BankDetails = { bank_name: string; account_number: string; account_name: string };

export type AjoPublic = {
  available: boolean;
  bank: BankDetails | null;
  items: { item: string; price: number }[];
  bundle_sizes: number[];
  bundles: Bundle[];
};

export type UseResult = {
  bundle: Bundle;
  use: { item: string; plate_number: number; plates_total: number; at: string };
  stamp: {
    counted: boolean;
    plate_number: number | null;
    jara: { code: string } | null;
    // Set when the plate went on a Lunch Crew card.
    crew: { name: string; plate_number: number; plates_for_jara: number; jara_to: string | null; jara_to_me: boolean } | null;
  };
};

export type AjoVendor = {
  enabled: boolean;
  bank_name: string | null;
  account_number: string | null;
  account_name: string | null;
  available: boolean;
  pending: {
    id: number;
    name: string;
    payer_name: string | null;
    item: string;
    plates_total: number;
    unit_price: number;
    total: number;
    created_at: string;
  }[];
  active: {
    id: number;
    name: string;
    item: string;
    unit_price: number;
    plates_total: number;
    plates_used: number;
    plates_left: number;
    confirmed_at: string | null;
  }[];
  served_today: { id: number; name: string; item: string; plate_number: number; plates_total: number; at: string }[];
};

export type AjoSettings = {
  enabled: boolean;
  bank_name?: string;
  account_number?: string;
  account_name?: string;
};

const pub = (slug: string) => `/public/${encodeURIComponent(slug)}/ajo`;
const ven = (slug: string) => `/stands/${encodeURIComponent(slug)}/ajo`;

export const ajoApi = {
  read: (slug: string) => apiClient<AjoPublic>('GET', pub(slug), null, customerHeaders(slug)),
  start: (slug: string, body: { item: string; plates: number; payer_name: string; unit_price: number }) =>
    apiClient<{ bundle: Bundle }>('POST', `${pub(slug)}/bundles`, body, customerHeaders(slug)),
  use: (slug: string) => apiClient<UseResult>('POST', `${pub(slug)}/use`, null, customerHeaders(slug)),

  vendor: (slug: string) => apiClient<AjoVendor>('GET', ven(slug)),
  saveSettings: (slug: string, body: AjoSettings) => apiClient<AjoVendor>('PUT', `${ven(slug)}/settings`, body),
  confirm: (slug: string, id: number) => apiClient<{ bundle: Bundle }>('POST', `${ven(slug)}/bundles/${id}/confirm`),
  reject: (slug: string, id: number) => apiClient<{ bundle: Bundle }>('POST', `${ven(slug)}/bundles/${id}/reject`),
  close: (slug: string, id: number) => apiClient<{ bundle: Bundle }>('POST', `${ven(slug)}/bundles/${id}/close`),
};

export const naira = (n: number) => `₦${n.toLocaleString('en-NG')}`;

/** Server times are naive UTC. */
export const parseUtc = (iso: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);

export const timeOf = (iso: string) =>
  parseUtc(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/** A readable message from an API error: the server's own words when it sent some. */
export function errorText(err: unknown, fallback: string): string {
  const e = err as ApiError | undefined;
  const detail = e?.raw?.detail;
  if (typeof detail === 'string') return detail;
  if (e?.status === 422 || !e?.status) return fallback;
  return e.message || fallback;
}
