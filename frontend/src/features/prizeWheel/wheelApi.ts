// Prize Wheel: the customer's spins and prizes, the vendor's wheel and the jara code check.
import { apiClient, customerHeaders } from '../../api';

export type Weight = 1 | 3 | 5; // rarely, sometimes, often: also the slice's size on the wheel

export type WheelSlice = { id: number; name: string; weight: number; photo: string | null };
export type WheelItemPublic = WheelSlice & { description: string | null; prize: string | null };
export type WheelItemVendor = WheelItemPublic & { available: boolean };

export type WonPrize = {
  code: string;
  name: string;
  prize: string | null;
  photo: string | null;
  expires_at: string;
  redeemed: boolean;
};

export type WheelState = {
  enabled: boolean;
  items: WheelItemPublic[];
  spins: number[]; // jara ids that can spin
  won: (WonPrize & { jara_id: number })[];
};

// The server's spin: the wheel as it was, the slice it stopped on and where in it (0..1).
export type SpinResult = { jara_id: number; wheel: WheelSlice[]; slot: number; landing: number; prize: WonPrize };

export type VendorWheel = {
  enabled: boolean;
  items: WheelItemVendor[];
  max_items: number;
  min_to_publish: number;
  valid_days: number;
  stats: { spins: number; given: number };
};

export type ItemInput = {
  name?: string;
  description?: string | null;
  prize?: string | null;
  weight?: Weight;
  available?: boolean;
  photo?: string | null; // a data URL replaces it, null removes it
};

export type CheckStatus = 'valid' | 'redeemed' | 'expired' | 'not_spun' | 'other_stand' | 'unknown';
export type CodeCheck = {
  status: CheckStatus;
  code: string;
  customer?: string;
  issued_at?: string;
  prize?: {
    name: string;
    prize: string | null;
    photo: string | null;
    spun_at: string;
    expires_at: string;
    redeemed_at: string | null;
  } | null;
};

const pub = (slug: string) => `/public/${slug}/wheel`;
const vendor = (slug: string) => `/stands/${slug}/wheel`;

export const wheelApi = {
  state: (slug: string) => apiClient<WheelState>('GET', pub(slug), null, customerHeaders(slug)),
  spin: (slug: string, jaraId: number) =>
    apiClient<SpinResult>('POST', `${pub(slug)}/spin`, { jara_id: jaraId }, customerHeaders(slug)),

  vendor: (slug: string) => apiClient<VendorWheel>('GET', vendor(slug)),
  addItem: (slug: string, item: ItemInput) => apiClient<VendorWheel>('POST', `${vendor(slug)}/items`, item),
  updateItem: (slug: string, id: number, item: ItemInput) =>
    apiClient<VendorWheel>('PUT', `${vendor(slug)}/items/${id}`, item),
  removeItem: (slug: string, id: number) => apiClient<VendorWheel>('DELETE', `${vendor(slug)}/items/${id}`),
  publish: (slug: string, enabled: boolean) => apiClient<VendorWheel>('PUT', vendor(slug), { enabled }),
  check: (slug: string, code: string) =>
    apiClient<CodeCheck>('GET', `/stands/${slug}/jara/${encodeURIComponent(code.trim())}`),
};

export const CHANCES: { weight: Weight; label: string; hint: string }[] = [
  { weight: 5, label: 'Often', hint: 'Big slice' },
  { weight: 3, label: 'Sometimes', hint: 'Normal slice' },
  { weight: 1, label: 'Rarely', hint: 'Small slice' },
];
