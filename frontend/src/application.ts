// MSFLib setup. Imported first in main.tsx, before any MSFLib provider or API client.
import { configureApplication } from '@msflib/core';

configureApplication({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  accessTokenKey: 'access_token',
});
