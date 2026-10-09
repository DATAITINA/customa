#!/bin/bash
# Use this script to install dependencies in a container environment, where poetry's parallel installation of
# dependencies interacts badly with the msflib github-based dependencies.

set -e

backup_pyproject="$(mktemp)"
cp pyproject.toml "${backup_pyproject}"
trap 'cp "${backup_pyproject}" pyproject.toml; rm -f "${backup_pyproject}"' EXIT

if [ -n "${CONTAINER_GITHUB_PAT}" ]; then
    git config --global url."https://x-access-token:${CONTAINER_GITHUB_PAT}@github.com/".insteadOf "https://github.com/";
fi
CONTAINER_GITHUB_PAT=${CONTAINER_GITHUB_PAT} python scripts/toml_deps.py pyproject.toml ./tmp/exports
python -m venv .venv
poetry lock
poetry install --no-dev --no-interaction --no-ansi
