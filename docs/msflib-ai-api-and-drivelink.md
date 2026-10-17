# Ask about your stand (msflib-ai-api) and stand photos in drivelink (msflib-drivelink)

## Ask about your stand
A card on the vendor dashboard. The vendor taps a question ("How did this week go?", "When am I
busiest?", "Who are my regulars?", "Which food sells best for me?") or types one, and gets a
short answer in plain words with one practical tip.

How it works:
- `msflib.ai_api.router.create_agent_router` is mounted at `/api/v1/stands/{slug}/assistant`
  (`POST /ask`, `POST /ask/stream`, `GET /status`). An outer router first requires a signed-in
  member of that stand: ai-api's own scope dependency would accept anonymous callers.
- The agent is built by ai-api from Customa's tools (an ai-core `StaticToolRegistry`), Customa's
  system prompt, and the same ai-core LLM as the character chat (`AI_CORE` settings).
- Each tool reads the stand from ai-api's `ScopeEnvelope` (`workspace_id`), passed per call
  through the LangGraph runtime context. The model can't choose another stand.
- Tools (read-only): stand summary (plates, new and returning customers, jara, ratings,
  payments, best-selling paid items, best day), busiest times, top regulars, menu and prices.
- Privacy: first names only where the customer gave one; never phone numbers, chats or keys.
- The answer is requested with `?protocol=langchain` (`{"type": "ai", "content": "..."}`).
- No setup beyond the chat's existing `AI_CORE` / OpenAI settings. No migration.

## Stand photos in the vendor's drivelink drive
With `STAND_PHOTOS_IN_DRIVELINK=true`, a stand photo goes through `DrivelinkService.create_file`
(drivelink's upload checks, storage and quota) into the vendor's drive, folder
"Stand photos · <stand>". Replacing a photo hard-deletes the old file from the drive and its
storage, and removing deletes it. `StandPhotoFile` links the stand to its drive file. The public
photo URL redirects to the cloud copy, or streams it for local file storage.

Vercel can't keep files, so this needs cloud storage. Cloudinary's free plan is enough. Set on
Vercel (customa-api):
- `STAND_PHOTOS_IN_DRIVELINK=true`
- `STORAGE_METHOD=cloudinary`
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (from the Cloudinary
  dashboard)

S3, GCS or Azure work too: MSFLib core storage settings. Without these settings, photos stay in
the database as before, so nothing breaks. Never commit keys.

Migration (run on Neon before deploying the backend):
`backend/scripts/migrations/2026-10-20_drivelink_stand_photos.sql`. It creates MSFLib's
`drivelinknode` table, generated from the real model, and `standphotofile`; it is safe to run
twice.

## Tests
`backend/app/tests/api/api_v1/test_msflib_depth.py` runs against the real MSFLib packages and
real login:
- the agent calls the stand tool, scoped to the stand;
- the system prompt reaches the model;
- anonymous callers get 401, and a vendor of another stand gets 403;
- tools hide names given without consent;
- photos are stored, replaced (one file left) and deleted in drivelink;
- the database fallback still works.
