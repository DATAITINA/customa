# Customa

**A friendly AI character for every small food stand.** Customers scan the stand's QR code, the
stand's character greets them by name, counts their plate, and every 6th plate earns a *jara*
(a free extra portion). The vendor watches visits, ratings and questions live on a dashboard.

Built in 5 hours at the KodeHauz Decennium Sprint, on **MSFLib**.

- Live app: https://customa-web.vercel.app (a stand's page: `/s/{slug}`, its QR sign: `/qr/{slug}`)
- API: https://customa-api.vercel.app/docs

## Return-visit features (Oct 2026)

Two features a vendor can turn on from the dashboard; each is off by default. Details and
acceptance criteria: [docs/return-visit-features.md](docs/return-visit-features.md).

- **Plate Ajo**: customers prepay 5 or 10 plates at today's price by transfer to the vendor's
  own account; Customa only keeps the count.
- **Lunch Crew**: friends share one card; every 6th crew plate earns a jara for the next member in
  turn, like an ajo payout.

The character chat is private (vendors only see food questions), short and warm (one chat per
plate, closed with a cliffhanger and picked up next plate), and remembers a few things the
customer can see and clear. Vendors can also set today's special and turn on surprise jara.
Details: [docs/character-chat-and-delights.md](docs/character-chat-and-delights.md).

A plate counts only after a real scan of the stand's QR code (it carries a secret scan code),
and customers can turn on leftover-food alerts: a text message (any phone) or a push notification
in the character's voice when the vendor taps "Tell my customers". Details:
[docs/scan-and-alerts.md](docs/scan-and-alerts.md). Vendors can sign in with Google:
[docs/google-sign-in.md](docs/google-sign-in.md).

The **Prize Wheel**: vendors put up to 6 of their foods on a wheel, and every jara becomes a
spin. The server picks the prize, the customer gets a one-time code, and the vendor checks it.
Details: [docs/prize-wheel.md](docs/prize-wheel.md).

**Return-visit boosters**: every new card starts with 2 gift stamps ("Welcome gift: 2 stamps on
us 🎁", display only); "Who's here now" shows staff which regulars just arrived, so they greet them
by name ("Ime! Welcome back o!"); and after each plate the character asks "When you go come back?"
for a day and a time, with a calendar file and a reminder. The dashboard shows the % of customers
who came back within 14 days. Details: [docs/return-visit-boosters.md](docs/return-visit-boosters.md).

Vendors pick a character (now with a **panda**, chick, bunny and cat), add a photo of their
stand, and customers can install the stand on their Home Screen, play quick games with the
character and delete their data from a clear sheet. Details:
[docs/stand-look-and-install.md](docs/stand-look-and-install.md).

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
| 6-hour window (a per-stand setting) | core tiered settings (`ModuleSettingsBase` namespace `CUSTOMA`) + `msflib-workspace-config` (`ScopedConfigService`: per-stand override) | | `CustomaSettings` |
| Jara on the 6th plate | core event bus: listener on `visit-create-pre-commit` issues the reward **in the same transaction** | | `eventbus/__init__.py` |
| Redeem a jara once | core `ModelAction.update` | | `/stands/{slug}/jara/{code}/redeem` |
| Chat with the character | `msflib-ai-core` (`get_ai_dependencies().get_llm()`, `TokenUsageCallback` for tokens, logged with latency) | | persona + guardrails prompt, menu-based fallback (`services/bisi.py`) |
| Food questions the vendor can read (chats stay private) | `msflib-conversation` (`ChannelService`, `AccessService`, `MembershipService.add_agent`, `MessagingService`) | | `services/chat_log.py` |
| Character from the vendor's own words | `msflib-ai-core` model, output validated by a Pydantic schema, one retry, safe default | | `suggest_character` |
| Pay for a plate (Paystack test mode, or cash the vendor confirms); a paid plate is a stamp | core `ModelBase` table `Payment` + `ModelAction` (`PaymentAction`); `msflib-workspace-config` per-stand `PAYMENTS_ENABLED`; app settings for the Paystack test key (never committed) | `@msflib/core` `configuredApiClient` | `services/paystack.py` (client), `services/payments.py` (rules), `endpoints/payments.py` (routes + signed webhook), `features/payments/`; see `docs/payments.md` |
| App shell | the official **MSFLib FastAPI template** (settings, session, keystore, auth/account routers, workspace hooks) | `@msflib/core` `configureApplication` | |

MSFLib has no payments module, so payments are built from MSFLib's own pieces above. Installed but not yet in a user flow: `msflib-ai-api` (planned: streamed chat replies) and `msflib-drivelink` (planned: stand photos; it needs cloud file storage such as Cloudinary or S3, because Vercel can't keep files; photos are stored in the database until then).

## Data and privacy

A customer is a random key kept on their own phone; a first name is stored only with consent.
**Delete my data** removes the customer's chats, ratings, jara and plates at that stand.
The vendor sees first names, plates, ratings and questions, never phone numbers.

## Run it locally

Backend (Python 3.11+, Poetry). MSFLib is a private repo: set up access as the organisers describe.

```bash
cd backend
cp .env-example .env          # set SECRET_KEY, USE_SQLITE=true, ...
poetry install
poetry run python -m app.initial_data   # tables
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
frontend/src/
  application.ts        configureApplication (MSFLib)
  api.ts                configuredApiClient calls
  components/Character.tsx  animated character kit
  pages/                Customer, Chat, Vendor (sign-in, setup, dashboard), QR
```
