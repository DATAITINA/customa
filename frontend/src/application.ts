// MSFLib setup. Imported first in main.tsx, before any MSFLib provider or API client.
import { configureApplication } from '@msflib/core';

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';
// Where MSFLib keeps the vendor's sign-in token (localStorage).
export const ACCESS_TOKEN_KEY = 'access_token';

configureApplication({
  baseURL: API_BASE,
  accessTokenKey: ACCESS_TOKEN_KEY,
});
