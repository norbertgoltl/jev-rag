# Development environment and workflow

## Supported environment

The primary environment is macOS Apple Silicon. Commands use POSIX shell and GNU/BSD Make syntax and can also be used on Linux/WSL. Actual execution has currently been verified on macOS with GNU Make 3.81. BSD make version detection is covered by a simulated smoke test. Actual BSD make execution has not yet been performed.

| Tool | Requirement | Version source |
| --- | --- | --- |
| Git | Available CLI | `doctor` prints the version |
| Make | GNU Make or BSD make | `doctor` prints the version |
| uv | Python project manager | `doctor` prints the version |
| Python | uv-managed `3.14.8`, installed and verified | `apps/api/.python-version` from FND-008 |
| Node.js | `24.22.1`, from the designated 24 LTS branch | Root `.node-version` and `package.json` |
| pnpm | `12.15.0` | Root `package.json` `packageManager` |
| Corepack | Bootstrap option, optional when a suitable pnpm is already available | `doctor` reports it when available |
| Docker + Compose | Available CLI and Compose plugin | `doctor` prints the version |

Node.js and pnpm pins record the currently installed and verified versions. Updates must change and revalidate the related version sources together.

Select Node.js with a user-level version manager based on `.node-version`. Provide pnpm according to the `packageManager` pin. Available Corepack can be used for bootstrapping, but `doctor` does not activate shims, download a package manager, or install global packages. It fails if the pinned pnpm is not available locally.

