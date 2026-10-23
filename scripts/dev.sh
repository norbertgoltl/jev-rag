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
  setup-api   Install locked backend dependencies
  dev-api     Start the host FastAPI development server
  dev-web     Start the host Next.js development server
  test-api    Run offline backend tests
  test        Run offline backend and frontend tests
  jev-smoke   Run explicitly authorized paid TypeSafe smoke test

  health      Check Qdrant HTTP readiness
  infra-test  Run isolated infrastructure acceptance tests
  up          Start Qdrant and wait for health
  down        Stop project infrastructure, preserving volumes
  status      Show project container health
  logs        Follow Qdrant logs (Ctrl-C stops following)

Requires later Foundation tasks:
  setup       Install locked API and web dependencies (FND-008, FND-012)
  lint        Check backend and frontend lint (FND-021, FND-022)
  format      Format backend and frontend sources (FND-021, FND-022)
  typecheck   Check Python and TypeScript types (FND-021, FND-022)
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
    up|down|status|logs|health|infra-test)
        require_command uv 'Install uv first.'
        cd "$REPO_ROOT"
        exec uv run --project apps/api --managed-python --locked python scripts/infrastructure.py "$1"
        ;;
    dev-api)
        require_file apps/api/pyproject.toml FND-008
        require_file apps/api/uv.lock FND-008
        require_command uv 'Install uv using its official installation guide.'
        cd "$REPO_ROOT"
        exec uv run --project "$REPO_ROOT/apps/api" --managed-python --locked jev-rag-api
        ;;
    setup-api|test-api)
        require_file apps/api/pyproject.toml FND-008
        require_file apps/api/uv.lock FND-008
        require_command uv 'Install uv using its official installation guide.'
        cd "$REPO_ROOT"
        if [ "$1" = setup-api ]; then
            exec uv sync --project "$REPO_ROOT/apps/api" --managed-python --locked
        fi
        exec uv run --project "$REPO_ROOT/apps/api" --managed-python --locked pytest "$REPO_ROOT/apps/api/tests"
        ;;
    dev-web)
        require_command pnpm 'Activate the pinned pnpm version with Corepack.'
        load_versions
        check_node_pnpm
        cd "$REPO_ROOT"
        exec pnpm --filter @jev-rag/web dev
        ;;
    jev-smoke)
        [ "${JEV_LIVE_SMOKE:-}" = 1 ] || fail 'Set JEV_LIVE_SMOKE=1 to acknowledge the paid TypeSafe request.'
        require_command uv 'Install uv first.'
        cd "$REPO_ROOT"
        exec uv run --project apps/api --managed-python --locked pytest "$REPO_ROOT/apps/api/tests/live/test_jev_smoke.py" --jev-live
        ;;
    test)
        require_command uv 'Install uv first.'
        require_command pnpm 'Activate the pinned pnpm version first.'
        cd "$REPO_ROOT"
        uv run --project apps/api --managed-python --locked pytest "$REPO_ROOT/apps/api/tests"
        exec pnpm --filter @jev-rag/web test
        ;;
    lint|format|typecheck|check)
        fail 'Application quality commands are not implemented. Complete FND-021–022 first. Use make smoke for developer CLI checks.'
        ;;
    *)
        fail "Unknown command: $1. Run make help."
        ;;
esac
