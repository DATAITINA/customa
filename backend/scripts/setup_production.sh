#!/usr/bin/env bash
# One-time production setup, run by a person (it handles secrets):
#   1. copies the backend settings into the Vercel project "customa-api"
#   2. creates the tables in Neon and seeds the demo stand
# Secrets are read from local files or typed in hidden; nothing is printed or committed.
set -euo pipefail
cd "$(dirname "$0")/.."

getv() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | tr -d '\r'; }

read -r -s -p "Paste the Neon connection string (postgresql://...), then Enter: " NEON; echo
[[ "$NEON" == postgresql://* ]] || { echo "That does not look like a Postgres URL."; exit 1; }
MSFLIB_TOKEN=$(grep -o '_authToken=[^[:space:]]*' "$HOME/.npmrc" | head -1 | cut -d= -f2 | tr -d '\r')
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")

add() {
  if [ -z "$2" ]; then echo "skipped $1 (empty)"; return; fi
  printf '%s' "$2" | vercel env add "$1" production --force >/dev/null 2>&1 && echo "set $1" || echo "FAILED $1"
}

echo "== Vercel settings for customa-api"
add MSFLIB_TOKEN "$MSFLIB_TOKEN"
add SQLALCHEMY_DATABASE_URI "$NEON"
add USE_SQLITE false
add SECRET_KEY "$SECRET_KEY"
add ENVIRONMENT production
add PROJECT_NAME "Customa API"
add FIRST_SUPERUSER "$(getv FIRST_SUPERUSER)"
add FIRST_SUPERUSER_PASSWORD "$(getv FIRST_SUPERUSER_PASSWORD)"
add USERS_OPEN_REGISTRATION true
add EMAILS_ENABLED false
add STORAGE_PATH /tmp/uploads
add LLM_PROVIDER openai
add LLM_BASE_URL "$(getv LLM_BASE_URL)"
add LLM_MODEL "$(getv LLM_MODEL)"
add LLM_API_KEY "$(getv LLM_API_KEY)"
add BACKEND_CORS_ORIGINS '["https://customa-web.vercel.app","http://localhost:5173"]'

echo "== Creating tables in Neon and seeding the demo stand"
USE_SQLITE=false SQLALCHEMY_DATABASE_URI="$NEON" .venv/Scripts/python.exe -m app.initial_data 2>&1 | grep -v "^INFO:sqlalchemy" | tail -3
echo "== Done"
