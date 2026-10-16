// Save your card / "Already have a card?": the card follows the customer to any browser.
import { apiClient, customerHeaders, type CustomerState } from '../../api';

export type CardState = { enabled: boolean; linked: boolean; masked: string | null; sms: boolean };

const path = (slug: string) => `/public/${slug}/card`;

export const cardApi = {
  state: (slug: string) => apiClient<CardState>('GET', path(slug), null, customerHeaders(slug)),
  link: (slug: string, phone: string, pin: string) =>
    apiClient<CardState>('PUT', `${path(slug)}/phone`, { phone, pin }, customerHeaders(slug)),
  unlink: (slug: string) => apiClient<CardState>('DELETE', `${path(slug)}/phone`, null, customerHeaders(slug)),
  sendCode: (slug: string, phone: string) =>
    apiClient<{ sent: boolean; message: string }>('POST', `${path(slug)}/recover/code`, { phone }),
  recover: (slug: string, phone: string, proof: { pin?: string; code?: string }) =>
    apiClient<{ key: string; customer: CustomerState }>('POST', `${path(slug)}/recover`, { phone, ...proof }, customerHeaders(slug)),
};

// Digits only, at most n: for the PIN and code boxes.
export const digits = (value: string, n: number) => value.replace(/\D/g, '').slice(0, n);
