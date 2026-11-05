# Continuous integration

`.github/workflows/ci.yml` runs for pull requests targeting `main`, pushes to `main`, and manual dispatches. It uses GitHub-hosted Ubuntu x64 runners with `contents: read`, no secrets, and four independent jobs: `backend`, `frontend`, `infrastructure`, and `security`.

The backend job installs from `apps/api/uv.lock`, checks the lock, and runs Ruff lint/format verification, strict mypy, and offline pytest with coverage. The frontend job installs the root pnpm lockfile with `--frozen-lockfile` and runs ESLint, Prettier format verification, generated OpenAPI type verification, Next.js/TypeScript type checking, Vitest coverage, and the production build. The infrastructure job runs the isolated Qdrant Compose acceptance test against the runner's native Docker Engine. The Compose file selects the native image architecture, so Apple Silicon uses ARM64 locally while CI uses x64 without emulation.

The security job installs Gitleaks 8.30.1 with checksum verification and runs `make security-check` plus its negative smoke test. It uses no live Jev key. All third-party actions are pinned to full commit SHAs. uv and pnpm caches are keyed by their lockfiles; caches contain no credentials, environment files, virtual environments, or `node_modules`. Job timeouts are 15 minutes for application checks, 20 minutes for infrastructure, and 10 minutes for security. Pull request runs may be canceled when a newer commit arrives; main branch runs continue.

Repository branch protection is configured separately from this workflow. The `main` ruleset must require pull requests and the exact status checks `backend`, `frontend`, `infrastructure`, and `security`, require those checks to be up to date, and apply the rule to administrators. Force pushes and branch deletion should remain disabled. Verify the active ruleset after the `security` check has appeared in CI; see the [Foundation release report](../foundation/release-report.md).

