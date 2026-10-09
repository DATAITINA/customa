import './application'; // must be first: configures MSFLib
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@msflib/react-auth';
import { App } from './App';
import './styles.css';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1 } } });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Vendor sign-in. Accounts are not per stand, so auth is not workspace-scoped. */}
      <AuthProvider options={{ isWorkspaceScoped: false }}>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
