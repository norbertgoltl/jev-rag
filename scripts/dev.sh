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
  test        Run offline backend and frontend tests with coverage
  check       Run lint, format check, types, tests and frontend build
  jev-smoke   Run explicitly authorized paid TypeSafe smoke test

  health      Check Qdrant HTTP readiness
  infra-test  Run isolated infrastructure acceptance tests
  up          Start Qdrant and wait for health
  down        Stop project infrastructure, preserving volumes
  status      Show project container health
  logs        Follow Qdrant logs (Ctrl-C stops following)

Quality commands:
  setup       Install locked API and web dependencies (FND-008, FND-012)
  lint-backend, format-check-backend, typecheck-backend, test-backend
  lint-frontend, format-check-frontend, typecheck-frontend, test-frontend, build-web
  format      Explicitly format backend sources
  format-frontend  Explicitly format frontend sources

No command sources .env as shell code.
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
        exec uv run --project "$REPO_ROOT/apps/api" --managed-python --locked pytest "$REPO_ROOT/apps/api/tests" -m 'not live'
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
    lint|lint-backend|lint-frontend|format|format-frontend|format-check|format-check-backend|format-check-frontend|typecheck|typecheck-backend|typecheck-frontend|test|test-backend|test-frontend|build-web|check)
        case "$1" in
            lint-backend|format-check-backend|format|typecheck-backend|test-backend)
                require_command uv 'Install uv first.'
                ;;
            lint-frontend|format-frontend|format-check-frontend|typecheck-frontend|test-frontend|build-web)
                require_command pnpm 'Activate the pinned pnpm version first.'
                ;;
            *)
                require_command uv 'Install uv first.'
                require_command pnpm 'Activate the pinned pnpm version first.'
                ;;
        esac
        cd "$REPO_ROOT"
        case "$1" in
            lint-backend|format-check-backend|format|typecheck-backend|test-backend)
                require_file apps/api/pyproject.toml FND-008
                require_file apps/api/uv.lock FND-008
                ;;
            lint-frontend|format-frontend|format-check-frontend|typecheck-frontend|test-frontend|build-web)
                require_file apps/web/package.json FND-012
                require_file pnpm-lock.yaml FND-012
                ;;
        esac
        case "$1" in
            lint-backend) exec uv run --project apps/api --managed-python --locked ruff check . ;;
            format-check-backend) exec uv run --project apps/api --managed-python --locked ruff format --check . ;;
            format) exec uv run --project apps/api --managed-python --locked ruff format . ;;
            typecheck-backend) exec uv run --project apps/api --managed-python --locked mypy --config-file apps/api/pyproject.toml apps/api/src/jev_rag_api apps/api/tests ;;
            test-backend) exec uv run --project apps/api --managed-python --locked pytest apps/api/tests -m 'not live' ;;
            lint-frontend) exec pnpm --filter @jev-rag/web lint --max-warnings 0 ;;
            format-frontend) exec pnpm --filter @jev-rag/web format ;;
            format-check-frontend) exec pnpm --filter @jev-rag/web format:check ;;
            typecheck-frontend) exec pnpm --filter @jev-rag/web typecheck ;;
            test-frontend) exec pnpm --filter @jev-rag/web test:coverage ;;
            build-web) exec pnpm --filter @jev-rag/web build ;;
            lint) "$0" lint-backend; exec "$0" lint-frontend ;;
            format-check) "$0" format-check-backend; exec "$0" format-check-frontend ;;
            typecheck) "$0" typecheck-backend; exec "$0" typecheck-frontend ;;
            test) "$0" test-backend; exec "$0" test-frontend ;;
            check)
                "$0" lint-backend
                "$0" lint-frontend
                "$0" format-check-backend
                "$0" format-check-frontend
                "$0" typecheck-backend
                "$0" typecheck-frontend
                "$0" test-backend
                "$0" test-frontend
                exec "$0" build-web
                ;;
        esac
        ;;
    *)
        fail "Unknown command: $1. Run make help."
        ;;
esac
