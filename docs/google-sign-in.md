# Vendor sign-in with Google

The vendor sign-in page shows **Continue with Google** under the email form. It uses the Google
sign-in that MSFLib auth already has on the backend:

1. The page asks `GET /api/v1/google/login?redirect_uri=https://<web>/vendor/google`. While Google
   sign-in is switched off the server answers 403 and the button is not shown, so it never fails.
2. The vendor signs in at Google (only Google's own `*.google.com` pages are followed).
3. Google sends them back to `/vendor/google?code=…`. The page posts
   `POST /api/v1/google/callback {code, redirect_uri}` and gets the same sign-in token as `/login`,
   saves it where MSFLib keeps it (`localStorage.access_token`) and opens `/vendor`. A vendor with
   no stand yet goes straight to stand setup.
4. Cancelled at Google, or a failed sign-in: a clear message and "Back to sign in".

Code: `frontend/src/features/googleSignIn/` (button, return page, requests).

## Setup
1. Google Cloud Console → APIs & Services → Credentials → Create credentials → OAuth client ID
   → Web application. Authorized redirect URI: `https://customa-web.vercel.app/vendor/google`
   (add `http://localhost:5173/vendor/google` for local work). Set up the OAuth consent screen
   (app name Customa, scopes email, profile, openid) and publish it.
2. Put the client ID and client secret in the backend environment (Vercel, customa-api) under the
   names MSFLib auth reads for Google sign-in (see the MSFLib auth docs; this repo's
   `.env-example` has the related `SSO_SECRET_KEY` and `SSO_REDIRECT_URL`), turn Google sign-in on,
   and redeploy the backend. The button appears by itself once `/google/login` stops answering 403.
