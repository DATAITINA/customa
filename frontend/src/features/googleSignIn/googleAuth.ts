// Vendor sign-in with Google, through MSFLib auth on the server:
//   GET  /google/login?redirect_uri=…  → the Google sign-in page (403 while it is switched off)
//   POST /google/callback {code, redirect_uri} → the same sign-in token as /login
// Google sends the vendor back to /vendor/google with a one-time code.
import { storage } from '@msflib/core';
import { ACCESS_TOKEN_KEY, API_BASE } from '../../application';

export const googleRedirectUri = () => `${window.location.origin}/vendor/google`;
const loginUrl = () => `${API_BASE}/google/login?redirect_uri=${encodeURIComponent(googleRedirectUri())}`;

// Only ever send the vendor to Google's own sign-in pages.
function isGoogle(url: unknown): url is string {
  if (typeof url !== 'string') return false;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && (u.hostname === 'accounts.google.com' || u.hostname.endsWith('.google.com'));
  } catch {
    return false;
  }
}

function googleUrlIn(data: unknown): string | null {
  if (isGoogle(data)) return data;
  if (data && typeof data === 'object') {
    for (const value of Object.values(data as Record<string, unknown>)) {
      if (isGoogle(value)) return value;
      const inner = value && typeof value === 'object' ? googleUrlIn(value) : null;
      if (inner) return inner;
    }
  }
  return null;
}

/** Where "Continue with Google" goes, or null when Google sign-in is off on the server. */
export async function googleSignInUrl(): Promise<string | null> {
  try {
    const r = await fetch(loginUrl(), { redirect: 'manual' });
    // The server redirects straight to Google: the browser follows the same address.
    if (r.type === 'opaqueredirect' || (r.status >= 300 && r.status < 400)) return loginUrl();
    if (!r.ok) return null;
    return googleUrlIn(await r.json().catch(() => null));
  } catch {
    return null;
  }
}

/** Swap Google's one-time code for the vendor's sign-in token. */
export async function finishGoogleSignIn(code: string): Promise<void> {
  const r = await fetch(`${API_BASE}/google/callback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, redirect_uri: googleRedirectUri() }),
  });
  const data = (await r.json().catch(() => null)) as { access_token?: string; detail?: unknown } | null;
  if (!r.ok || !data?.access_token) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'Google sign-in did not work. Try again.');
  }
  storage.setItem(ACCESS_TOKEN_KEY, data.access_token);
}
