#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
. "$REPO_ROOT/scripts/lib/common.sh"

case "${1:-help}" in
    help)
        cat <<'HELP'
Usage: make <target> (from the repository root)

Available now:
  help        Show the developer command interface
  doctor      Check local tools and version pins without installing anything
  smoke       Run offline developer CLI smoke checks

Requires later Foundation tasks:
  setup       Install locked API and web dependencies (FND-008, FND-012)
  up          Start Docker infrastructure (FND-015)
  down        Stop infrastructure, preserving volumes (FND-015)
  status      Show infrastructure status (FND-015)
  logs        Show infrastructure logs (FND-015)
  dev-api     Start the host FastAPI development server (FND-009)
  dev-web     Start the host Next.js development server (FND-012)
  lint        Check backend and frontend lint (FND-021, FND-022)
  format      Format backend and frontend sources (FND-021, FND-022)
  typecheck   Check Python and TypeScript types (FND-021, FND-022)
  test        Run offline application tests (FND-021, FND-022)
  check       Run all checks, including format-check and web build (FND-021, FND-022)

Unavailable subsystems fail explicitly. No command sources .env as shell code.
HELP
        ;;
    setup)
        # Validate both workspaces before installing either dependency set.
        require_file apps/api/pyproject.toml FND-008
        require_file apps/api/.python-version FND-008
        require_file apps/api/uv.lock FND-008
        require_file apps/web/package.json FND-012
        require_file pnpm-lock.yaml FND-012
        load_versions
        require_command uv 'Install uv using its official installation guide.'
        check_node_pnpm
        cd "$REPO_ROOT"
        uv sync --project "$REPO_ROOT/apps/api" --managed-python --locked
        pnpm install --frozen-lockfile
        ;;
    up|down|status|logs)
        fail 'Infrastructure commands are not implemented. Complete FND-015–017 first. No containers or volumes were changed.'
        ;;
    dev-api)
        fail 'The FastAPI application is not implemented. Complete FND-008–011 first.'
        ;;
    dev-web)
        fail 'The Next.js application is not implemented. Complete FND-012–014 first.'
        ;;
    lint|format|typecheck|test|check)
        fail 'Application quality commands are not implemented. Complete FND-021–022 first. Use make smoke for developer CLI checks.'
        ;;
    *)
        fail "Unknown command: $1. Run make help."
        ;;
esac
