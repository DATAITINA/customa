# Customa

**A friendly AI character for every small food stand.** Customers scan the stand's QR code, the
stand's character greets them by name, counts their plate, and every 6th plate earns a *jara*
(a free extra portion). The vendor watches visits, ratings and questions live on a dashboard.

Built in 5 hours at the KodeHauz Decennium Sprint, on **MSFLib**.

- Live app: https://customa-web.vercel.app (demo stand: `/s/iya-bisi-demo`, QR sign: `/qr/iya-bisi-demo`)
- API: https://customa-api.vercel.app/docs

> The demo stand, *Iya Bisi's Yam & Fish (Demo)*, is fictional. On it a plate counts every
> **30 seconds** so it can be shown on stage; real stands count one plate per **6 hours**.

## The problem

Vendors in Uyo told us their biggest daily problem is getting enough customers, so cooked food
sells out instead of staying overnight. They know regulars by face, not by name, and have no
till or app for loyalty. Customa gives each stand a mascot that remembers customers and rewards
coming back.

## How MSFLib carries the app

| Customa feature | MSFLib (backend) | MSFLib (frontend) | Our code |
|---|---|---|---|
| Vendor sign-up, sign-in, protected routes | `msflib-auth` (JWT login, `get_current_active_account`), `msflib-account` (accounts, open registration) | `@msflib/react-auth` (`AuthProvider`, `useAuth`) | POST `/logout` shim for react-auth |
| A stand per vendor | `msflib-workspaces` (`WorkspaceAction.create_with_owner`, membership), `msflib-tenancy` (default tenant), workspace membership checks from `msflib-auth` (`get_user_dependencies`, `PathParameterResolver`) | | `services/stands.py` |
| Count a plate, block repeats | core `ModelBase` tables + `ModelAction` (`VisitAction.count_plate` holds the one-plate-per-window rule) | `@msflib/core` `configuredApiClient` | `actions/customa.py` |
| 6-hour window, 30 s on the demo stand | core tiered settings (`ModuleSettingsBase` namespace `CUSTOMA`) + `msflib-workspace-config` (`ScopedConfigService`: per-stand override) | | `CustomaSettings` |
| Jara on the 6th plate | core event bus: listener on `visit-create-pre-commit` issues the reward **in the same transaction** | | `eventbus/__init__.py` |
| Redeem a jara once | core `ModelAction.update` | | `/stands/{slug}/jara/{code}/redeem` |
| Chat with the character | `msflib-ai-core` (`get_ai_dependencies().get_llm()`, `TokenUsageCallback` for tokens, logged with latency) | | persona + guardrails prompt, menu-based fallback (`services/bisi.py`) |
| Saved chats the vendor can read | `msflib-conversation` (`ChannelService`, `AccessService`, `MembershipService.add_agent`, `MessagingService`) | | `services/chat_log.py` |
| Character from the vendor's own words | `msflib-ai-core` model, output validated by a Pydantic schema, one retry, safe default | | `suggest_character` |
| Demo stand ready instantly | core models/actions in an idempotent seed (`app/seed/demo.py`) run by the template's `initial_data` | | |
| App shell | the official **MSFLib FastAPI template** (settings, session, keystore, auth/account routers, workspace hooks) | `@msflib/core` `configureApplication` | |

Installed but not yet in a user flow: `msflib-ai-api`, `msflib-drivelink` (planned: stand photo storage).

## Data and privacy

A customer is a random key kept on their own phone; a first name is stored only with consent.
**Delete my data** removes the customer's chats, ratings, jara and plates at that stand.
The vendor sees first names, plates, ratings and questions, never phone numbers.

## Run it locally

Backend (Python 3.11+, Poetry). MSFLib is a private repo: set up access as the organisers describe.

```bash
cd backend
cp .env-example .env          # set SECRET_KEY, USE_SQLITE=true, DEMO_VENDOR_PASSWORD, ...
poetry install
poetry run python -m app.initial_data   # tables + demo stand
poetry run uvicorn app.main:app --reload
```

Frontend (Node 20+, pnpm; `@msflib/*` come from GitHub Packages, `NPM_TOKEN` needed):

```bash
cd frontend
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env
pnpm install
pnpm dev
```

Optional AI: `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://ai-gateway.vercel.sh/v1`,
`LLM_MODEL=openai/gpt-4o-mini`, `LLM_API_KEY=...`. Without a key every AI feature
falls back to answers from the stand's menu.

## Deploy

Both apps run on Vercel (`backend/vercel.json`, `frontend/vercel.json`) with Neon Postgres.
`backend/scripts/setup_production.sh` copies settings into Vercel and seeds Neon.
Vercel cannot read the private MSFLib repo, so the deploy uploads MSFLib wheels built locally
from the exact pinned commits (`backend/vendor-wheels/`, not committed).

## Layout

```
backend/app/
  core/config.py        settings: MSFLib modules + CustomaSettings
  models/customa.py     Character, Customer, Visit, Rating, JaraReward
  actions/customa.py    ModelActions, the plate rule
  eventbus/             jara listener
  services/             stands (tiered settings), bisi (AI), chat_log (conversation)
  api/api_v1/endpoints/ public (customer), stands (vendor), session
  seed/demo.py          Iya Bisi demo stand
frontend/src/
  application.ts        configureApplication (MSFLib)
  api.ts                configuredApiClient calls
  components/Character.tsx  animated character kit
  pages/                Customer, Chat, Vendor (sign-in, setup, dashboard), QR
```
