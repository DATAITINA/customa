// All calls to the Customa backend go through @msflib/core's configured API
// client: one place for the base URL, the bearer token and error handling.
import { configuredApiClient, storage } from '@msflib/core';

export type Character = {
  name: string;
  body: string;
  color: string;
  accessory: string;
  greeting: string;
  personality: string;
  menu: { item: string; price: number }[];
};

export type CustomerState = { key: string; first_name: string | null; plate_number: number };

export type StandPublic = {
  stand: { name: string; slug: string; description: string };
  character: Character | null;
  plates_for_jara: number;
  window_seconds: number;
  customer: CustomerState | null;
};

export type CountResult = {
  customer: CustomerState;
  returning: boolean;
  visit_id: number;
  plate_number: number;
  plates_for_jara: number;
  jara: { code: string } | null;
};

export type Dashboard = {
  stand: { name: string; slug: string; description: string; character: Character | null };
  plates_for_jara: number;
  stats: {
    plates_today: number;
    customers: number;
    returning_customers: number;
    jara_issued: number;
    average_rating: number | null;
  };
  recent_visits: { id: number; name: string; plate_number: number; stars: number | null; at: string }[];
  open_jara: { code: string; name: string; at: string }[];
  recent_questions: { id: number; who: string; question: string; at: string }[];
};

export type StandSummary = { name: string; slug: string; description: string; character: Character | null };

// Customer and stand routes are not workspace-scoped on the client: the stand
// slug is already in the path.
const { apiClient } = configuredApiClient({ isWorkspaceScoped: false });

// The customer's key for a stand lives on their phone only.
const keyName = (slug: string) => `customa:customer:${slug}`;
export const getCustomerKey = (slug: string) => storage.getItem(keyName(slug));
export const setCustomerKey = (slug: string, key: string) => storage.setItem(keyName(slug), key);
export const clearCustomerKey = (slug: string) => storage.removeItem(keyName(slug));

function customerHeaders(slug: string): RequestInit {
  const key = getCustomerKey(slug);
  return key ? { headers: { 'X-Customer-Key': key } } : {};
}

/** Error thrown by the API client for a non-2xx response. */
export type ApiError = { status?: number; message: string; raw?: { detail?: unknown } };

export const api = {
  stand: (slug: string) => apiClient<StandPublic>('GET', `/public/${slug}`, null, customerHeaders(slug)),
  countPlate: (slug: string, body: { first_name?: string; consent: boolean }) =>
    apiClient<CountResult>('POST', `/public/${slug}/visits`, body, customerHeaders(slug)),
  rate: (slug: string, visitId: number, stars: number) =>
    apiClient('POST', `/public/${slug}/ratings`, { visit_id: visitId, stars }, customerHeaders(slug)),
  deleteMe: (slug: string) => apiClient('DELETE', `/public/${slug}/me`, null, customerHeaders(slug)),
  chat: (slug: string, message: string, history: { role: string; content: string }[]) =>
    apiClient<{ reply: string; source: string }>(
      'POST',
      `/public/${slug}/chat`,
      { message, history },
      customerHeaders(slug),
    ),

  myStands: () => apiClient<StandSummary[]>('GET', '/stands/mine'),
  createStand: (body: { name: string; description: string; character: Partial<Character> & { name: string } }) =>
    apiClient<StandSummary>('POST', '/stands', body),
  dashboard: (slug: string) => apiClient<Dashboard>('GET', `/stands/${slug}/dashboard`),
  redeemJara: (slug: string, code: string) =>
    apiClient<{ code: string; redeemed: boolean }>('POST', `/stands/${slug}/jara/${encodeURIComponent(code)}/redeem`),
  updateCharacter: (slug: string, body: Partial<Character>) =>
    apiClient<StandSummary>('PUT', `/stands/${slug}/character`, body),
  suggestCharacter: (description: string) =>
    apiClient<Partial<Character> & { source: string }>('POST', '/stands/suggest-character', { description }),
};
