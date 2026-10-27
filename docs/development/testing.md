# Testing and quality checks

Run `make check` from the repository root before opening a pull request. It runs backend and frontend lint, formatting verification, type checks, offline tests with coverage, and the frontend production build. It does not start Docker or call the live Jev API.

## Backend

The API project uses the locked `apps/api/uv.lock` environment. Run `make setup-api` to install it, then `make lint-backend`, `make format-check-backend`, `make typecheck-backend`, or `make test-backend`. Run `make format` only when you intend to modify Python files. Pytest enforces an 80% package coverage floor with branch measurement and writes `apps/api/coverage.xml`.

Unit tests and offline integration tests use local fixtures and mocked transports. Tests marked `live` are excluded from `make test-backend`; `make jev-smoke` requires `JEV_LIVE_SMOKE=1` and a configured API key. Qdrant acceptance tests are separate: `make infra-test` requires Docker Compose and a local `.env` copied from `.env.example`.

## Frontend

The frontend is part of the root pnpm workspace. Use `corepack pnpm install --frozen-lockfile` to install dependencies. The targets `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`, and `make build-web` run ESLint, Next.js type generation plus TypeScript, Vitest V8 coverage, and the production build. React tests use jsdom; server API tests opt into Node. Coverage floors are 80% lines, statements, and functions, and 70% branches.

