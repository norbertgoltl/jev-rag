# Testing and quality checks

Run `make check` from the repository root before opening a pull request. It runs backend and frontend lint, formatting verification, type checks, offline tests with coverage, and the frontend production build. It does not start Docker or call the live Jev API. The Foundation handoff also requires `make security-setup`, `make security-check`, `make security-smoke`, and `make infra-test`.

## Backend

The API project uses the locked `apps/api/uv.lock` environment. Run `make setup-api` to install it, then `make lint-backend`, `make format-check-backend`, `make typecheck-backend`, or `make test-backend`. Run `make format` only when you intend to modify Python files. Pytest enforces an 80% package coverage floor with branch measurement and writes `apps/api/coverage.xml`.

Unit tests and offline integration tests use local fixtures and mocked transports. Tests marked `live` are excluded from `make test-backend`; `make jev-smoke` requires `JEV_LIVE_SMOKE=1` and a configured API key. Qdrant acceptance tests are separate: `make infra-test` requires Docker Compose and a local `.env` copied from `.env.example`.

## Frontend

The frontend is part of the root pnpm workspace. Use `corepack pnpm install --frozen-lockfile` to install dependencies. The targets `make lint-frontend`, `make format-check-frontend`, `make typecheck-frontend`, `make test-frontend`, and `make build-web` run ESLint, Prettier verification, Next.js type generation plus TypeScript, Vitest V8 coverage, and the production build. Run `make format-frontend` only when you intend to modify frontend files. `apps/web/tests/openapi-contract.test.ts` checks the BFF's contract guards against the examples and paths in `docs/architecture/contracts/foundation.openapi.json`, so contract drift fails the tests. React tests use jsdom; server API tests opt into Node. Coverage floors are 80% lines, statements, and functions, and 70% branches.

## Security

`make security-setup` installs the checksum-pinned Gitleaks 8.30.1 binary under ignored `.tools/`. `make security-check` scans history and first-party working-tree paths and validates frontend and Qdrant boundaries. `make security-smoke` creates a temporary isolated repository and verifies that synthetic tracked secrets, frontend credential references, scanner findings, and wildcard Qdrant bindings fail. It removes the fixture when complete.

## Foundation release gate

Use [`../foundation/release-checklist.md`](../foundation/release-checklist.md) and record only commands that were actually run in [`../foundation/release-report.md`](../foundation/release-report.md). A clean setup must use a separate clone. Never use volume deletion to make an infrastructure test pass.

