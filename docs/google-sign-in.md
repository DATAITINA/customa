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

## Setup (free)
1. **Google Cloud Console** (console.cloud.google.com), with a new project called "Customa":
   - **APIs & Services → OAuth consent screen**: choose External, app name Customa, your email,
     scopes `email`, `profile` and `openid`. Publish the app (In production) so any Google
     account can sign in.
   - **APIs & Services → Credentials → Create credentials → OAuth client ID → Web application**.
     Authorized redirect URI: `https://customa-web.vercel.app/vendor/google` (add
     `http://localhost:5173/vendor/google` for local work). Copy the **Client ID** and
     **Client secret**.
2. **Vercel → customa-api → Settings → Environment Variables** (the names MSFLib auth reads):
   - `ENABLE_GOOGLE_OAUTH` = `true`
   - `ALLOW_GOOGLE_OAUTH_SIGNUP` = `true` (new vendors can sign up with Google)
   - `GOOGLE_OAUTH_CLIENT_ID` = the Client ID
   - `GOOGLE_OAUTH_CLIENT_SECRET` = the Client secret
   - `GOOGLE_REDIRECT_URI` = `https://customa-web.vercel.app/vendor/google`

   Then redeploy the backend. The button appears by itself once `/google/login` stops answering
   403.

## Backend pieces
- `SessionMiddleware` (`app/main.py`): MSFLib auth's Google login step keeps its sign-in state in
  a signed session cookie, as in MSFLib's own auth tests.
- The `google-account-create` listener (`app/eventbus/__init__.py`): MSFLib auth emits it for an
  email it doesn't know yet. It creates the vendor account (with a random password nobody knows),
  and the vendor then sets up their stand like after email sign-up. An existing vendor with the
  same email simply signs in.
- Test: `backend/app/tests/api/api_v1/test_google_sign_in.py`.
