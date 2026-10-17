// Plan the next visit ("When you go come back?"): the customer's plan and the vendor's numbers.
import { API_BASE } from '../../application';
import { apiClient, customerHeaders, getCustomerKey } from '../../api';

export type Slot = 'morning' | 'lunch' | 'evening';
export type Plan = {
  id: number;
  day: string;
  slot: Slot;
  status: string;
  label: string; // "Thursday 16 Oct · Lunch (11am–3pm)"
  when: string; // "Thursday for lunch"
  confirm: string; // "Deal! I go dey expect you Thursday for lunch 🙌"
  reminder: 'push' | 'sms' | null;
  reminder_at: string | null;
};
export type PlanState = {
  plan: Plan | null;
  options: { days: { date: string; label: string; open: Slot[] }[]; slots: { key: Slot; label: string; hours: string }[] };
  reminder: 'push' | 'sms' | null;
};
export type VendorPlans = {
  coming_today: { total: number; by_slot: Record<Slot, number>; names: { name: string; slot: Slot; came: boolean }[] };
  kept_week: { kept: number; total: number };
};

const path = (slug: string) => `/public/${slug}/plan`;

export const plansApi = {
  state: (slug: string) => apiClient<PlanState>('GET', path(slug), null, customerHeaders(slug)),
  make: (slug: string, day: string, slot: Slot) => apiClient<PlanState>('PUT', path(slug), { day, slot }, customerHeaders(slug)),
  cancel: (slug: string) => apiClient<PlanState>('DELETE', path(slug), null, customerHeaders(slug)),
  // "Add to my calendar": a link the phone opens (the customer's key goes in the address).
  calendarUrl: (slug: string) => `${API_BASE}${path(slug)}.ics?k=${encodeURIComponent(getCustomerKey(slug) ?? '')}`,
};