Official references: [Node.js releases](https://nodejs.org/en/about/previous-releases), [pnpm installation](https://pnpm.io/installation), [pnpm workspace](https://pnpm.io/workspaces), [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

## Project roots and lockfiles

| Path | Responsibility |
| --- | --- |
| `apps/api/` | Single Python project with its own `pyproject.toml`, `uv.lock`, and `.venv`, from FND-008 |
| `apps/web/` | Next.js with its own `package.json`, from FND-012 |
| `package.json` | Private workspace coordinator, runtime and package manager pins, no application dependencies |
| `pnpm-workspace.yaml` | Only `apps/web`, with a shared root lockfile |
| `infra/compose.yaml` | Docker infrastructure, from FND-015–017 |
| `docs/foundation/` | Foundation acceptance checklist and actual release validation |
| `scripts/` | Developer CLI and offline smoke tests |
| `docs/architecture/`, `docs/adr/`, `docs/foundation/` | Architecture, decisions, phase boundaries |
| `docs/development/` | Setup and development workflow |
| `.github/` | PR template and GitHub Actions CI |

There is no root Python project, uv workspace, separate frontend lockfile, or pre-created shared/agent/embedding package. Application roots are currently maintained by their own READMEs, without empty `.gitkeep` files.

`apps/api/uv.lock` was created during FND-008, and the root `pnpm-lock.yaml` during FND-012. Both lockfiles and the runtime pins are version-controlled. Setup must not generate missing lockfiles or resolve new versions.

## Currently runnable commands

Run from the repository root:

```sh
make help
make doctor
make smoke
```

`help` shows the complete stable command interface. `doctor` collects diagnostics and exits with a non-zero code if a tool is missing or differs from the required version. It also checks Docker context and Engine availability, native architecture, Compose configuration, minimum CPU and memory resources, and host port ownership. It requires the root `.env` and an installed backend environment, but does not check application or Qdrant HTTP readiness or change configuration. Python discovery is offline and limited to already installed uv-managed interpreters.

Automatic pnpm package manager resolution is disabled by `pmOnFail: ignore`. The CLI checks version matching separately. For version queries, diagnostics also disable Corepack's project-based switching and network access. This prevents the check from generating a pnpm boot lockfile or downloading a missing version. The behavior is described in the [pnpm CLI settings](https://pnpm.io/settings/cli#pmonfail).

`smoke` runs without external APIs, a Docker daemon, or installed application dependencies, using a temporary copy and simulated tools. It checks successful and failed diagnostics, errors from unimplemented targets, setup delegation and error propagation, paths containing spaces, and that `.env` content is not executed. It removes temporary files and does not initialize the real workspaces.

From another directory, use `make -C /absolute/path/to/jev-rag help`. Shell entrypoints also resolve the repository root relative to their own file locations.

## Application and infrastructure commands

| Command | Behavior |
| --- | --- |
| `make setup` | First checks both workspace manifests, the API Python pin, and both lockfiles. Then runs `uv sync --project apps/api --managed-python --locked`, followed by root `pnpm install --frozen-lockfile`. The frontend manifest and root lockfile are complete. |
| `make up` | Starts Qdrant, waiting up to 90 seconds for health. |
| `make down` | Stops the project while preserving the volume and host apps. |
| `make status`, `make logs` | Project Qdrant status and log following. |
| `make dev-api` | Starts host-based FastAPI in the uv environment, on a loopback address by default. |
| `make dev-web` | Calls the @jev-rag/web dev command at 127.0.0.1:3000. |
| `make lint`, `make typecheck` | Backend and frontend quality checks, see the [testing guide](testing.md). |
| `make format`, `make format-frontend` | Explicitly format backend or frontend sources, respectively. |
| `make check` | Lint, format-check, typecheck, offline tests with coverage, and frontend production build. |

Every missing subsystem produces a clear error and a non-zero exit code. Setup stops after the first installation failure and does not run the next package manager. Installation through the two package managers is not a shared transaction. Failure of the second step does not roll back a successful first step. Repeated setup synchronizes the same locked dependencies. GitHub Actions runs backend, frontend, infrastructure, and security checks in four separate jobs, see the [CI guide](ci.md).

The infrastructure CLI checks Docker daemon availability and port conflicts before startup. Normal shutdown preserves volumes. FastAPI and Next.js run on the host. See the [infrastructure guide](infrastructure.md) for lifecycle commands and isolated acceptance testing.

## Configuration and host isolation

The root [.env.example](../../.env.example) is a backend/infrastructure template without secrets. Copy it to `.env` if needed, without overwriting an existing file. Backend Settings locates the repository-root `.env` from the source file location. The infrastructure CLI reads it with a dotenv parser, with process environment values taking precedence, and runs Compose from the repository root with explicit `--env-file .env -f infra/compose.yaml` paths. Neither loader executes `.env` as shell code, and path resolution does not depend on the caller's working directory.

The frontend template is [`apps/web/.env.local.example`](../../apps/web/.env.local.example), with the local version at `apps/web/.env.local`. API keys must not enter frontend code or public variables. Mock mode does not require a TypeSafe key. Live mode fails without a key.

Python packages may be installed only in the project's `.venv`, and frontend dependencies only in a pnpm-managed project directory. System Python, system Node, and global project-specific npm/pip packages must not be modified. The uv interpreter store and pnpm cache may be user-level.

## Git and editing rules

Use short-lived branches from `main`, review, and squash merge. New tasks may use `feature/fnd-XXX-description`, and fixes may use `fix/fnd-XXX-description`. Commit messages use Conventional Commits in English, for example:

```text
chore(repo): initialize monorepo development tooling
```

Do not add a co-author to commit messages. The [PR template](../../.github/pull_request_template.md) records quality checks.

EditorConfig requires UTF-8, LF, a final newline, 4 spaces for Python and shell, 2 spaces for TypeScript/JSON/YAML, and tabs for Makefiles. Git attributes normalize text and treat designated media types as binary.

`.gitignore` excludes secret files, environments, dependencies, builds, and caches. `.env.example`, `.env.local.example`, and similar templates are exceptions. This does not prevent explicit addition of secrets. Secret-checking details are documented in the [security baseline](security.md).

Before committing, run `git status --short`, `git diff --check`, and `make smoke`, and record any `doctor` discrepancies. Review the contents of new files alongside the diff, because `git diff` alone does not show untracked files. Verify that changes contain no secrets, `.venv`, `node_modules`, or generated data.

## FND-005–007 validation status

The structure, workspace metadata, Git/editor rules, PR template, CLI, and smoke tests are complete. `make help` and `make smoke` passed. After fixing the Python environment, the real `make doctor` also passed with exit code 0. Checks for uv-managed Python `3.14.8`, Node.js `24.22.1`, pnpm `12.15.0`, Git, Make, uv, Corepack, and Docker Compose succeeded. Diagnostics did not install or modify tools and do not check application or infrastructure readiness. The [Foundation release report](../foundation/release-report.md) records current release validation statuses.

Application quality gate commands: `make lint`, `make format-check`, `make typecheck`, `make test`, and `make check`. Details: [testing](testing.md), [CI](ci.md).

## FND-008–011 validation status

The backend, typed configuration, error handling, and JSON logging are complete. The project was installed using the actual uv.lock. The 36 backend tests, lockfile check, wheel/sdist build, live host HTTP smoke, and updated CLI smoke test passed. Readiness remains 503 without a real Qdrant adapter. Details and commands: [API README](../../apps/api/README.md), [backend configuration](backend.md).


### FND-012–014 validation

The frontend was created with the official generator. Frozen installation with pnpm 12.15.0, ESLint, Next route typegen and TypeScript, 18 mocked tests, production build without a backend, CLI smoke, and production HTTP smoke passed. After pinning the host versions of Node.js 24.22.1 and pnpm 12.15.0, `make doctor` passed. The lockfile SHA-256 checksum is unchanged, and no regeneration occurred. FND-015–017 records the Qdrant-ready integration, while the current [release report](../foundation/release-report.md) records the complete clean-clone diagnostics flow. Details: [frontend](../../apps/web/README.md).

The FND-015–017 infrastructure and real Qdrant readiness are complete. Current commands and validation: [infrastructure](infrastructure.md).

`make test` runs offline backend and frontend tests. `make jev-smoke` is a separately authorized live TypeSafe check and is not part of normal test execution. Details: [Jev integration](jev-integration.md).
