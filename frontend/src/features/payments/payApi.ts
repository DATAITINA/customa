// Pay for a plate: Paystack (test mode) or cash the vendor confirms. A paid plate is a stamp.
import { apiClient, customerHeaders } from '../../api';

export type Payment = {
  id: number;
  reference: string;
  method: 'paystack' | 'cash';
  status: 'pending' | 'paid' | 'failed' | 'cancelled';
  item: string;
  amount: number;
  code: string;
  stamped: boolean;
  paid_at: string | null;
};
export type PayState = {
  enabled: boolean;
  card: boolean;
  test_mode: boolean;
  menu: { item: string; price: number }[];
  pending_cash: Payment | null;
};
export type VendorRow = Payment & { name: string; at: string };
export type Today = {
  enabled: boolean;
  total: number;
  count: number;
  by_method: { paystack: number; cash: number };
  paid: VendorRow[];
  waiting_cash: VendorRow[];
  card_ready: boolean;
  card_problem: string | null;
};

const pub = (slug: string) => `/public/${slug}/pay`;
const vendor = (slug: string) => `/stands/${slug}/payments`;

export const naira = (n: number) => `₦${n.toLocaleString('en-NG')}`;

export const payApi = {
  state: (slug: string) => apiClient<PayState>('GET', pub(slug), null, customerHeaders(slug)),
  start: (slug: string, item: string, method: 'paystack' | 'cash') =>
    apiClient<{ payment: Payment; checkout_url: string | null }>('POST', pub(slug), { item, method }, customerHeaders(slug)),
  confirm: (slug: string, reference: string) => apiClient<{ payment: Payment }>('POST', `${pub(slug)}/confirm`, { reference }),
  cancel: (slug: string, id: number) => apiClient<{ cancelled: boolean }>('DELETE', `${pub(slug)}/${id}`, null, customerHeaders(slug)),
  today: (slug: string) => apiClient<Today>('GET', `${vendor(slug)}/today`),
  setEnabled: (slug: string, enabled: boolean) => apiClient<Today>('PUT', `${vendor(slug)}/settings`, { enabled }),
  cashReceived: (slug: string, id: number) => apiClient<{ payment: Payment }>('POST', `${vendor(slug)}/${id}/cash-received`),
  vendorCancel: (slug: string, id: number) => apiClient<{ cancelled: boolean }>('POST', `${vendor(slug)}/${id}/cancel`),
};
