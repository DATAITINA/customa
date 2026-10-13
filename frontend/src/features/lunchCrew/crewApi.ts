// Lunch Crew API calls and types (customer routes use the customer's key, vendor routes the login).
import { apiClient, customerHeaders } from '../../api';

export type CrewMemberView = { name: string; is_me: boolean; is_next: boolean };

export type CrewView = {
  name: string;
  code: string;
  members: CrewMemberView[];
  plate_number: number; // plates on the current crew card (0 right after a jara)
  plates_for_jara: number;
  next_jara_to: string | null;
  my_turn_position: number | null; // 1 = the next crew jara is mine
  max_members: number;
};

export type CrewInvite = { name: string; code: string; members_count: number; max_members: number; full: boolean };

export type CrewPublic = {
  enabled: boolean;
  max_members: number;
  plates_for_jara: number;
  crew: CrewView | null;
  invite: CrewInvite | null;
};

export type VendorCrew = {
  name: string;
  members: string[];
  plate_number: number;
  plates_for_jara: number;
  next_jara_to: string | null;
};

export type VendorCrews = { enabled: boolean; max_members: number; plates_for_jara: number; crews: VendorCrew[] };

export const crewApi = {
  get: (slug: string, code?: string | null) =>
    apiClient<CrewPublic>(
      'GET',
      `/public/${encodeURIComponent(slug)}/crew${code ? `?code=${encodeURIComponent(code)}` : ''}`,
      null,
      customerHeaders(slug),
    ),
  create: (slug: string, name: string) =>
    apiClient<CrewPublic>('POST', `/public/${encodeURIComponent(slug)}/crew`, { name }, customerHeaders(slug)),
  join: (slug: string, code: string) =>
    apiClient<CrewPublic>('POST', `/public/${encodeURIComponent(slug)}/crew/join`, { code }, customerHeaders(slug)),
  leave: (slug: string) => apiClient<CrewPublic>('POST', `/public/${encodeURIComponent(slug)}/crew/leave`, null, customerHeaders(slug)),

  vendor: (slug: string) => apiClient<VendorCrews>('GET', `/stands/${encodeURIComponent(slug)}/crew`),
  setEnabled: (slug: string, enabled: boolean) =>
    apiClient<VendorCrews>('PUT', `/stands/${encodeURIComponent(slug)}/crew/settings`, { enabled }),
};

// The invite code in a share link: /s/<slug>?crew=CODE
// The invite code from a crew share link (?crew=). Kept for this browser tab too: a friend
// who opens the link away from the stand still has it after scanning the stand's QR code.
const INVITE_KEY = 'customa:crew-invite';
export function inviteCodeFromUrl(): string | null {
  const fromUrl = new URLSearchParams(window.location.search).get('crew');
  try {
    if (fromUrl) sessionStorage.setItem(INVITE_KEY, fromUrl);
    return fromUrl ?? sessionStorage.getItem(INVITE_KEY);
  } catch {
    return fromUrl;
  }
}

export function dropInviteFromUrl() {
  try { sessionStorage.removeItem(INVITE_KEY); } catch { /* storage blocked: nothing kept */ }
  const params = new URLSearchParams(window.location.search);
  if (!params.has('crew')) return;
  params.delete('crew');
  const qs = params.toString();
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
}
