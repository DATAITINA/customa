#!/usr/bin/env bash
# Create the tables in Neon and seed the demo stand (safe to run again).
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -s -p "Paste the Neon connection string (postgresql://...), then Enter: " NEON; echo
[[ "$NEON" == postgresql://* ]] || { echo "That does not look like a Postgres URL."; exit 1; }
USE_SQLITE=false SQLALCHEMY_DATABASE_URI="$NEON" .venv/Scripts/python.exe -m app.initial_data 2>&1 | grep -v "^INFO:sqlalchemy" | tail -3
