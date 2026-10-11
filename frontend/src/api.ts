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

export type LastPlates = { left: number; until: string } | null;

// window_seconds is this customer's wait between plates, decided by the server.
// plate_number is the last plate on the card their plates go to now: the Lunch Crew card when
// crew_name is set, else their own card. open_jara: their unredeemed jara codes at this stand.
export type CustomerState = {
  key: string;
  first_name: string | null;
  plate_number: number;
  window_seconds: number;
  seconds_left?: number;
  crew_name?: string | null;
  open_jara?: { code: string }[];
};

// The crew part of a counted plate (Lunch Crew). jara_to names the winner on the crew's jara
// plate (null on other plates); when it is someone else, CountResult.jara is null.
export type CrewCountInfo = {
  name: string;
  plate_number: number;
  plates_for_jara: number;
  jara_to: string | null;
  jara_to_me: boolean;
};

export type StandPublic = {
  stand: { name: string; slug: string; description: string };
  character: Character | null;
  plates_for_jara: number;
  window_seconds: number;
  last_plates: LastPlates;
  customer: CustomerState | null;
};

export type CountResult = {
  customer: CustomerState;
  returning: boolean;
  visit_id: number;
  plate_number: number;
  plates_for_jara: number;
  jara: { code: string } | null;
  crew?: CrewCountInfo | null;
};

export type Dashboard = {
  stand: { name: string; slug: string; description: string; character: Character | null };
  plates_for_jara: number;
  last_plates: LastPlates;
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
export const { apiClient } = configuredApiClient({ isWorkspaceScoped: false });

// The customer's key for a stand lives on their phone only.
const keyName = (slug: string) => `customa:customer:${slug}`;
export const getCustomerKey = (slug: string) => storage.getItem(keyName(slug));
export const setCustomerKey = (slug: string, key: string) => storage.setItem(keyName(slug), key);
export const clearCustomerKey = (slug: string) => storage.removeItem(keyName(slug));

export function customerHeaders(slug: string): RequestInit {
  const key = getCustomerKey(slug);
  return key ? { headers: { 'X-Customer-Key': key } } : {};
}

/** Error thrown by the API client for a non-2xx response. */
export type ApiError = { status?: number; message: string; raw?: { detail?: unknown } };

export const api = {
  stand: (slug: string) => apiClient<StandPublic>('GET', `/public/${slug}`, null, customerHeaders(slug)),
  countPlate: (slug: string, body: { first_name?: string; consent: boolean; source?: 'qr' }) =>
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
  announceLastPlates: (slug: string, plates_left: number, minutes = 90) =>
    apiClient<{ last_plates: LastPlates }>('POST', `/stands/${slug}/last-plates`, { plates_left, minutes }),
  updateCharacter: (slug: string, body: Partial<Character>) =>
    apiClient<StandSummary>('PUT', `/stands/${slug}/character`, body),
  suggestCharacter: (description: string) =>
    apiClient<Partial<Character> & { source: string }>('POST', '/stands/suggest-character', { description }),
};
