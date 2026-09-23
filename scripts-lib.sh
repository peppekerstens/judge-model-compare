#!/usr/bin/env bash
# Shared loader for every shell script in this repository.
# It reads .env from the repository root, and then ~/.env for the secrets.
# Copy .env.example to .env first. Usage inside a script:
#
#   . "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)/scripts-lib.sh"
#   need LEGION_SSH POC_SSH
#
load_env() {
  local root
  root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  if [ -f "$root/.env" ]; then
    set -a; . "$root/.env"; set +a
  else
    echo "no .env in $root. Copy .env.example to .env and fill it in." >&2
    return 1
  fi
  # The keys live in ~/.env, the one plain-text copy, with gopass as the source.
  if [ -f "$HOME/.env" ]; then
    set -a; . "$HOME/.env"; set +a
  fi
}

need() {
  local missing=0 name
  for name in "$@"; do
    if [ -z "${!name:-}" ]; then
      echo "$name is missing. Add it to .env (see .env.example)." >&2
      missing=1
    fi
  done
  [ "$missing" = 0 ]
}

load_env
