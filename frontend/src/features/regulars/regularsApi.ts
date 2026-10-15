// Regular-arrived alert: "Who's here now" actions for staff, the vendor's phone ping, and the
// customer's own "my usual".
import { apiClient, customerHeaders } from '../../api';

// One customer counted in the last ARRIVAL_WINDOW_MINUTES (comes with the dashboard).
export type HereNow = {
  id: number;
  name: string | null; // only if the customer gave it
  visit_number: number;
  visit_label: string; // "9th visit" or "New face: first plate 👋"
  returning: boolean;
  last_came: string | null; // "3 days ago"
  jara: 'next_is_jara' | 'has_jara' | null;
  greeting: string; // what staff can say, in the stand's voice
  usual: string | null; // only if the customer chose to share it
  at: string;
  greeted_at: string | null;
};

export type PingInfo = { available: boolean; public_key: string | null; phones: number };

const vendor = (slug: string) => `/stands/${slug}/arrivals`;

export const regularsApi = {
  greeted: (slug: string, id: number) => apiClient<{ id: number; greeted_at: string }>('POST', `${vendor(slug)}/${id}/greeted`),
  pingInfo: (slug: string) => apiClient<PingInfo>('GET', `${vendor(slug)}/ping`),
  pingOn: (slug: string, sub: PushSubscriptionJSON) => apiClient<{ subscribed: boolean }>('POST', `${vendor(slug)}/ping`, sub),
  pingOff: (slug: string, endpoint: string) => apiClient<{ subscribed: boolean }>('POST', `${vendor(slug)}/ping/off`, { endpoint }),

  usual: (slug: string) => apiClient<{ usual: string | null; menu: string[] }>('GET', `/public/${slug}/usual`, null, customerHeaders(slug)),
  setUsual: (slug: string, item: string) => apiClient<{ usual: string }>('PUT', `/public/${slug}/usual`, { item }, customerHeaders(slug)),
  clearUsual: (slug: string) => apiClient<{ usual: null }>('DELETE', `/public/${slug}/usual`, null, customerHeaders(slug)),
};
