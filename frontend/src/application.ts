// MSFLib setup. Imported first in main.tsx, before any MSFLib provider or API client.
import { configureApplication } from '@msflib/core';

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

configureApplication({
  baseURL: API_BASE,
  accessTokenKey: 'access_token',
});
